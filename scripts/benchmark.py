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


# ── filter_jobs ────────────────────────────────────────────────────────────────

def filter_jobs(
    jobs: list[dict],
    today: date | None = None,
    return_relaxed: bool = False,
) -> list[dict] | tuple[list[dict], bool]:
    """Filter to Pune/Remote India + within DAYS_WINDOW days."""
    if today is None:
        today = date.today()
    cutoff = today - timedelta(days=DAYS_WINDOW)

    def _parse_date(val) -> date | None:
        if not val or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return pd.to_datetime(str(val), utc=True).date()
        except Exception:
            return None

    def _recent(j: dict) -> bool:
        d = _parse_date(j.get("date_posted"))
        return d is not None and d >= cutoff

    recent = [j for j in jobs if _recent(j)]
    preferred = [j for j in recent if is_pune_or_remote(j.get("location", ""))]

    relaxed = False
    if 0 < len(preferred) < 10:
        preferred = [
            j for j in recent
            if not any(f in j.get("location", "").lower()
                       for f in ["usa", "uk,", "canada", "germany",
                                 "singapore", "australia", "new york",
                                 "london", "san francisco"])
        ]
        relaxed = True

    return (preferred, relaxed) if return_relaxed else preferred


# ── LLM scoring ────────────────────────────────────────────────────────────────

SCORE_PROMPT_TEMPLATE = """You are evaluating job postings for a Senior AI Platform / MLOps / LLMOps engineer.

CANDIDATE PROFILE (resume excerpt):
{resume}

SCORING RUBRIC (total 100 points):
- role_match (0-40): Alignment with MLOps/LLMOps/AI Platform/RAG/agentic systems from title+description. Cap at 20 if description is empty.
- seniority_fit (0-20): Senior/Staff/Principal=20; mid-level=12; junior/manager/trainee=0-5
- company_quality (0-20): AI-native/product=20; MNC R&D=15; IT services/body-shop=<=5
- location_ok (0-10): Pune or explicit Remote India=10; other India city=5; abroad=0
- recency (0-10): <=7 days old=10; 8-15 days=7; >15 days=0

JOBS TO SCORE:
{jobs_json}

Return ONLY valid JSON (no markdown, no prose):
{{"jobs": [{{"idx": 0, "role_match": <int>, "seniority_fit": <int>, "company_quality": <int>, "location_ok": <int>, "recency": <int>, "llm_score": <sum>, "verdict": "<one sentence>"}}]}}
"""


def _extract_json(raw: str) -> dict | None:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(raw[start:], start):
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None


def llm_score_batch(
    jobs: list[dict],
    resume_text: str,
    model: str,
    api_key: str,
) -> list[dict]:
    """Score a batch of jobs via LLM. Returns list with llm_score added (None on failure)."""
    os.environ["OPENROUTER_API_KEY"] = api_key

    jobs_payload = [
        {"idx": i, "title": j["title"], "company": j["company"],
         "location": j["location"], "date_posted": str(j.get("date_posted", "")),
         "description": j.get("description", "")[:300]}
        for i, j in enumerate(jobs)
    ]
    prompt = SCORE_PROMPT_TEMPLATE.format(
        resume=resume_text[:2000],
        jobs_json=json.dumps(jobs_payload, ensure_ascii=False),
    )

    def _call(m: str):
        return litellm.completion(
            model=m,
            messages=[{"role": "user", "content": prompt}],
        )

    try:
        response = _call(model)
    except (litellm.exceptions.RateLimitError, litellm.exceptions.NotFoundError):
        print(f"[warn] {model} rate-limited, falling back to {FALLBACK_MODEL}", file=sys.stderr)
        try:
            response = _call(FALLBACK_MODEL)
        except Exception as e:
            print(f"[warn] Fallback also failed: {e}", file=sys.stderr)
            return [dict(j, llm_score=None, verdict="scoring failed",
                         role_match=None, seniority_fit=None,
                         company_quality=None, location_ok=None, recency=None)
                    for j in jobs]

    raw = response.choices[0].message.content or ""
    data = _extract_json(raw)
    scored_map: dict[int, dict] = {}
    if data:
        for item in data.get("jobs", []):
            scored_map[item["idx"]] = item

    result = []
    for i, job in enumerate(jobs):
        scores = scored_map.get(i, {})
        result.append(dict(
            job,
            llm_score=scores.get("llm_score"),
            verdict=scores.get("verdict", ""),
            role_match=scores.get("role_match"),
            seniority_fit=scores.get("seniority_fit"),
            company_quality=scores.get("company_quality"),
            location_ok=scores.get("location_ok"),
            recency=scores.get("recency"),
        ))
    return result


def score_all(
    jobs: list[dict],
    resume_text: str,
    model: str,
    api_key: str,
) -> list[dict]:
    """Score all jobs in batches of BATCH_SIZE."""
    scored = []
    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i:i + BATCH_SIZE]
        print(f"  [LLM] scoring jobs {i+1}-{i+len(batch)} ...", file=sys.stderr)
        scored.extend(llm_score_batch(batch, resume_text, model, api_key))
        if i + BATCH_SIZE < len(jobs):
            time.sleep(2)
    return scored
