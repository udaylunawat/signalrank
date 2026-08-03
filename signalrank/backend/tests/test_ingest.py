import time
from datetime import date

import pandas as pd

import batch.ingest as ingest
from batch.ingest import (
    SearchRequest,
    _fit_storage_fields,
    build_query_plan,
    expand_role_queries,
    normalize_himalayas_job,
    normalize_jobicy_job,
    normalize_jobspy_job,
    normalize_remotive_job,
    scrape_jobspy_jobs,
)


def test_storage_fields_are_bounded_to_database_columns():
    row = _fit_storage_fields(
        {
            "job_url": "https://example.com/job",
            "title": "t" * 501,
            "company": "c" * 256,
            "location": "l" * 300,
            "site": "s" * 101,
            "description": "d" * 1000,
        }
    )

    assert len(row["title"]) == 500
    assert len(row["company"]) == 255
    assert len(row["location"]) == 255
    assert len(row["site"]) == 100
    assert len(row["description"]) == 1000


def test_normalize_remotive_job():
    row = normalize_remotive_job(
        {
            "url": "https://example.com/jobs/1",
            "title": "Senior AI Engineer",
            "company_name": "Example",
            "description": "<p>Build &amp; ship <strong>agents</strong>.</p>",
            "candidate_required_location": "Worldwide",
            "publication_date": "2026-07-13T07:05:10",
        }
    )

    assert row is not None
    assert row["description"] == "Build & ship agents ."
    assert row["site"] == "remotive"
    assert row["date_posted"].year == 2026


def test_normalize_remotive_job_requires_url_and_title():
    assert normalize_remotive_job({"title": "Engineer"}) is None
    assert normalize_remotive_job({"url": "https://example.com"}) is None


def test_normalize_jobspy_job():
    row = normalize_jobspy_job(
        {
            "site": "indeed",
            "job_url": "https://indeed.example/jobs/1",
            "title": "Staff AI Engineer",
            "company": "Example",
            "location": "KA, IN",
            "description": "Build agent platforms",
            "date_posted": date(2026, 7, 15),
        }
    )

    assert row is not None
    assert row["site"] == "indeed"
    assert row["date_posted"].tzinfo is not None


def test_normalize_jobspy_job_requires_url_and_title():
    assert normalize_jobspy_job({"title": "Engineer"}) is None
    assert normalize_jobspy_job({"job_url": "https://example.com"}) is None


def test_role_query_expansion_is_deterministic_and_bounded():
    queries = expand_role_queries(
        ["Senior Agentic Platform Engineer", "MLOps Engineer"], max_queries=5
    )
    assert queries == [
        "Senior Agentic Platform Engineer",
        "Agentic Platform Engineer",
        "MLOps Engineer",
    ]


def test_query_plan_covers_location_lanes_without_boolean_queries():
    plan = build_query_plan(
        ["AI/ML Engineer"],
        locations=["Bangalore", "Remote only"],
        max_queries=4,
    )
    assert [request.location for request in plan] == ["Bengaluru, India"]
    assert all(" OR " not in request.query for request in plan)


def test_empty_roles_do_not_fall_back_to_a_specific_profession():
    assert expand_role_queries([]) == []
    assert build_query_plan([], locations=["Remote"]) == []


def test_normalize_free_source_jobs():
    himalayas = normalize_himalayas_job(
        {
            "applicationLink": "https://example.com/himalayas?utm_source=test",
            "title": "AI Platform Engineer",
            "companyName": "Example",
            "description": "<p>Build agents</p>",
            "locationRestrictions": ["India"],
            "pubDate": 1784041131,
        }
    )
    jobicy = normalize_jobicy_job(
        {
            "url": "https://example.com/jobicy",
            "jobTitle": "LLM Engineer",
            "companyName": "Example",
            "jobDescription": "Ship models",
            "jobGeo": "Remote",
            "pubDate": "2026-07-15T00:00:00Z",
        }
    )
    assert himalayas is not None and himalayas["site"] == "himalayas"
    assert himalayas["job_url"] == "https://example.com/himalayas"
    assert himalayas["date_posted"].year == 2026
    assert jobicy is not None and jobicy["site"] == "jobicy"


def test_jobspy_sources_fail_independently(monkeypatch):
    def fake_scrape_jobs(*, site_name, **kwargs):
        if site_name == ["linkedin"]:
            raise RuntimeError("blocked")
        return pd.DataFrame(
            [
                {
                    "site": "indeed",
                    "job_url": "https://example.com/indeed",
                    "title": "AI Engineer",
                }
            ]
        )

    monkeypatch.setattr(ingest, "scrape_jobs", fake_scrape_jobs)
    rows, reports = scrape_jobspy_jobs(
        [SearchRequest("AI Engineer", "India")], sleep_fn=lambda _: None
    )
    assert len(rows) == 1
    assert [(report.source, report.status) for report in reports] == [
        ("indeed", "success"),
        ("linkedin", "error"),
    ]


def test_jobspy_retries_and_spaces_indeed_queries(monkeypatch):
    attempts: dict[tuple[str, str], int] = {}
    delays: list[float] = []

    def fake_scrape_jobs(*, site_name, search_term, **kwargs):
        key = (site_name[0], search_term)
        attempts[key] = attempts.get(key, 0) + 1
        if key == ("indeed", "AI Engineer") and attempts[key] == 1:
            raise RuntimeError("temporary block")
        return pd.DataFrame(
            [
                {
                    "site": site_name[0],
                    "job_url": f"https://example.com/{site_name[0]}/{search_term}",
                    "title": search_term,
                }
            ]
        )

    monkeypatch.setattr(ingest, "scrape_jobs", fake_scrape_jobs)
    rows, reports = scrape_jobspy_jobs(
        [
            SearchRequest("AI Engineer", "India"),
            SearchRequest("ML Engineer", "India"),
        ],
        sleep_fn=delays.append,
    )
    assert len(rows) == 4
    assert all(report.status == "success" for report in reports)
    assert ingest.JOBSPY_RETRY_BACKOFF in delays
    assert ingest.JOBSPY_INTER_QUERY_DELAY in delays


def test_jobspy_timeout_is_reported_without_blocking_refresh(monkeypatch):
    def fake_scrape_jobs(**kwargs):
        time.sleep(0.05)
        return pd.DataFrame()

    monkeypatch.setattr(ingest, "scrape_jobs", fake_scrape_jobs)
    rows, reports = scrape_jobspy_jobs(
        [SearchRequest("AI Engineer", "India")],
        sleep_fn=lambda _: None,
        max_attempts=1,
        request_timeout_seconds=0.001,
        refresh_timeout_seconds=1,
    )

    assert rows == []
    assert [(report.source, report.status) for report in reports] == [
        ("indeed", "error"),
        ("linkedin", "error"),
    ]
    assert all("exceeded" in (report.error_summary or "") for report in reports)
