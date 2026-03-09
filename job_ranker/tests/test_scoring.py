# tests/test_scoring.py
"""Tests for the weighted additive scoring model."""

from datetime import datetime, timedelta, timezone

import pytest

from job_ranker.domain.additive_scoring import (
    company_score_0_100,
    compute_weighted_score,
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
        assert company_score_0_100("default") == 50.0

    def test_legacy_preferred(self):
        assert company_score_0_100("preferred") == 100.0

    def test_legacy_deprioritized(self):
        assert company_score_0_100("deprioritized") == 15.0

    def test_unknown_tier(self):
        assert company_score_0_100("something_else") == 50.0


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
        assert recency_score_0_100(None) == 50.0

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
