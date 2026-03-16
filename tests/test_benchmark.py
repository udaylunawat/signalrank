# tests/test_benchmark.py
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import litellm
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from benchmark import (
    DEFAULT_MODEL,
    build_report,
    clean_latex,
    dedup_key,
    filter_jobs,
    is_pune_or_remote,
    llm_score_batch,
    load_job_ranker_results,
    load_mini_ranker_results,
    normalise_row,
    run_mini_ranker,
)


# --- clean_latex ---
def test_clean_latex_strips_commands():
    tex = r"\textbf{Senior MLOps Engineer} with \emph{7 years}"
    result = clean_latex(tex)
    assert "Senior MLOps Engineer" in result
    assert r"\textbf" not in result


def test_clean_latex_removes_comments():
    tex = "Python % this is a comment\nKubernetes"
    result = clean_latex(tex)
    assert "Kubernetes" in result
    assert "comment" not in result


# --- normalise_row ---
def test_normalise_row_mini_ranker():
    row = {
        "title": "ML Engineer",
        "company": "Acme",
        "location": "Pune",
        "date_posted": "2026-03-10",
        "job_url": "https://example.com/1",
        "final_score": 72.5,
        "description": "Build ML pipelines. " * 50,
    }
    out = normalise_row(row, system="mini_ranker")
    assert out["url"] == "https://example.com/1"
    assert out["system_score"] == 72.5
    assert len(out["description"]) <= 300


def test_normalise_row_job_ranker():
    row = {
        "title": "MLOps Lead",
        "company": "Databricks",
        "location": "Remote India",
        "date_posted": "2026-03-12",
        "url": "https://example.com/2",
        "system_score": 88.0,
        "description": "Own the ML platform.",
    }
    out = normalise_row(row, system="job_ranker")
    assert out["title"] == "MLOps Lead"
    assert out["system_score"] == 88.0


# --- is_pune_or_remote ---
@pytest.mark.parametrize(
    "loc,expected",
    [
        ("Pune, Maharashtra", True),
        ("Remote India", True),
        ("Work from home - India", True),
        ("Bengaluru, Karnataka", False),
        ("New York, USA", False),
        ("Maharashtra", True),
        ("", False),
    ],
)
def test_is_pune_or_remote(loc, expected):
    assert is_pune_or_remote(loc) == expected


# --- dedup_key ---
def test_dedup_key_normalises():
    assert dedup_key("Senior MLOps Engineer", "  Databricks ") == (
        "senior mlops engineer",
        "databricks",
    )


def test_dedup_key_strips_whitespace():
    a = dedup_key("ML Platform Engineer", "Nvidia")
    b = dedup_key("  ML Platform Engineer  ", "  NVIDIA  ")
    assert a == b


# --- load_job_ranker_results ---
def test_load_job_ranker_results_returns_normalised():
    mock_rows = [
        (
            "https://ex.com/1",
            85.0,
            json.dumps(
                {
                    "title": "MLOps Engineer",
                    "company": "Databricks",
                    "location": "Pune",
                    "date_posted": "2026-03-10",
                    "description": "Build ML pipelines.",
                }
            ),
        ),
    ]
    with patch("benchmark.duckdb") as mock_db:
        mock_con = MagicMock()
        mock_db.connect.return_value.__enter__ = lambda s: mock_con
        mock_db.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_con.execute.return_value.fetchall.return_value = mock_rows
        rows = load_job_ranker_results(Path("/fake/duckdb"))
    assert len(rows) == 1
    assert rows[0]["title"] == "MLOps Engineer"
    assert rows[0]["system_score"] == 85.0
    assert rows[0]["url"] == "https://ex.com/1"


def test_load_job_ranker_results_empty_returns_empty():
    with patch("benchmark.duckdb") as mock_db:
        mock_con = MagicMock()
        mock_db.connect.return_value.__enter__ = lambda s: mock_con
        mock_db.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_con.execute.return_value.fetchall.return_value = []
        rows = load_job_ranker_results(Path("/fake/duckdb"))
    assert rows == []


# --- load_mini_ranker_results ---
def test_load_mini_ranker_results_reads_csv(tmp_path):
    csv = tmp_path / "mini_ranked_20260317_120000.csv"
    csv.write_text(
        "title,company,location,date_posted,job_url,final_score,description\n"
        "MLOps Lead,Nvidia,Pune,2026-03-10,https://ex.com/3,91.0,Great role\n"
    )
    rows = load_mini_ranker_results(tmp_path)
    assert len(rows) == 1
    assert rows[0]["title"] == "MLOps Lead"
    assert rows[0]["system_score"] == 91.0


def test_load_mini_ranker_results_picks_latest(tmp_path):
    (tmp_path / "mini_ranked_20260317_100000.csv").write_text(
        "title,company,location,date_posted,job_url,final_score,description\nOld,Co,Pune,2026-03-10,u,50.0,d\n"
    )
    (tmp_path / "mini_ranked_20260317_120000.csv").write_text(
        "title,company,location,date_posted,job_url,final_score,description\nNew,Co,Pune,2026-03-10,u,80.0,d\n"
    )
    rows = load_mini_ranker_results(tmp_path)
    assert rows[0]["title"] == "New"




def _make_job(location="Pune", date_posted="2026-03-10", **kw):
    return {
        "title": "ML Eng",
        "company": "Co",
        "location": location,
        "date_posted": date_posted,
        "url": "u",
        "system_score": 50.0,
        "description": "d",
        **kw,
    }


def test_filter_jobs_keeps_pune_recent():
    jobs = [_make_job(location="Pune", date_posted="2026-03-10")]
    result = filter_jobs(jobs, today=date(2026, 3, 17))
    assert len(result) == 1


def test_filter_jobs_removes_old():
    jobs = [_make_job(date_posted="2026-02-01")]
    result = filter_jobs(jobs, today=date(2026, 3, 17))
    assert len(result) == 0


def test_filter_jobs_removes_bengaluru():
    jobs = [_make_job(location="Bengaluru, Karnataka")]
    result = filter_jobs(jobs, today=date(2026, 3, 17))
    assert len(result) == 0


def test_filter_jobs_keeps_remote_india():
    jobs = [_make_job(location="Remote, India", date_posted="2026-03-15")]
    result = filter_jobs(jobs, today=date(2026, 3, 17))
    assert len(result) == 1


def test_filter_jobs_excludes_null_date():
    jobs = [_make_job(date_posted=None)]
    result = filter_jobs(jobs, today=date(2026, 3, 17))
    assert len(result) == 0


def test_filter_jobs_relaxes_to_india_if_few(monkeypatch):
    # Only 5 Pune/remote jobs → relax to all India
    jobs = [_make_job(location="Pune")] * 5 + [_make_job(location="Bengaluru")] * 10
    result, relaxed = filter_jobs(jobs, today=date(2026, 3, 17), return_relaxed=True)
    assert relaxed is True
    assert len(result) == 15



def _make_completion(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_llm_score_batch_happy_path():
    jobs = [
        {
            "title": "MLOps Engineer",
            "company": "Nvidia",
            "location": "Pune",
            "date_posted": "2026-03-10",
            "description": "Build ML infra.",
        }
    ]
    response_json = json.dumps(
        {
            "jobs": [
                {
                    "idx": 0,
                    "role_match": 35,
                    "seniority_fit": 18,
                    "company_quality": 18,
                    "location_ok": 10,
                    "recency": 7,
                    "llm_score": 88,
                    "verdict": "Strong fit.",
                }
            ]
        }
    )
    with patch("benchmark.litellm.completion") as mock_llm:
        mock_llm.return_value = _make_completion(response_json)
        results = llm_score_batch(
            jobs, resume_text="MLOps engineer 7YOE", model=DEFAULT_MODEL, api_key="fake"
        )
    assert len(results) == 1
    assert results[0]["llm_score"] == 88
    assert results[0]["verdict"] == "Strong fit."


def test_llm_score_batch_falls_back_on_rate_limit():
    jobs = [
        {
            "title": "MLOps Engineer",
            "company": "Nvidia",
            "location": "Pune",
            "date_posted": "2026-03-10",
            "description": "Build ML infra.",
        }
    ]
    ok_resp = _make_completion(
        json.dumps(
            {
                "jobs": [
                    {
                        "idx": 0,
                        "role_match": 30,
                        "seniority_fit": 15,
                        "company_quality": 15,
                        "location_ok": 10,
                        "recency": 7,
                        "llm_score": 77,
                        "verdict": "Good.",
                    }
                ]
            }
        )
    )
    with patch("benchmark.litellm.completion") as mock_llm:
        mock_llm.side_effect = [
            litellm.exceptions.RateLimitError("x", llm_provider="x", model="x"),
            ok_resp,
        ]
        results = llm_score_batch(
            jobs, resume_text="MLOps engineer", model=DEFAULT_MODEL, api_key="fake"
        )
    assert results[0]["llm_score"] == 77


def test_llm_score_batch_json_parse_failure_returns_null():
    jobs = [
        {
            "title": "ML Eng",
            "company": "Co",
            "location": "Pune",
            "date_posted": "2026-03-10",
            "description": "d",
        }
    ]
    with patch("benchmark.litellm.completion") as mock_llm:
        mock_llm.return_value = _make_completion("Sorry, I cannot score these jobs.")
        results = llm_score_batch(
            jobs, resume_text="x", model=DEFAULT_MODEL, api_key="fake"
        )
    assert results[0]["llm_score"] is None




def _scored_job(title, company, loc, score, sys_score, url="https://ex.com"):
    return {
        "title": title,
        "company": company,
        "location": loc,
        "date_posted": "2026-03-15",
        "url": url,
        "system_score": sys_score,
        "description": "d",
        "llm_score": score,
        "verdict": "Good fit.",
        "role_match": score // 4,
        "seniority_fit": 15,
        "company_quality": 15,
        "location_ok": 10,
        "recency": 7,
    }


def test_build_report_contains_headers():
    jr = [_scored_job("MLOps Eng", "Nvidia", "Pune", 88, 92.0)]
    mr = [_scored_job("ML Platform Eng", "Salesforce", "Remote India", 82, 85.0)]
    report = build_report(jr, mr, relaxed_a=False, relaxed_b=False)
    assert "# Job Search Benchmark" in report
    assert "job_ranker" in report
    assert "mini_ranker" in report
    assert "TL;DR" in report
    assert "Head-to-Head" in report
    assert "Overlap" in report


def test_build_report_shows_overlap():
    job = _scored_job("MLOps Eng", "Nvidia", "Pune", 88, 92.0)
    report = build_report([job], [job], relaxed_a=False, relaxed_b=False)
    assert "Overlap" in report
    assert "Nvidia" in report


def test_build_report_shows_relaxed_warning():
    jr = [_scored_job("MLOps Eng", "Co", "Bengaluru", 60, 70.0)]
    report = build_report(jr, [], relaxed_a=True, relaxed_b=False)
    assert "⚠️" in report


def test_run_mini_ranker_creates_config_and_calls_subprocess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "mini_ranked_20260317_120000.csv").write_text(
        "title,company,location,date_posted,job_url,final_score,description\n"
        "MLOps Eng,Nvidia,Pune,2026-03-15,https://ex.com,90.0,Great\n"
    )
    with patch("benchmark.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        rows = run_mini_ranker(
            resume_path=Path("/fake/resume.tex"),
            repo_root=tmp_path,
            hours_old=360,
        )
    assert mock_run.called
    assert len(rows) == 1
    assert rows[0]["title"] == "MLOps Eng"
    # config.yaml should be cleaned up
    assert not (tmp_path / "config.yaml").exists()
