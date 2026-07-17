from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from api.models import CompanyReputation, JobRaw
from batch.company_enrichment import _expired, enrich_company_reputations
from llm.openrouter import PreflightStatus


class FakeLLM:
    last_model = "free/test-model"

    def __init__(self):
        self.calls = 0

    async def preflight(self):
        return PreflightStatus(status="ready", authenticated=True)

    async def llm_json(self, **kwargs):
        self.calls += 1
        return {
            "assessments": [
                {
                    "canonical_name": "acme",
                    "score": 72,
                    "tier": "A",
                    "confidence": 0.88,
                    "rationale": "Established employer with a durable public record.",
                }
            ]
        }


def test_expiry_check_accepts_sqlite_naive_datetimes():
    now = datetime.now(timezone.utc)

    assert _expired((now - timedelta(minutes=1)).replace(tzinfo=None), now)
    assert not _expired((now + timedelta(minutes=1)).replace(tzinfo=None), now)


async def test_enrichment_persists_and_reuses_ai_assessment(db):
    db.add(
        JobRaw(
            job_url="https://example.com/company-enrichment",
            title="Accountant",
            company="Acme Pvt Ltd",
            active=True,
        )
    )
    await db.commit()
    llm = FakeLLM()

    first = await enrich_company_reputations(db, llm)
    second = await enrich_company_reputations(db, llm)
    row = (
        await db.execute(
            select(CompanyReputation).where(CompanyReputation.canonical_name == "acme")
        )
    ).scalar_one()

    assert first.assessed == 1
    assert second.cached == 1
    assert llm.calls == 1
    assert row.reputation_tier == "A"
    assert row.confidence == 0.88
    assert row.model_id == "free/test-model"


async def test_enrichment_limit_prioritizes_companies_with_more_jobs(db):
    for index in range(2):
        db.add(
            JobRaw(
                job_url=f"https://example.com/acme-{index}",
                title="Accountant",
                company="Acme Pvt Ltd",
                active=True,
            )
        )
    db.add(
        JobRaw(
            job_url="https://example.com/other",
            title="Accountant",
            company="Other Corp",
            active=True,
        )
    )
    await db.commit()

    llm = FakeLLM()
    result = await enrich_company_reputations(db, llm, max_companies=1)

    assert result.assessed == 1
    assert llm.calls == 1
