# job_ranker/tests/test_config_advisor.py
from unittest.mock import patch

import pandas as pd
import pytest

from job_ranker.llm.config_advisor import (
    ADVISOR_MODEL_POOL,
    build_user_message,
    run_advisor,
    sample_jobs,
)


@pytest.fixture
def ranked_df():
    rows = []
    for i in range(250):
        rows.append({
            "title": f"Role {i}",
            "company": f"Company {i % 30}",
            "final_score": 100 - i * 0.4,
            "description": f"Description for role {i} " * 10,
        })
    return pd.DataFrame(rows)


def test_sample_jobs_top20_always_included(ranked_df):
    sample = sample_jobs(ranked_df, run_id="run-abc")
    top20_titles = set(ranked_df.head(20)["title"])
    sample_titles = set(sample["title"])
    assert top20_titles.issubset(sample_titles)


def test_sample_jobs_total_is_40(ranked_df):
    sample = sample_jobs(ranked_df, run_id="run-abc")
    assert len(sample) == 40


def test_sample_jobs_reproducible(ranked_df):
    s1 = sample_jobs(ranked_df, run_id="run-xyz")
    s2 = sample_jobs(ranked_df, run_id="run-xyz")
    assert list(s1["title"]) == list(s2["title"])


def test_sample_jobs_different_run_id_differs(ranked_df):
    # With 180-row pool and 20 samples, different seeds will always differ
    s1 = sample_jobs(ranked_df, run_id="run-aaa")
    s2 = sample_jobs(ranked_df, run_id="run-bbb")
    # Top-20 titles are identical (both take ranked_df.head(20))
    # The random-20 tail should differ for different run_ids
    assert list(s1["title"][20:]) != list(s2["title"][20:])


def test_build_user_message_contains_resume(ranked_df):
    sample = sample_jobs(ranked_df, run_id="run-abc")
    msg = build_user_message(sample, resume_text="I am an ML engineer with Python skills", config={})
    assert "ML engineer" in msg


def test_build_user_message_contains_job_titles(ranked_df):
    sample = sample_jobs(ranked_df, run_id="run-abc")
    msg = build_user_message(sample, resume_text="resume", config={})
    assert "Role 0" in msg


def test_advisor_model_pool_has_priority_models():
    assert "openrouter/hunter-alpha" in ADVISOR_MODEL_POOL
    assert "openrouter/healer-alpha" in ADVISOR_MODEL_POOL
    assert "nvidia/nemotron-3-super-120b-a12b:free" in ADVISOR_MODEL_POOL
    assert ADVISOR_MODEL_POOL[0] == "openrouter/hunter-alpha"


def test_run_advisor_writes_report(tmp_path, ranked_df):
    # llm_text returns text on first call (hunter-alpha succeeds)
    with patch("job_ranker.llm.config_advisor.llm_text", return_value="## 1. Skills Gap\nAdd PyTorch"):
        run_advisor(
            ranked_df=ranked_df,
            resume_text="I am an engineer",
            run_id="run-test",
            config={},
            reports_dir=tmp_path,
        )
    report = tmp_path / "config_suggestions_run-test.md"
    assert report.exists()
    content = report.read_text()
    assert "Skills Gap" in content
    assert "run-test" in content
    # Model attribution must be present
    assert "openrouter/hunter-alpha" in content


def test_run_advisor_writes_partial_report_on_llm_failure(tmp_path, ranked_df):
    # All models return empty string (all fail) — partial report written
    with patch("job_ranker.llm.config_advisor.llm_text", return_value=""):
        run_advisor(
            ranked_df=ranked_df,
            resume_text="I am an engineer",
            run_id="run-fail",
            config={},
            reports_dir=tmp_path,
        )
    report = tmp_path / "config_suggestions_run-fail.md"
    assert report.exists()
    assert "error" in report.read_text().lower() or "unavailable" in report.read_text().lower()


def test_run_advisor_no_api_key_writes_no_report(tmp_path, ranked_df, monkeypatch):
    # Per spec: missing API key → no report file, no error
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_advisor(
        ranked_df=ranked_df,
        resume_text="I am an engineer",
        run_id="run-nokey",
        config={},
        reports_dir=tmp_path,
    )
    assert result is None
    assert not (tmp_path / "config_suggestions_run-nokey.md").exists()
