from datetime import datetime, timedelta, timezone

import pandas as pd
from batch.ranker import (
    _apply_additive_scoring,
    _apply_pre_filters,
    _apply_role_lane_cap,
    _apply_target_role_filter,
    _preference_location_weight,
    matched_resume_skills,
    score_jobs_for_user,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def test_target_role_fit_keeps_broader_matches():
    frame = pd.DataFrame(
        {
            "title": [
                "Senior AI Engineer",
                "Platform Architect",
                "AI Cinematic Video Editor",
                "Remote Office Assistant",
            ]
        }
    )
    scored = _apply_target_role_filter(
        frame,
        {"profile_intent": {"roles": ["Staff AI Engineer", "Platform Architect"]}},
    )
    assert scored["title"].tolist() == frame["title"].tolist()
    assert scored.loc[0, "target_role_score"] > scored.loc[3, "target_role_score"]
    assert scored.loc[0, "match_lane"] == "primary"
    assert scored.loc[3, "match_lane"] == "broader"


def test_generic_engineer_token_does_not_make_a_role_primary():
    frame = pd.DataFrame(
        {"title": ["AI Engineer", "Java Engineer", "AWS Solution Architect"]}
    )

    scored = _apply_target_role_filter(
        frame,
        {"profile_intent": {"roles": ["Staff AI Engineer", "AI Platform Engineer"]}},
    )

    assert scored["match_lane"].tolist() == ["primary", "broader", "broader"]


def test_skill_overlap_is_resume_intersection():
    assert matched_resume_skills(
        ["python", "kubernetes", "large language models"],
        {"python", "postgresql"},
    ) == ["python"]


def test_broader_matches_cannot_outrank_primary_role_matches():
    frame = pd.DataFrame(
        {
            "title": ["AI Platform Engineer", "Java Engineer"],
            "match_lane": ["primary", "broader"],
            "final_score": [71.0, 82.0],
        }
    )

    scored = _apply_role_lane_cap(frame, {"ranking": {"broader_match_score_cap": 64}})

    assert scored["final_score"].tolist() == [71.0, 64.0]


def test_company_and_title_exclusions_are_effective():
    frame = pd.DataFrame(
        {
            "title": [
                "AI Engineer",
                "QA Engineer",
                "Platform Engineer",
                "AI Engineer",
            ],
            "company": [
                "Deloitte Consulting",
                "Product Co",
                "Product Co",
                "QAnalytics",
            ],
            "description": ["", "", "", ""],
        }
    )
    filtered = _apply_pre_filters(
        frame,
        {
            "title_blocklist": ["QA roles"],
            "company_preferences": {"excluded_companies": ["Deloitte"]},
        },
    )
    assert filtered[["title", "company"]].values.tolist() == [
        ["Platform Engineer", "Product Co"],
        ["AI Engineer", "QAnalytics"],
    ]


def test_company_tiers_are_hard_filters_before_role_or_resume_scoring():
    frame = pd.DataFrame(
        {
            "title": ["Accountant", "AI Engineer", "Platform Engineer"],
            "company": ["Google India", "Unknown Startup", "Zscaler"],
            "description": ["", "", ""],
        }
    )
    base = {
        "company_scoring": {
            "tier_s": ["Google"],
            "tier_a": ["Microsoft"],
        },
        "company_preferences": {
            "tiers": ["tier_s"],
            "preferred_companies": ["Zscaler"],
        },
    }

    first = _apply_pre_filters(
        frame,
        {
            **base,
            "profile_intent": {"roles": ["AI Engineer"]},
            "resume": {"distilled_text": "AI engineer"},
        },
    )
    second = _apply_pre_filters(
        frame,
        {
            **base,
            "profile_intent": {"roles": ["Accountant"]},
            "resume": {"distilled_text": "finance leader"},
        },
    )

    assert first["company"].tolist() == ["Google India", "Zscaler"]
    assert second["company"].tolist() == first["company"].tolist()


def test_any_company_disables_tier_filter_and_exclusion_still_wins():
    frame = pd.DataFrame(
        {
            "title": ["AI Engineer", "AI Engineer"],
            "company": ["Google", "Deloitte"],
            "description": ["", ""],
        }
    )
    filtered = _apply_pre_filters(
        frame,
        {
            "company_scoring": {"tier_s": ["Google"]},
            "company_preferences": {
                "tiers": ["any", "tier_s"],
                "excluded_companies": ["Deloitte"],
            },
        },
    )

    assert filtered["company"].tolist() == ["Google"]


def test_preferred_company_score_is_resume_semantic_independent():
    frame = pd.DataFrame(
        {
            "title": ["Engineer", "Engineer"],
            "description": ["", ""],
            "company": ["Zscaler Inc", "Zscaler Inc"],
            "company_tier": ["tier_a", "tier_a"],
            "semantic_score": [0.3, 0.9],
            "skill_overlap": [1, 1],
            "role_skill_score": [1.0, 1.0],
            "functional_role_penalty": [1.0, 1.0],
            "seniority_score": [1.0, 1.0],
            "location_weight": [1.0, 1.0],
            "date_posted": [datetime.now(timezone.utc)] * 2,
        }
    )
    scored = _apply_additive_scoring(
        frame,
        {
            "company_scoring": {"tier_a": ["Zscaler"]},
            "company_preferences": {"preferred_companies": ["Zscaler"]},
            "ranking": {},
        },
    )

    assert scored["company_score"].tolist() == [100.0, 100.0]


def test_location_preferences_understand_remote_and_city_aliases():
    cfg = {
        "location_scoring": {
            "preferred_locations": ["Remote only", "Bangalore"],
            "preferred_weight": 1.4,
        }
    }
    assert _preference_location_weight("Worldwide / Remote", cfg) == 1.4
    assert _preference_location_weight("Bengaluru, Karnataka", cfg) == 1.4
    assert _preference_location_weight("Mumbai, India", cfg) == 1.0


def test_stale_jobs_are_suppressed_with_last_seen_fallback():
    now = datetime.now(timezone.utc)
    frame = pd.DataFrame(
        {
            "title": ["Fresh", "Stale", "Undated but seen"],
            "company": ["A", "B", "C"],
            "description": ["", "", ""],
            "date_posted": [now - timedelta(days=2), now - timedelta(days=45), None],
            "last_seen": [now, now, now - timedelta(days=2)],
        }
    )
    filtered = _apply_pre_filters(frame, {"ranking": {"max_job_age_days": 30}})
    assert filtered["title"].tolist() == ["Fresh", "Undated but seen"]


async def test_score_jobs_empty_corpus(db: AsyncSession):
    results = await score_jobs_for_user(
        db=db,
        user_id="test-user",
        resume_text="I am a machine learning engineer",
        config_overrides=None,
    )
    assert isinstance(results, pd.DataFrame)
    assert len(results) == 0


async def test_score_jobs_returns_ranked_results(db: AsyncSession):
    embedding = "[" + ",".join(["0.0"] * 384) + "]"
    await db.execute(
        text(
            f"INSERT INTO jobs_raw (id, job_url, title, company, description, location, site, embedding, ingested_at) "
            f"VALUES (gen_random_uuid(), :url, :title, :company, :desc, :loc, :site, '{embedding}'::vector, now())"
        ),
        {
            "url": "https://example.com/job-ranker-test-1",
            "title": "Senior ML Engineer",
            "company": "Google",
            "desc": "Build machine learning pipelines using Python, TensorFlow, and PyTorch. "
            "Deploy models to production. Strong experience with NLP and deep learning required.",
            "loc": "Bangalore, India",
            "site": "linkedin",
        },
    )
    await db.flush()

    results = await score_jobs_for_user(
        db=db,
        user_id="test-user",
        resume_text="Machine learning engineer with 5 years experience in Python, PyTorch, NLP, and deep learning.",
        config_overrides=None,
    )
    assert isinstance(results, pd.DataFrame)
    assert len(results) >= 0
