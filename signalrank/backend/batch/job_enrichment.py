import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import JobEnrichment, JobRaw
from llm.job_enrichment import (
    PROMPT_VERSION,
    RUBRIC_VERSION,
    JobCandidate,
    JobEnrichmentAssessment,
    JobEnrichmentAssessor,
)
from llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobEnrichmentResult:
    assessed: int = 0
    unavailable: int = 0
    cached: int = 0
    status: str = "complete"


def _content_sha256(job: JobRaw) -> str:
    payload = "\n".join(
        " ".join(str(value or "").split())
        for value in (job.title, job.description, job.location)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


def _candidate(job: JobRaw) -> JobCandidate:
    return JobCandidate(
        job_key=str(job.id),
        title=str(job.title or ""),
        description=str(job.description or ""),
        location=str(job.location or ""),
    )


def _unavailable_assessment(job: JobRaw) -> JobEnrichmentAssessment:
    return JobEnrichmentAssessment(
        job_key=str(job.id),
        role_summary=None,
        role_aliases=[],
        seniority_band="unknown",
        required_skills=[],
        preferred_skills=[],
        workplace={"mode": "unknown", "locations": []},
        coherence_status="unassessed",
        coherence_confidence=0.0,
        coherence_reason=None,
        assessment_status="unavailable",
        model_id=None,
    )


def _store(
    db: AsyncSession,
    job: JobRaw,
    assessment: JobEnrichmentAssessment,
    existing: JobEnrichment | None,
    now: datetime,
    ttl_days: int,
) -> None:
    row = existing
    if row is None:
        row = JobEnrichment(job_id=str(job.id), content_sha256=_content_sha256(job))
        db.add(row)
    row.content_sha256 = _content_sha256(job)
    row.role_summary = assessment.role_summary
    row.role_aliases = assessment.role_aliases
    row.seniority_band = assessment.seniority_band
    row.required_skills = assessment.required_skills
    row.preferred_skills = assessment.preferred_skills
    row.workplace = assessment.workplace
    row.coherence_status = assessment.coherence_status
    row.coherence_confidence = assessment.coherence_confidence
    row.coherence_reason = assessment.coherence_reason
    row.assessment_status = assessment.assessment_status
    row.model_id = assessment.model_id
    row.prompt_hash = PROMPT_VERSION
    row.rubric_version = RUBRIC_VERSION
    row.assessed_at = now
    row.expires_at = now + timedelta(days=ttl_days)


async def enrich_job_postings(
    db: AsyncSession,
    llm: OpenRouterClient | None,
    *,
    ttl_days: int = 30,
    max_jobs: int | None = 24,
) -> JobEnrichmentResult:
    """Cache a candidate-independent reading of fresh job descriptions.

    An unavailable model writes an explicit neutral state. Ranking must never
    reinterpret this as a negative fit signal.
    """

    statement = (
        select(JobRaw)
        .where(JobRaw.active.is_(True))
        .order_by(JobRaw.last_seen.desc(), JobRaw.id)
    )
    if max_jobs is not None:
        statement = statement.limit(max(0, max_jobs))
    jobs = list((await db.execute(statement)).scalars())
    if not jobs:
        return JobEnrichmentResult()

    job_ids = [str(job.id) for job in jobs]
    rows = await db.execute(
        select(JobEnrichment).where(JobEnrichment.job_id.in_(job_ids))
    )
    existing = {str(row.job_id): row for row in rows.scalars()}
    now = datetime.now(timezone.utc)
    pending = [
        job
        for job in jobs
        if (
            (row := existing.get(str(job.id))) is None
            or row.content_sha256 != _content_sha256(job)
            or _expired(row.expires_at, now)
        )
    ]
    if not pending:
        return JobEnrichmentResult(cached=len(jobs))

    assessments: dict[str, JobEnrichmentAssessment]
    status = "complete"
    if llm is None:
        assessments = {str(job.id): _unavailable_assessment(job) for job in pending}
        status = "unavailable"
    else:
        preflight = await llm.preflight()
        if not preflight.authenticated:
            logger.warning("Skipping job enrichment: %s", preflight.status)
            assessments = {str(job.id): _unavailable_assessment(job) for job in pending}
            status = preflight.status
        else:
            assessments = await JobEnrichmentAssessor(llm).assess(
                _candidate(job) for job in pending
            )

    assessed = 0
    unavailable = 0
    for job in pending:
        assessment = assessments.get(str(job.id)) or _unavailable_assessment(job)
        _store(db, job, assessment, existing.get(str(job.id)), now, ttl_days)
        if assessment.assessment_status == "assessed":
            assessed += 1
        else:
            unavailable += 1
    await db.commit()
    return JobEnrichmentResult(
        assessed=assessed,
        unavailable=unavailable,
        cached=len(jobs) - len(pending),
        status=status,
    )
