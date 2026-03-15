"""
test_recruiter_finder.py — pytest tests for recruiter scoring + dedup.

Run: uv run pytest job_ranker/tests/test_recruiter_finder.py -v
"""
import pytest
from job_ranker.scrapers.recruiter_finder import _clean_title


class TestCleanTitle:
    def test_truncates_at_pipe(self):
        raw = "Senior Recruiter at Adobe | LinkedIn"
        assert _clean_title(raw) == "Senior Recruiter at Adobe"

    def test_truncates_at_newline(self):
        raw = "Natasha Castelino - Recruiter-Cognizant| LinkedIn\nRajesh Kumar - Manager - Cognizant"
        result = _clean_title(raw)
        assert "Rajesh Kumar" not in result
        # Newline comes before pipe — only newline split should apply, pipe segment preserved
        assert result == "Natasha Castelino - Recruiter-Cognizant| LinkedIn"

    def test_truncates_at_spaced_dash(self):
        # Only " - " (with spaces) triggers split, not every hyphen
        raw = "HR - Talent Acquisition @ Cognizant - LinkedIn IndiaRajesh Kumar"
        # Splits at first " - "
        result = _clean_title(raw)
        assert result == "HR"

    def test_preserves_clean_title_unchanged(self):
        raw = "Senior Technical Recruiter"
        assert _clean_title(raw) == "Senior Technical Recruiter"

    def test_caps_at_120_chars(self):
        raw = "A" * 200
        assert len(_clean_title(raw)) <= 120

    def test_empty_string(self):
        assert _clean_title("") == ""

    def test_none_returns_empty(self):
        assert _clean_title(None) == ""

    def test_hyphen_without_spaces_not_split(self):
        # "Recruiter-Cognizant" — hyphen without surrounding spaces, should NOT split
        raw = "Recruiter-Cognizant"
        assert _clean_title(raw) == "Recruiter-Cognizant"

    def test_breaks_after_first_separator(self):
        # Without break, this would: find \n, truncate to "Foo | Bar", then find |, truncate to "Foo"
        # With break, stops after first separator match (newline comes first in loop, stops there)
        raw = "Foo | Bar\nBaz"
        assert _clean_title(raw) == "Foo | Bar"


from job_ranker.scrapers.recruiter_finder import score_recruiter


class TestScoreRecruiter:
    def test_non_recruiter_returns_zero(self):
        # No recruiter term in title
        assert score_recruiter("CometChat", "ML Platform Engineer") == 0.0

    def test_none_title_returns_zero(self):
        assert score_recruiter(None, "ML Engineer") == 0.0

    def test_empty_title_returns_zero(self):
        assert score_recruiter("", "ML Engineer") == 0.0

    def test_baseline_generic_recruiter(self):
        # Has recruiter term but no function keyword overlap
        score = score_recruiter("HR Manager", "ML Platform Engineer")
        assert 0.0 < score < 0.5

    def test_technical_recruiter_for_engineering_job(self):
        score = score_recruiter("Senior Technical Recruiter", "Backend Software Engineer")
        assert score >= 0.5

    def test_ml_keywords_in_both(self):
        score = score_recruiter("Talent Acquisition - ML & AI Roles", "Senior ML Engineer")
        assert score >= 0.7

    def test_product_recruiter_for_pm_job(self):
        # "product" bare word must be in _FUNCTION_KEYWORDS["product"] for overlap to fire
        score = score_recruiter("Talent Acquisition - Product Hiring", "Senior Product Manager")
        assert score >= 0.7  # passes only if "product" is in _FUNCTION_KEYWORDS["product"]

    def test_generic_ta_beats_non_recruiter(self):
        ta_score = score_recruiter("Talent Acquisition Specialist", "Data Engineer")
        non_rec = score_recruiter("Product Owner at Workday", "Data Engineer")
        assert ta_score > non_rec

    def test_empty_job_title(self):
        # No job title to match against — still a recruiter, gets baseline
        score = score_recruiter("Senior Recruiter", "")
        assert 0.0 < score <= 0.3

    def test_none_job_title(self):
        score = score_recruiter("Talent Acquisition Specialist", None)
        assert 0.0 < score <= 0.3

    def test_score_zero_point_zero_boundary(self):
        # Exactly 0.0 must be returned (not 0.001) for non-recruiter titles
        assert score_recruiter("Software Engineer", "ML Engineer") == 0.0
        assert score_recruiter("Sumo Logic", "Senior Engineer") == 0.0
