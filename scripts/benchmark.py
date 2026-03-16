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


# ── build_report ───────────────────────────────────────────────────────────────

def _fmt_date(val) -> str:
    if not val:
        return ""
    try:
        return str(pd.to_datetime(str(val)).date())
    except Exception:
        return str(val)


def build_report(
    job_ranker_jobs: list[dict],
    mini_ranker_jobs: list[dict],
    relaxed_a: bool = False,
    relaxed_b: bool = False,
) -> str:
    today = date.today()
    lines = [f"# Job Search Benchmark — {today}", ""]
    lines += ["**Systems:** job_ranker (A) vs mini_ranker (B)",
              "**Filter:** Pune or Remote India · last 15 days",
              "**Scorer:** LLM (arcee-ai/trinity, 5-dimension rubric)", ""]

    avg_a = (sum(j["llm_score"] for j in job_ranker_jobs if j.get("llm_score")) /
             max(1, sum(1 for j in job_ranker_jobs if j.get("llm_score"))))
    avg_b = (sum(j["llm_score"] for j in mini_ranker_jobs if j.get("llm_score")) /
             max(1, sum(1 for j in mini_ranker_jobs if j.get("llm_score"))))
    winner = "job_ranker" if avg_a >= avg_b else "mini_ranker"
    lines += [
        "## TL;DR Verdict", "",
        f"**Winner: {winner}** (avg LLM score: job_ranker={avg_a:.1f}, mini_ranker={avg_b:.1f}). "
        f"job_ranker covers more sources (RapidAPI + Indeed + LinkedIn + Google Jobs) but is slower. "
        f"mini_ranker is faster and self-contained but limited to Indeed + LinkedIn.", "",
    ]

    def _table(jobs: list[dict], label: str, relaxed: bool) -> list[str]:
        note = " ⚠️ *location filter relaxed to all-India (< 10 Pune/remote results)*" if relaxed else ""
        out = [f"## System: {label} — Top {len(jobs)}{note}", ""]
        out += ["| # | LLM Score | Title | Company | Location | Posted | Sys Score | URL |",
                "|---|-----------|-------|---------|----------|--------|-----------|-----|"]
        sorted_jobs = sorted(jobs, key=lambda j: j.get("llm_score") or 0, reverse=True)
        for i, j in enumerate(sorted_jobs, 1):
            score = j.get("llm_score", "—")
            score_str = f"**{score}**" if isinstance(score, int) and score >= 70 else str(score)
            url = j.get("url", "")
            url_md = f"[link]({url})" if url else "—"
            out.append(
                f"| {i} | {score_str} | {j['title']} | {j['company']} | "
                f"{j['location']} | {_fmt_date(j.get('date_posted'))} | "
                f"{j['system_score']:.1f} | {url_md} |"
            )
        out.append("")
        return out

    lines += _table(job_ranker_jobs, "job_ranker (A)", relaxed_a)
    lines += _table(mini_ranker_jobs, "mini_ranker (B)", relaxed_b)

    def _count(jobs, threshold): return sum(1 for j in jobs if (j.get("llm_score") or 0) >= threshold)
    def _loc_count(jobs, pat): return sum(1 for j in jobs if pat in j.get("location", "").lower())

    lines += [
        "## Head-to-Head Comparison", "",
        "| Metric | job_ranker | mini_ranker |",
        "|--------|-----------|-------------|",
        f"| Avg LLM score | {avg_a:.1f} | {avg_b:.1f} |",
        f"| Jobs ≥70 | {_count(job_ranker_jobs, 70)} | {_count(mini_ranker_jobs, 70)} |",
        f"| Jobs ≥50 | {_count(job_ranker_jobs, 50)} | {_count(mini_ranker_jobs, 50)} |",
        f"| Pune jobs | {_loc_count(job_ranker_jobs, 'pune')} | {_loc_count(mini_ranker_jobs, 'pune')} |",
        f"| Remote India jobs | {_loc_count(job_ranker_jobs, 'remote')} | {_loc_count(mini_ranker_jobs, 'remote')} |",
        f"| Total returned | {len(job_ranker_jobs)} | {len(mini_ranker_jobs)} |",
        "",
    ]

    keys_a = {dedup_key(j["title"], j["company"]): j for j in job_ranker_jobs}
    keys_b = {dedup_key(j["title"], j["company"]): j for j in mini_ranker_jobs}
    overlap_keys = set(keys_a) & set(keys_b)
    only_a = {k: v for k, v in keys_a.items() if k not in overlap_keys}
    only_b = {k: v for k, v in keys_b.items() if k not in overlap_keys}

    lines += [f"## Overlap — {len(overlap_keys)} jobs found by both systems", ""]
    if overlap_keys:
        lines += ["| Title | Company | A LLM Score | B LLM Score |",
                  "|-------|---------|-------------|-------------|"]
        for k in overlap_keys:
            ja, jb = keys_a[k], keys_b[k]
            lines.append(f"| {ja['title']} | {ja['company']} | {ja.get('llm_score','—')} | {jb.get('llm_score','—')} |")
    lines.append("")

    def _unique_table(jobs_dict: dict, label: str) -> list[str]:
        out = [f"## Unique to {label} — {len(jobs_dict)} jobs", ""]
        if jobs_dict:
            out += ["| LLM Score | Title | Company | Location | URL |",
                    "|-----------|-------|---------|----------|-----|"]
            for j in sorted(jobs_dict.values(), key=lambda x: x.get("llm_score") or 0, reverse=True):
                url_md = f"[link]({j['url']})" if j.get("url") else "—"
                out.append(f"| {j.get('llm_score','—')} | {j['title']} | {j['company']} | {j['location']} | {url_md} |")
        out.append("")
        return out

    lines += _unique_table(only_a, "job_ranker")
    lines += _unique_table(only_b, "mini_ranker")

    return "\n".join(lines)


# ── run_mini_ranker / run_job_ranker / main ────────────────────────────────────

MINI_RANKER_CONFIG = {
    "resume_file": "",
    "search_queries": [
        "ai platform engineer", "ml platform engineer", "mlops",
        "llmops", "genai", "agentic systems", "ai infrastructure",
    ],
    "country": "India",
    "hours_old": 360,
    "preferred_locations": ["pune", "remote", "maharashtra"],
    "top_companies": [
        "databricks", "snowflake", "nvidia", "openai", "anthropic",
        "microsoft", "google", "meta", "salesforce", "qualcomm",
        "hugging face", "atlassian", "servicenow", "intuit", "razorpay",
        "phonepe", "meesho", "groww", "zycus", "informatica",
    ],
    "avoid_companies": [
        "wipro", "infosys", "tcs", "hcl", "tech mahindra",
        "cognizant", "capgemini", "accenture", "fractal",
    ],
}


def run_mini_ranker(
    resume_path: Path,
    repo_root: Path,
    hours_old: int = 360,
    skip_run: bool = False,
) -> list[dict]:
    """Run mini_ranker subprocess, return normalised rows."""
    outputs_dir = repo_root / "outputs"
    config_path = repo_root / "config.yaml"

    if not skip_run:
        cfg = dict(MINI_RANKER_CONFIG)
        cfg["resume_file"] = str(resume_path)
        cfg["hours_old"] = hours_old
        config_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
        try:
            print("[run] mini_ranker ...", file=sys.stderr)
            result = subprocess.run(
                ["uv", "run", "python", "mini_ranker.py", "--hours-old", str(hours_old)],
                cwd=str(repo_root),
                capture_output=False,
                text=True,
            )
            if result.returncode != 0:
                print(f"[warn] mini_ranker exited with code {result.returncode}", file=sys.stderr)
        finally:
            if config_path.exists():
                config_path.unlink()

    return load_mini_ranker_results(outputs_dir)


def run_job_ranker(repo_root: Path, skip_run: bool = False) -> list[dict]:
    """Run job_ranker entrypoint subprocess, then load from DuckDB."""
    db_path = repo_root / "job_ranker" / "duckdb"

    if not skip_run:
        print("[run] job_ranker ...", file=sys.stderr)
        subprocess.run(
            ["uv", "run", "python", "-m", "job_ranker.entrypoint", "run",
             "--user", "example", "--hours-old", "360",
             "--search", "mlops|llmops|ai platform engineer|ml platform engineer"],
            cwd=str(repo_root),
            capture_output=False,
            text=True,
        )

    return load_job_ranker_results(db_path)


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Benchmark job_ranker vs mini_ranker")
    parser.add_argument("--skip-run", action="store_true",
                        help="Skip subprocess runs, use existing outputs")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    resume_text = ""
    if RESUME_PATH.exists():
        resume_text = clean_latex(RESUME_PATH.read_text(encoding="utf-8", errors="ignore"))[:2000]
    else:
        print(f"[warn] Resume not found at {RESUME_PATH}", file=sys.stderr)

    print("[benchmark] Running job_ranker ...", file=sys.stderr)
    jr_raw = run_job_ranker(REPO_ROOT, skip_run=args.skip_run)
    print(f"  → {len(jr_raw)} rows from job_ranker", file=sys.stderr)

    print("[benchmark] Running mini_ranker ...", file=sys.stderr)
    mr_raw = run_mini_ranker(RESUME_PATH, REPO_ROOT, skip_run=args.skip_run)
    print(f"  → {len(mr_raw)} rows from mini_ranker", file=sys.stderr)

    jr_filtered, relaxed_a = filter_jobs(jr_raw, return_relaxed=True)
    mr_filtered, relaxed_b = filter_jobs(mr_raw, return_relaxed=True)
    jr_top30 = sorted(jr_filtered, key=lambda j: j["system_score"], reverse=True)[:30]
    mr_top30 = sorted(mr_filtered, key=lambda j: j["system_score"], reverse=True)[:30]
    print(f"[benchmark] After filter: job_ranker={len(jr_top30)}, mini_ranker={len(mr_top30)}", file=sys.stderr)

    print("[benchmark] Scoring job_ranker results ...", file=sys.stderr)
    jr_scored = score_all(jr_top30, resume_text, args.model, api_key)
    print("[benchmark] Scoring mini_ranker results ...", file=sys.stderr)
    mr_scored = score_all(mr_top30, resume_text, args.model, api_key)

    report = build_report(jr_scored, mr_scored, relaxed_a=relaxed_a, relaxed_b=relaxed_b)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
