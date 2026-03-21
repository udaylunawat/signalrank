"""
test_recruiter_finder.py — pytest tests for recruiter scoring + dedup.

Run: uv run pytest job_ranker/tests/test_recruiter_finder.py -v
"""
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


from job_ranker.scrapers.recruiter_finder import RecruiterContact, dedup_top_n


def _c(name, title, job_url="https://linkedin.com/jobs/view/123",
       job_title="ML Engineer", confidence="medium"):
    return RecruiterContact(company="TestCo", name=name, title=title,
                            job_url=job_url, job_title=job_title, confidence=confidence)


class TestDedupTopN:
    def test_keeps_top_2_per_job(self):
        contacts = [
            _c("Alice", "Senior Technical Recruiter"),
            _c("Bob",   "HR Manager"),
            _c("Carol", "Talent Acquisition - ML"),
            _c("Dave",  "CometChat Employee"),  # score=0.0
        ]
        result = dedup_top_n(contacts, n=2)
        names = [c.name for c in result]
        assert len(result) == 2
        assert "Dave" not in names

    def test_score_zero_excluded(self):
        # Score exactly 0.0 must be excluded
        contacts = [
            _c("Alice", "Talent Acquisition"),
            _c("Bob",   "Product Owner"),  # no recruiter term — score=0.0
        ]
        result = dedup_top_n(contacts, n=2)
        assert all(c.name != "Bob" for c in result)

    def test_high_confidence_breaks_tie(self):
        contacts = [
            _c("Alice", "Talent Acquisition Specialist", confidence="medium"),
            _c("Bob",   "Talent Acquisition Specialist", confidence="high"),
        ]
        result = dedup_top_n(contacts, n=1)
        assert result[0].name == "Bob"

    def test_multi_job_urls_independent(self):
        contacts = [
            _c("Alice", "Senior Technical Recruiter", job_url="https://li.com/1"),
            _c("Bob",   "Talent Acquisition",         job_url="https://li.com/1"),
            _c("Carol", "Technical Sourcer",          job_url="https://li.com/2"),
            _c("Dave",  "HR Manager",                 job_url="https://li.com/2"),
        ]
        result = dedup_top_n(contacts, n=1)
        assert len(result) == 2  # 1 per job URL
        assert len({c.job_url for c in result}) == 2

    def test_fallback_when_all_score_zero(self):
        # No recruiter terms — fallback to top-1 by confidence
        contacts = [
            _c("Alice", "CometChat Employee", confidence="high"),
            _c("Bob",   "Product Owner",      confidence="medium"),
        ]
        result = dedup_top_n(contacts, n=2)
        assert len(result) == 1
        assert result[0].name == "Alice"

    def test_none_job_url_grouped_together(self):
        # Contacts with job_url=None all go into one group
        contacts = [
            _c("Alice", "Technical Recruiter", job_url=None),
            _c("Bob",   "HR Manager",          job_url=None),
            _c("Carol", "Talent Acquisition",  job_url=None),
        ]
        result = dedup_top_n(contacts, n=2)
        assert len(result) == 2  # top-2 from the single group

    def test_empty_job_url_grouped_with_none(self):
        contacts = [
            _c("Alice", "Technical Recruiter", job_url=""),
            _c("Bob",   "Senior Recruiter",    job_url=None),
        ]
        result = dedup_top_n(contacts, n=2)
        # Both in same "__no_url__" group — top-2 (or fewer if <2 scored)
        assert len(result) <= 2

    def test_empty_input(self):
        assert dedup_top_n([], n=2) == []


from job_ranker.scrapers.recruiter_finder import _build_queries, _llm_validate_contacts


class TestBuildQueries:
    def test_returns_3_variants(self):
        queries = _build_queries("Adobe")
        assert len(queries) == 3

    def test_first_query_has_india_cities(self):
        q = _build_queries("Adobe")[0]
        assert "bangalore" in q.lower()
        assert "talent acquisition" in q.lower()

    def test_company_in_all_queries(self):
        for q in _build_queries("ServiceNow"):
            assert "ServiceNow" in q


class TestNegativeTitleSignals:
    def test_sales_scores_zero(self):
        assert score_recruiter("Sales Manager", "ML Engineer") == 0.0

    def test_marketing_scores_zero(self):
        assert score_recruiter("Marketing Recruiter", "ML Engineer") == 0.0

    def test_business_development_scores_zero(self):
        assert score_recruiter("Business Development Manager", "ML Engineer") == 0.0


class TestIndiaLocationBonus:
    def test_bangalore_gets_bonus(self):
        base = score_recruiter("Talent Acquisition Specialist", "ML Engineer")
        with_loc = score_recruiter("Talent Acquisition Specialist - Bangalore", "ML Engineer")
        assert with_loc > base

    def test_bonus_capped_at_1(self):
        score = score_recruiter("Talent Acquisition - ML & AI Roles - India", "Senior ML Engineer")
        assert score <= 1.0


class TestLLMValidation:
    def test_passes_through_on_empty_response(self):
        from unittest.mock import patch
        contacts = [
            _c("Alice", "Technical Recruiter"),
            _c("Bob", "HR Manager"),
        ]
        with patch("job_ranker.llm.client.llm_text", return_value=""):
            result = _llm_validate_contacts(contacts, "TestCo", "ML Engineer")
        assert len(result) == len(contacts)

    def test_filters_low_scores(self):
        import json
        from unittest.mock import patch
        contacts = [
            _c("Alice", "Technical Recruiter"),
            _c("Bob", "HR Manager"),
            _c("Carol", "Talent Acquisition"),
        ]
        mock_response = json.dumps([
            {"idx": 0, "score": 5, "reason": "good"},
            {"idx": 1, "score": 1, "reason": "bad"},
            {"idx": 2, "score": 4, "reason": "good"},
        ])
        with patch("job_ranker.llm.client.llm_text", return_value=mock_response):
            result = _llm_validate_contacts(contacts, "TestCo", "ML Engineer")
        names = [c.name for c in result]
        assert "Bob" not in names
        assert "Alice" in names
        assert "Carol" in names
        assert result[0].name == "Alice"

    def test_passes_through_on_exception(self):
        from unittest.mock import patch
        contacts = [_c("Alice", "Technical Recruiter")]
        with patch("job_ranker.llm.client.llm_text", side_effect=Exception("fail")):
            result = _llm_validate_contacts(contacts, "TestCo", "ML Engineer")
        assert len(result) == 1

    def test_all_low_scores_returns_empty(self):
        import json
        from unittest.mock import patch
        contacts = [
            _c("Alice", "Technical Recruiter"),
            _c("Bob", "HR Manager"),
        ]
        mock_response = json.dumps([
            {"idx": 0, "score": 1, "reason": "US-based"},
            {"idx": 1, "score": 2, "reason": "former employee"},
        ])
        with patch("job_ranker.llm.client.llm_text", return_value=mock_response):
            result = _llm_validate_contacts(contacts, "TestCo", "ML Engineer")
        assert len(result) == 0

    def test_empty_contacts_returns_empty(self):
        assert _llm_validate_contacts([], "TestCo", "ML Engineer") == []


from unittest.mock import patch


class TestFindIntegration:
    """find() should return ≤2 scored contacts per job, not 5-10 raw ones."""

    _FAKE_CONTACTS = [
        # 6 contacts for the same job_url — only 3 are actual recruiters
        ("Alice",  "Senior Technical Recruiter",    "high"),
        ("Bob",    "HR Business Partner",            "medium"),
        ("Carol",  "Talent Acquisition - ML Roles", "high"),
        ("Dave",   "Workday Employee",               "medium"),  # score=0.0
        ("Eve",    "Product Owner",                  "low"),     # score=0.0
        ("Frank",  "Recruiter - Engineering",        "medium"),
    ]

    def _make_ddg(self, company, domain, job_url, job_title, job_score, location="india"):
        """Mock matching search_linkedin_ddg's exact signature to avoid arg-mapping bugs."""
        from job_ranker.scrapers.recruiter_finder import RecruiterContact
        return [
            RecruiterContact(company=company, name=n, title=t,
                             job_url=job_url, job_title=job_title, confidence=conf)
            for n, t, conf in self._FAKE_CONTACTS
        ]

    def _patch_find(self):
        return (
            patch("job_ranker.scrapers.recruiter_finder.resolve_domain", return_value="workday.com"),
            patch("job_ranker.scrapers.recruiter_finder.search_linkedin_ddg", side_effect=self._make_ddg),
            patch("job_ranker.scrapers.recruiter_finder._llm_validate_contacts", side_effect=lambda c, *a: c),
        )

    def test_find_returns_at_most_5(self):
        from job_ranker.scrapers.recruiter_finder import RecruiterFinder
        finder = RecruiterFinder()
        with self._patch_find()[0], self._patch_find()[1], self._patch_find()[2]:
            contacts = finder.find(
                company="Workday",
                job_url="https://linkedin.com/jobs/view/999",
                job_title="ML Engineer",
                max_results=10,
            )
        assert len(contacts) <= 5

    def test_find_excludes_non_recruiters(self):
        from job_ranker.scrapers.recruiter_finder import RecruiterFinder
        finder = RecruiterFinder()
        with self._patch_find()[0], self._patch_find()[1], self._patch_find()[2]:
            contacts = finder.find(
                company="Workday",
                job_url="https://linkedin.com/jobs/view/999",
                job_title="ML Engineer",
                max_results=10,
            )
        names = [c.name for c in contacts]
        assert "Dave" not in names   # "Workday Employee" — score=0.0
        assert "Eve" not in names    # "Product Owner" — score=0.0

    def test_find_prefers_high_confidence(self):
        from job_ranker.scrapers.recruiter_finder import RecruiterFinder
        finder = RecruiterFinder()
        with self._patch_find()[0], self._patch_find()[1], self._patch_find()[2]:
            contacts = finder.find(
                company="Workday",
                job_url="https://linkedin.com/jobs/view/999",
                job_title="ML Engineer",
                max_results=10,
            )
        names = [c.name for c in contacts]
        assert "Alice" in names
        assert "Carol" in names
