from types import SimpleNamespace

import pandas as pd
from sqlalchemy import select

from api.models import JobEnrichment, JobRaw
from batch.job_enrichment import enrich_job_postings
from batch.ranker import _apply_listing_quality, _apply_target_role_filter
from llm.job_enrichment import JobCandidate, JobEnrichmentAssessor


class FakeLLM:
    last_model = "free/test-model"

    def __init__(self):
        self.calls = 0

    async def preflight(self):
        return SimpleNamespace(status="ready", authenticated=True)

    async def llm_json(self, **kwargs):
        self.calls += 1
        key = kwargs["user"].split('"job_key":"', 1)[1].split('"', 1)[0]
        return {
            "assessments": [
                {
                    "job_key": key,
                    "role_summary": "Builds and operates data platforms.",
                    "role_aliases": ["Data Platform Engineer"],
                    "seniority_band": "senior",
                    "required_skills": ["Python"],
                    "preferred_skills": ["Kubernetes"],
                    "workplace": {"mode": "hybrid", "locations": ["Pune"]},
                    "coherence_status": "coherent",
                    "coherence_confidence": 0.9,
                    "coherence_reason": "aligned",
                }
            ]
        }


async def test_job_enrichment_is_cached_by_job_content(db):
    job = JobRaw(
        job_url="https://example.com/job-enrichment",
        title="Data Platform Engineer",
        company="Acme",
        description="Build and operate data platforms with Python.",
        location="Pune",
        active=True,
    )
    db.add(job)
    await db.commit()
    llm = FakeLLM()

    first = await enrich_job_postings(db, llm)
    second = await enrich_job_postings(db, llm)
    row = (await db.execute(select(JobEnrichment))).scalar_one()

    assert first.assessed == 1
    assert second.cached == 1
    assert llm.calls == 1
    assert row.role_aliases == ["Data Platform Engineer"]
    assert row.coherence_status == "coherent"


async def test_unavailable_enrichment_is_explicit_and_neutral(db):
    db.add(
        JobRaw(
            job_url="https://example.com/unavailable-enrichment",
            title="Engineer",
            company="Acme",
            description="Build reliable services.",
            active=True,
        )
    )
    await db.commit()

    result = await enrich_job_postings(db, None)
    row = (await db.execute(select(JobEnrichment))).scalar_one()

    assert result.unavailable == 1
    assert row.assessment_status == "unavailable"
    assert row.coherence_status == "unassessed"
    assert row.coherence_confidence == 0.0


async def test_assessor_rejects_extra_or_invented_schema_fields():
    llm = FakeLLM()
    assessment = await JobEnrichmentAssessor(llm).assess(
        [
            JobCandidate(
                job_key="job-1",
                title="Data Platform Engineer",
                description="Build data systems.",
                location="Pune",
            )
        ]
    )

    assert assessment["job-1"].assessment_status == "assessed"
    assert assessment["job-1"].model_id == "free/test-model"


def test_assessed_contradiction_demotes_but_unassessed_is_neutral():
    frame = pd.DataFrame(
        {
            "final_score": [80.0, 80.0],
            "match_lane": ["primary", "primary"],
            "coherence_status": ["contradictory", "contradictory"],
            "coherence_confidence": [0.9, 0.9],
            "enrichment_status": ["assessed", "unavailable"],
        }
    )

    ranked = _apply_listing_quality(frame, {"ranking": {}})

    assert ranked.loc[0, "match_lane"] == "broader"
    assert ranked.loc[0, "final_score"] < 80.0
    assert ranked.loc[1, "match_lane"] == "primary"
    assert ranked.loc[1, "final_score"] == 80.0


def test_enriched_role_alias_needs_an_assessed_job_reading():
    frame = pd.DataFrame(
        {
            "title": ["Platform Engineer", "Platform Engineer"],
            "description": ["Build systems.", "Build systems."],
            "enriched_role_aliases": [
                ["Forward Deployed Engineer"],
                ["Forward Deployed Engineer"],
            ],
            "enrichment_status": ["assessed", "unavailable"],
        }
    )

    ranked = _apply_target_role_filter(
        frame, {"profile_intent": {"roles": ["Forward Deployed Engineer"]}}
    )

    assert ranked.loc[0, "match_lane"] == "primary"
    assert ranked.loc[0, "role_match_method"] == "enriched_role_alias"
    assert ranked.loc[1, "match_lane"] == "broader"
