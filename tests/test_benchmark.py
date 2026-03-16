# tests/test_benchmark.py
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from benchmark import clean_latex, normalise_row, is_pune_or_remote, dedup_key

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
        "title": "ML Engineer", "company": "Acme",
        "location": "Pune", "date_posted": "2026-03-10",
        "job_url": "https://example.com/1", "final_score": 72.5,
        "description": "Build ML pipelines. " * 50,
    }
    out = normalise_row(row, system="mini_ranker")
    assert out["url"] == "https://example.com/1"
    assert out["system_score"] == 72.5
    assert len(out["description"]) <= 300

def test_normalise_row_job_ranker():
    row = {
        "title": "MLOps Lead", "company": "Databricks",
        "location": "Remote India", "date_posted": "2026-03-12",
        "url": "https://example.com/2", "system_score": 88.0,
        "description": "Own the ML platform.",
    }
    out = normalise_row(row, system="job_ranker")
    assert out["title"] == "MLOps Lead"
    assert out["system_score"] == 88.0

# --- is_pune_or_remote ---
@pytest.mark.parametrize("loc,expected", [
    ("Pune, Maharashtra", True),
    ("Remote India", True),
    ("Work from home - India", True),
    ("Bengaluru, Karnataka", False),
    ("New York, USA", False),
    ("Maharashtra", True),
    ("", False),
])
def test_is_pune_or_remote(loc, expected):
    assert is_pune_or_remote(loc) == expected

# --- dedup_key ---
def test_dedup_key_normalises():
    assert dedup_key("Senior MLOps Engineer", "  Databricks ") == ("senior mlops engineer", "databricks")

def test_dedup_key_strips_whitespace():
    a = dedup_key("ML Platform Engineer", "Nvidia")
    b = dedup_key("  ML Platform Engineer  ", "  NVIDIA  ")
    assert a == b

from benchmark import load_job_ranker_results, load_mini_ranker_results
import duckdb

# --- load_job_ranker_results ---
def test_load_job_ranker_results_returns_normalised():
    mock_rows = [
        ("https://ex.com/1", 85.0, json.dumps({
            "title": "MLOps Engineer", "company": "Databricks",
            "location": "Pune", "date_posted": "2026-03-10",
            "description": "Build ML pipelines.",
        })),
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
