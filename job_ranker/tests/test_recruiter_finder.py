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
