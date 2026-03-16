"""
scripts/benchmark.py

Benchmark: job_ranker vs mini_ranker
Runs both systems, filters to Pune/Remote India + ≤15 days,
LLM-scores top-30 from each, writes docs/benchmark-YYYY-MM-DD.md.

Usage:
    uv run python scripts/benchmark.py
    uv run python scripts/benchmark.py --skip-run   # use existing outputs
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import litellm
import pandas as pd
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / "job_ranker" / ".env")
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / f"benchmark-{date.today()}.md"
DEFAULT_MODEL = "openrouter/arcee-ai/trinity-large-preview:free"
FALLBACK_MODEL = "openrouter/arcee-ai/trinity-mini:free"
RESUME_PATH = REPO_ROOT / "job_ranker" / "users" / "example" / "resume.tex"
DUCKDB_PATH = REPO_ROOT / "job_ranker" / "duckdb"
DAYS_WINDOW = 15
BATCH_SIZE = 20  # jobs per LLM call

PUNE_REMOTE_PATTERNS = [
    "pune", "pun",
    "maharashtra",
    "work from home", "wfh",
]

LOCATION_REJECT = [
    "bengaluru", "bangalore", "chennai", "hyderabad",
    "delhi", "mumbai", "kolkata", "noida", "gurugram",
    "new york", "london", "san francisco", "singapore",
    "austin", "seattle", "toronto",
]


# ── helpers ────────────────────────────────────────────────────────────────────

def clean_latex(text: str) -> str:
    """Strip LaTeX markup, return plain text."""
    text = re.sub(r"%.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}\\~^&$#_]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalise_row(row: dict, system: str) -> dict:
    """Normalise a raw row from either system to common schema."""
    if system == "mini_ranker":
        url = row.get("job_url", "") or ""
        score = float(row.get("final_score", 0) or 0)
    else:  # job_ranker
        url = row.get("url", "") or row.get("job_url", "") or ""
        score = float(row.get("system_score", 0) or row.get("final_score", 0) or 0)

    desc = str(row.get("description", "") or "")[:300]
    return {
        "title": str(row.get("title", "") or "").strip(),
        "company": str(row.get("company", "") or "").strip(),
        "location": str(row.get("location", "") or "").strip(),
        "date_posted": row.get("date_posted"),
        "url": url,
        "system_score": score,
        "description": desc,
    }


def is_pune_or_remote(location: str) -> bool:
    """Return True if location matches Pune or Remote India."""
    loc = location.lower()
    # "remote" + any India signal
    if "remote" in loc:
        if any(ind in loc for ind in ["india", "in", "pune", "maharashtra", "bengaluru",
                                       "mumbai", "hyderabad", "chennai", "delhi"]):
            return True
        # bare "remote" with no country — accept tentatively
        if not any(foreign in loc for foreign in ["usa", "uk", "us,", "canada",
                                                    "germany", "singapore", "australia"]):
            return True
    for pat in PUNE_REMOTE_PATTERNS:
        if pat in loc:
            return True
    return False


def dedup_key(title: str, company: str) -> tuple[str, str]:
    """Normalised (title, company) tuple for cross-system deduplication."""
    return (title.lower().strip(), company.lower().strip())


DUCKDB_SQL = """
SELECT
    rr.job_url                        AS url,
    rr.final_score                    AS system_score,
    rr.payload                        AS payload
FROM run_results rr
WHERE rr.run_id = (
    SELECT run_id FROM runs
    WHERE status = 'success'
    ORDER BY finished_at DESC
    LIMIT 1
)
  AND TRY_CAST(rr.payload->>'date_posted' AS DATE)
        >= CURRENT_DATE - INTERVAL '15' DAY
ORDER BY rr.final_score DESC
LIMIT 100
"""


def load_job_ranker_results(db_path: Path) -> list[dict]:
    """Query DuckDB for top results from the latest successful run."""
    try:
        with duckdb.connect(str(db_path), read_only=True) as con:
            rows = con.execute(DUCKDB_SQL).fetchall()
        result = []
        for url, score, payload in rows:
            if isinstance(payload, str):
                payload = json.loads(payload)
            elif not isinstance(payload, dict):
                payload = {}
            result.append(normalise_row({
                "url": url or "",
                "system_score": score or 0,
                "title": payload.get("title", "") or "",
                "company": payload.get("company", "") or "",
                "location": payload.get("location", "") or "",
                "date_posted": payload.get("date_posted"),
                "description": payload.get("description", "") or "",
            }, system="job_ranker"))
        return result
    except Exception as e:
        print(f"[warn] DuckDB load failed: {e}", file=sys.stderr)
        return []


def load_mini_ranker_results(outputs_dir: Path) -> list[dict]:
    """Load the most recent mini_ranker CSV from outputs/."""
    csvs = sorted(outputs_dir.glob("mini_ranked_*.csv"), reverse=True)
    if not csvs:
        print(f"[warn] No mini_ranked_*.csv found in {outputs_dir}", file=sys.stderr)
        return []
    df = pd.read_csv(csvs[0])
    df = df.sort_values("final_score", ascending=False)
    rows = []
    for _, row in df.head(100).iterrows():
        rows.append(normalise_row(row.to_dict(), system="mini_ranker"))
    return rows
