# tests/test_scoring.py
"""Tests for the weighted additive scoring model."""

from datetime import datetime, timedelta, timezone

import pytest

from job_ranker.domain.additive_scoring import (
    apply_company_semantic_floor,
    apply_hidden_gem_bonus,
    company_score_0_100,
    compute_weighted_score,
    detect_contract_type,
    location_score_0_100,
    recency_score_0_100,
    seniority_score_0_100,
    skills_score_0_100,
)


# ---- Skills dimension ----

class TestSkillsScore:
    def test_high_semantic(self):
        score = skills_score_0_100(0.90, 0, 1.0, 1.0, 1.0)
        assert 88 <= score <= 92

    def test_low_semantic(self):
        score = skills_score_0_100(0.30, 0, 1.0, 1.0, 1.0)
        assert 28 <= score <= 32

    def test_skill_overlap_bonus(self):
        base = skills_score_0_100(0.70, 0, 1.0, 1.0, 1.0)
        with_overlap = skills_score_0_100(0.70, 5, 1.0, 1.0, 1.0)
        assert with_overlap - base == pytest.approx(8.0)  # capped at 8

    def test_consulting_dampener(self):
        normal = skills_score_0_100(0.80, 0, 1.0, 1.0, 1.0)
        damped = skills_score_0_100(0.80, 0, 1.0, 1.0, 0.8)
        assert normal - damped == pytest.approx(10.0)

    def test_clamp_to_100(self):
        score = skills_score_0_100(1.0, 10, 1.4, 1.2, 1.0)
        assert score == 100.0

    def test_clamp_to_0(self):
        score = skills_score_0_100(0.0, 0, 0.6, 0.8, 0.8)
        assert score == 0.0


# ---- Company dimension ----

class TestCompanyScore:
    def test_tier_s(self):
        assert company_score_0_100("tier_s") == 100.0

    def test_tier_a(self):
        assert company_score_0_100("tier_a") == 85.0

    def test_tier_b(self):
        assert company_score_0_100("tier_b") == 65.0

    def test_tier_c(self):
        assert company_score_0_100("tier_c") == 45.0

    def test_tier_d(self):
        assert company_score_0_100("tier_d") == 15.0

    def test_default(self):
        assert company_score_0_100("default") == 40.0

    def test_legacy_preferred(self):
        assert company_score_0_100("preferred") == 100.0

    def test_legacy_deprioritized(self):
        assert company_score_0_100("deprioritized") == 15.0

    def test_unknown_tier(self):
        assert company_score_0_100("something_else") == 40.0


# ---- Seniority dimension ----

class TestSeniorityScore:
    def test_junior_minimum(self):
        score = seniority_score_0_100(0.4)
        assert score == pytest.approx(10.0)

    def test_neutral(self):
        score = seniority_score_0_100(1.0)
        assert 70 <= score <= 82

    def test_senior_maximum(self):
        score = seniority_score_0_100(1.15)
        assert score == pytest.approx(100.0)

    def test_below_range(self):
        score = seniority_score_0_100(0.2)
        assert score == 0.0  # clamped


# ---- Location dimension ----

class TestLocationScore:
    def test_preferred(self):
        assert location_score_0_100(1.2) == 100.0

    def test_no_match(self):
        assert location_score_0_100(1.0) == 30.0


# ---- Recency dimension ----

class TestRecencyScore:
    def test_today(self):
        now = datetime.now(timezone.utc).isoformat()
        score = recency_score_0_100(now)
        assert 98 <= score <= 100

    def test_30_days(self):
        d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        score = recency_score_0_100(d)
        assert 28 <= score <= 32

    def test_none(self):
        assert recency_score_0_100(None) == 30.0

    def test_naive_datetime(self):
        """Naive datetimes (no tz) should be treated as UTC, not return default."""
        d = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        score = recency_score_0_100(d)
        assert 78 <= score <= 82  # ~80 for 7-day-old

    def test_very_old(self):
        d = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        score = recency_score_0_100(d)
        assert score == 10.0


# ---- Weighted sum ----

class TestWeightedScore:
    def test_arithmetic(self):
        scores = {
            "skills_match": 80,
            "company_fit": 100,
            "seniority": 60,
            "location": 100,
            "recency": 50,
        }
        expected = 80 * 0.40 + 100 * 0.20 + 60 * 0.15 + 100 * 0.15 + 50 * 0.10
        assert compute_weighted_score(scores) == pytest.approx(expected)

    def test_weights_sum_to_one(self):
        from job_ranker.domain.additive_scoring import DEFAULT_WEIGHTS
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_custom_weights(self):
        scores = {
            "skills_match": 100,
            "company_fit": 0,
            "seniority": 0,
            "location": 0,
            "recency": 0,
        }
        custom = {"skills_match": 1.0, "company_fit": 0, "seniority": 0, "location": 0, "recency": 0}
        assert compute_weighted_score(scores, custom) == pytest.approx(100.0)


from job_ranker.domain.scoring import calculate_seniority_score


class TestSeniorityScoring:
    """Tests for calculate_seniority_score including over-seniority."""

    BASE_CFG = {
        "ranking": {
            "seniority_penalty": {
                "junior_multiplier": 0.4,
                "low_yoe_multiplier": 0.5,
                "over_senior_multiplier": 0.7,
                "title_keywords": {
                    "junior": ["intern", "junior", "entry"],
                    "over_senior": ["director", "head of", "chief"],
                },
            },
            "seniority_boosting_keywords": ["senior", "lead", "staff", "principal"],
        },
    }

    def test_director_gets_penalty(self):
        score = calculate_seniority_score(
            self.BASE_CFG, title="Director of Engineering", description="", user_yoe=7
        )
        assert score == pytest.approx(0.7)

    def test_vp_no_penalty(self):
        """VP at finance companies is senior IC, not management."""
        score = calculate_seniority_score(
            self.BASE_CFG, title="VP of Engineering", description="", user_yoe=7
        )
        assert score >= 1.0  # Should get senior boost, not penalty

    def test_head_of_gets_penalty(self):
        score = calculate_seniority_score(
            self.BASE_CFG, title="Head of AI Platform", description="", user_yoe=7
        )
        assert score == pytest.approx(0.7)

    def test_senior_engineer_no_penalty(self):
        score = calculate_seniority_score(
            self.BASE_CFG, title="Senior Software Engineer", description="", user_yoe=7
        )
        assert score >= 1.0  # Gets a boost, not a penalty

    def test_principal_engineer_no_penalty(self):
        """Principal is senior-boosted, not over-senior penalized."""
        score = calculate_seniority_score(
            self.BASE_CFG, title="Principal Engineer", description="", user_yoe=7
        )
        assert score >= 1.0


class TestCompanySemanticFloor:
    """company_score should be scaled down when semantic_score is below the floor."""

    def test_above_floor_unchanged(self):
        assert apply_company_semantic_floor(100.0, 0.70, 0.60) == pytest.approx(100.0)

    def test_at_floor_unchanged(self):
        assert apply_company_semantic_floor(100.0, 0.60, 0.60) == pytest.approx(100.0)

    def test_below_floor_scaled(self):
        result = apply_company_semantic_floor(100.0, 0.50, 0.60)
        assert result == pytest.approx(83.333, abs=0.1)

    def test_low_semantic_heavy_scaling(self):
        result = apply_company_semantic_floor(100.0, 0.40, 0.60)
        assert result == pytest.approx(66.667, abs=0.1)

    def test_tier_a_below_floor(self):
        result = apply_company_semantic_floor(85.0, 0.50, 0.60)
        assert result == pytest.approx(85.0 * 0.50 / 0.60, abs=0.1)

    def test_zero_floor_no_scaling(self):
        assert apply_company_semantic_floor(100.0, 0.30, 0.0) == pytest.approx(100.0)


class TestHiddenGemBonus:
    """Unknown-tier companies with high semantic score get a company_score bump."""

    def test_unknown_high_semantic_gets_bonus(self):
        result = apply_hidden_gem_bonus(40.0, "default", 0.75)
        assert result == 60.0

    def test_unknown_low_semantic_no_bonus(self):
        result = apply_hidden_gem_bonus(40.0, "default", 0.65)
        assert result == 40.0

    def test_known_tier_no_bonus(self):
        """Tier_s company should not get the bonus even with high semantic."""
        result = apply_hidden_gem_bonus(100.0, "tier_s", 0.80)
        assert result == 100.0

    def test_tier_a_no_bonus(self):
        result = apply_hidden_gem_bonus(85.0, "tier_a", 0.80)
        assert result == 85.0

    def test_at_threshold_gets_bonus(self):
        result = apply_hidden_gem_bonus(40.0, "default", 0.70)
        assert result == 60.0

    def test_none_tier_gets_bonus(self):
        """None tier (unclassified) should also get the bonus."""
        result = apply_hidden_gem_bonus(40.0, None, 0.75)
        assert result == 60.0

    def test_custom_threshold_and_bonus(self):
        result = apply_hidden_gem_bonus(40.0, "default", 0.80, threshold=0.75, bonus_score=70.0)
        assert result == 70.0


class TestContractDetection:
    """Detect contract/part-time signals in title and description prefix."""

    def test_part_time_in_title(self):
        assert detect_contract_type("Part-Time Data Scientist", "") is True

    def test_contract_in_title(self):
        assert detect_contract_type("Contract ML Engineer", "") is True

    def test_freelance_in_title(self):
        assert detect_contract_type("Freelance AI Developer", "") is True

    def test_hours_per_day_in_description(self):
        assert detect_contract_type("Data Scientist", "3 hours per day remote position") is True

    def test_normal_job_no_signal(self):
        assert detect_contract_type("Senior ML Engineer", "Full-time role at a fast-growing startup") is False

    def test_signal_beyond_200_chars_ignored(self):
        """Only first 200 chars of description are scanned."""
        long_desc = "x" * 201 + " contract position"
        assert detect_contract_type("ML Engineer", long_desc) is False

    def test_temporary_in_title(self):
        assert detect_contract_type("Temporary Software Engineer", "") is True

    def test_backslash_escaped_part_time(self):
        """Markdown-escaped 'Part\\-Time' should still be detected."""
        assert detect_contract_type("ML Engineer", "Type: \\- Part\\-Time") is True

    def test_hr_per_day(self):
        assert detect_contract_type("Data Scientist", "3 hr/day remote") is True


from job_ranker.domain.roles import classify_functional_role


class TestTitleWeightedClassification:
    """Title keywords should count 3x more than description keywords in heuristic fallback."""

    BASE_CFG = {
        "functional_role_taxonomy": {
            "architecture_strategy": {
                "keywords": ["enterprise architect", "solution architect"],
            },
            "customer_facing": {
                "keywords": ["customer engineer", "sales engineer"],
            },
        },
        "functional_role_terms": {
            "ai": ["llm", "agent", "rag", "embedding", "inference"],
            "devops": ["kubernetes", "terraform", "ci/cd", "pipeline"],
            "security": ["siem", "soc", "threat"],
        },
        "functional_role_thresholds": {
            "security_min_terms": 2,
            "agentic_min_terms": 3,
            "mlops_ai_terms": 1,
            "mlops_devops_terms": 1,
            "platform_devops_min_terms": 2,
        },
    }

    def test_taxonomy_match_still_works(self):
        """Taxonomy match uses full text — should still catch 'customer engineer'."""
        result = classify_functional_role(
            "Customer Engineer", "Build AI solutions with LLM and RAG", self.BASE_CFG
        )
        assert result == "customer_facing"

    def test_ai_title_gets_boosted(self):
        """Title with AI terms should classify as agentic even with few description terms."""
        result = classify_functional_role(
            "LLM Agent Engineer",
            "Work on embedding systems",
            self.BASE_CFG,
        )
        # Title: llm(3) + agent(3) = 6, Desc: embedding(1) = 1, Total AI = 7 >= 3
        assert result == "agentic_systems"

    def test_generic_title_ai_description_not_agentic(self):
        """Generic title + AI description shouldn't easily reach agentic threshold."""
        result = classify_functional_role(
            "Software Engineer",
            "Work with llm and agent systems",
            self.BASE_CFG,
        )
        # Title: 0 AI terms, Desc: llm(1) + agent(1) = 2, Total AI = 2 < 3
        assert result != "agentic_systems"

    def test_mlops_classification(self):
        """Title with devops terms + description with AI -> mlops."""
        result = classify_functional_role(
            "Platform Engineer - Kubernetes",
            "Deploy llm inference services",
            self.BASE_CFG,
        )
        # Title: kubernetes(3), Desc: llm(1)+inference(1)=2. AI=2>=1, DevOps=3>=1 -> mlops
        assert result == "mlops_llmops"
