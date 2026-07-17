import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import CompanyReputation as CompanyReputationModel, JobRaw
from llm.company_reputation import (
    CompanyCandidate,
    CompanyReputationAssessor,
    canonicalize_company_name,
)
from llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnrichmentResult:
    assessed: int = 0
    unknown: int = 0
    cached: int = 0
    status: str = "complete"


def _expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


async def enrich_company_reputations(
    db: AsyncSession,
    llm: OpenRouterClient,
    *,
    ttl_days: int = 60,
    max_companies: int | None = None,
) -> EnrichmentResult:
    company_count = func.count(JobRaw.id)
    statement = (
        select(JobRaw.company, company_count)
        .where(JobRaw.active.is_(True), JobRaw.company.is_not(None))
        .group_by(JobRaw.company)
        .order_by(company_count.desc(), JobRaw.company)
    )
    if max_companies is not None:
        statement = statement.limit(max(0, max_companies))
    rows = await db.execute(statement)
    display_names: dict[str, str] = {}
    for company, _ in rows:
        canonical = canonicalize_company_name(str(company or ""))
        if canonical:
            display_names.setdefault(canonical, str(company).strip())
    if not display_names:
        return EnrichmentResult()

    existing_rows = await db.execute(
        select(CompanyReputationModel).where(
            CompanyReputationModel.canonical_name.in_(display_names)
        )
    )
    existing = {row.canonical_name: row for row in existing_rows.scalars()}
    now = datetime.now(timezone.utc)
    pending = [
        name
        for name in display_names
        if name not in existing
        or (
            not existing[name].manual_override
            and _expired(existing[name].expires_at, now)
        )
    ]
    if not pending:
        return EnrichmentResult(cached=len(display_names))

    preflight = await llm.preflight()
    if not preflight.authenticated:
        logger.warning("Skipping company enrichment: %s", preflight.status)
        return EnrichmentResult(
            cached=len(display_names) - len(pending),
            status=preflight.status,
        )

    assessor = CompanyReputationAssessor(llm)
    assessments = await assessor.assess(
        [CompanyCandidate(display_names[name]) for name in pending]
    )
    assessed_count = 0
    unknown_count = 0
    for canonical, assessment in assessments.items():
        row = existing.get(canonical)
        if row is None:
            row = CompanyReputationModel(
                canonical_name=canonical,
                display_name=assessment.display_name,
            )
            db.add(row)
        if row.manual_override:
            continue
        row.display_name = assessment.display_name
        row.reputation_score = assessment.score
        row.reputation_tier = assessment.tier
        row.confidence = assessment.confidence
        row.rationale = assessment.rationale
        row.assessment_status = assessment.assessment_status
        row.model_id = assessment.model_id
        row.prompt_hash = assessment.fingerprint
        row.rubric_version = assessment.rubric_version
        row.assessed_at = now
        row.expires_at = now + timedelta(days=ttl_days)
        if assessment.assessment_status == "assessed":
            assessed_count += 1
        else:
            unknown_count += 1
    await db.commit()
    return EnrichmentResult(
        assessed=assessed_count,
        unknown=unknown_count,
        cached=len(display_names) - len(pending),
    )
