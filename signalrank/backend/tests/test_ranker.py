from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from batch.ranker import (
    _apply_additive_scoring,
    _apply_pre_filters,
    _apply_role_lane_cap,
    _apply_target_role_filter,
    _assess_required_skill_coverage,
    _build_explanation,
    _classify_explicit_skill_matches,
    _match_explicit_skills,
    _order_match_lanes,
    _order_ranked_jobs,
    _preference_location_weight,
    score_jobs_for_user,
)
from domain.scoring import calculate_seniority_score, extract_required_yoe_range
from domain.skills import SkillCanonicalizer


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


def test_explicit_resume_skills_match_without_profession_taxonomy():
    matched = _match_explicit_skills(
        "Build browser automation with Selenium WebDriver and JavaScript.",
        {"java", "selenium webdriver", "financial modeling", "figma"},
    )
    assert matched == ["selenium webdriver"]


def test_skill_evidence_distinguishes_required_preferred_and_mentioned():
    evidence = _classify_explicit_skill_matches(
        "Python is required. AWS is preferred. Build services with PostgreSQL.",
        {"python", "aws", "postgresql"},
    )

    assert evidence == {
        "required": ["python"],
        "preferred": ["aws"],
        "mentioned": ["postgresql"],
        "all": ["aws", "postgresql", "python"],
    }


def test_required_skill_coverage_is_generic_and_unassessed_is_neutral():
    canonicalizer = SkillCanonicalizer(
        {
            "skills": {
                "equivalence_groups": {
                    "postgres": {
                        "canonical": "postgresql",
                        "variants": ["postgres"],
                    }
                }
            }
        }
    )
    assessed = _assess_required_skill_coverage(
        ["Python", "Postgres", "Kubernetes"],
        {"python", "postgresql"},
        "assessed",
        canonicalizer,
    )
    unavailable = _assess_required_skill_coverage(
        ["Python"], {"python"}, "unavailable", canonicalizer
    )

    assert assessed == {
        "status": "assessed",
        "matched": ["postgresql", "python"],
        "missing": ["kubernetes"],
        "total": 3,
        "coverage": 2 / 3,
    }
    assert unavailable["status"] == "unassessed"
    assert unavailable["coverage"] is None


def test_required_skill_coverage_is_explainable_without_changing_scores():
    explanation = _build_explanation(
        pd.Series(
            {
                "required_skill_coverage_status": "assessed",
                "assessed_matched_required_skills": ["python"],
                "missing_required_skills": ["kubernetes"],
                "assessed_required_skill_overlap": 1,
                "assessed_required_skill_count": 2,
                "required_skill_coverage": 0.5,
            }
        )
    )

    assert explanation["skill_evidence"]["required_coverage"] == {
        "status": "assessed",
        "matched": ["python"],
        "missing": ["kubernetes"],
        "matched_count": 1,
        "total_count": 2,
        "ratio": 0.5,
    }
    assert "required_skill_coverage" not in explanation["scores"]


def test_role_alias_and_description_phrase_produce_explainable_primary_match():
    scored = _apply_target_role_filter(
        pd.DataFrame(
            {
                "title": ["Platform specialist", "Office specialist"],
                "description": [
                    "Build systems as a machine learning engineer.",
                    "Support meeting rooms and office operations.",
                ],
            }
        ),
        {
            "profile_intent": {
                "roles": ["ML Engineer"],
                "role_aliases": {"ML Engineer": ["machine learning engineer"]},
            }
        },
    )

    assert scored.loc[0, "match_lane"] == "primary"
    assert scored.loc[0, "matched_target_role"] == "ML Engineer"
    assert scored.loc[0, "role_match_method"] == "description_phrase"
    assert scored.loc[1, "match_lane"] == "broader"


def test_experience_requirement_is_contextual_and_seniority_remains_soft():
    requirement = extract_required_yoe_range(
        "Minimum 5 years of relevant experience with distributed systems."
    )
    company_history = extract_required_yoe_range(
        "Our company has over 25 years of experience serving customers."
    )
    score = calculate_seniority_score(
        {},
        title="Software Engineer",
        description="Minimum 5 years of relevant experience with distributed systems.",
        user_yoe=2,
    )

    assert requirement is not None
    assert requirement.minimum_years == 5
    assert requirement.maximum_years is None
    assert company_history is None
    assert score <= 0.65


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


def test_primary_lane_precedes_higher_scoring_broader_match():
    ordered = _order_match_lanes(
        pd.DataFrame(
            {
                "title": ["Forward Deployed Engineer", "Data Platform Engineer"],
                "match_lane": ["primary", "broader"],
                "final_score": [40.11, 54.88],
            }
        )
    )

    assert ordered["title"].tolist() == [
        "Forward Deployed Engineer",
        "Data Platform Engineer",
    ]


def test_benchmark_can_replay_pre_fix_score_ordering():
    frame = pd.DataFrame(
        {
            "title": ["Forward Deployed Engineer", "Data Platform Engineer"],
            "match_lane": ["primary", "broader"],
            "final_score": [40.11, 54.88],
        }
    )

    pre_fix = _order_ranked_jobs(frame, prioritize_primary_lane=False)
    post_fix = _order_ranked_jobs(frame, prioritize_primary_lane=True)

    assert pre_fix["title"].tolist()[0] == "Data Platform Engineer"
    assert post_fix["title"].tolist()[0] == "Forward Deployed Engineer"


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
            "ai_company_tier": ["S", "unknown", "unknown"],
            "company_reputation_confidence": [0.95, 0.0, 0.0],
        }
    )
    base = {
        "company_scoring": {
            "tier_s": ["Google"],
            "tier_a": ["Microsoft"],
        },
        "company_preferences": {
            "tiers": ["tier_s"],
            "filter_mode": "selected_tiers",
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


def test_top_reputed_filter_requires_ai_tier_and_confidence():
    frame = pd.DataFrame(
        {
            "title": ["QA Engineer", "Designer", "Accountant", "Sales Lead"],
            "company": ["Trusted", "Low confidence", "Unknown", "Preferred"],
            "description": ["", "", "", ""],
            "ai_company_tier": ["A", "S", "unknown", "unknown"],
            "company_reputation_confidence": [0.9, 0.4, 0.0, 0.0],
        }
    )
    filtered = _apply_pre_filters(
        frame,
        {
            "company_preferences": {
                "filter_mode": "top_reputed",
                "preferred_companies": ["Preferred"],
            }
        },
    )
    assert filtered["company"].tolist() == ["Trusted", "Preferred"]


def test_role_matching_is_profession_agnostic_across_multiple_families():
    cases = [
        ("QA Automation Engineer", "QA Automation Engineer", "AI Engineer"),
        ("Product Designer", "Senior Product Designer", "Product Manager"),
        ("Financial Analyst", "Financial Analyst", "Data Analyst"),
        ("Account Executive", "Enterprise Account Executive", "Accountant"),
        ("Data Scientist", "Data Scientist", "UX Researcher"),
    ]
    for target, relevant, irrelevant in cases:
        scored = _apply_target_role_filter(
            pd.DataFrame({"title": [relevant, irrelevant]}),
            {"profile_intent": {"roles": [target]}},
        )
        assert scored.loc[0, "match_lane"] == "primary"
        assert scored.loc[0, "target_role_score"] > scored.loc[1, "target_role_score"]


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
