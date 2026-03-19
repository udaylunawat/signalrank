"""
scripts/find_roles.py

Phase 2: For each company in a companies YAML, run DDG searches directly,
then call LLM once per company to extract structured roles from raw results.

No tool-use loop — DDG is called in Python, LLM only does extraction.

Usage:
    uv run python scripts/find_roles.py
    uv run python scripts/find_roles.py --companies docs/companies-2026-03-16.yaml
    uv run python scripts/find_roles.py --model openrouter/qwen/qwen3-4b:free
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import litellm
import yaml
from ddgs import DDGS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── constants ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPANIES = REPO_ROOT / "docs" / f"companies-{date.today()}.yaml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs"
# mistral-small supports tool use and follows JSON instructions well
DEFAULT_MODEL = "openrouter/arcee-ai/trinity-large-preview:free"
FALLBACK_MODEL = "openrouter/arcee-ai/trinity-mini:free"
MAX_SEARCH_RESULTS = 5
DDG_DELAY = 1.5  # seconds between DDG queries to avoid rate limiting

# Companies to skip (already employed there or confirmed poor fit)
SKIP_COMPANIES = {"fractal analytics", "fractal"}

# Pure IT services body-shops — unlikely to pay 50+ LPA for platform roles
SKIP_TIER2_SERVICES = {
    "tcs", "tata consultancy services",
    "infosys",
    "wipro",
    "cognizant",
    "tech mahindra",
    "accenture",
    "hcl", "hcl technologies",
    "capgemini",
    "mphasis",
    "hexaware",
    "sasken technologies", "sasken",
}


# ── DDG search (direct, no LLM) ───────────────────────────────────────────────

def ddg_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return [{"title": "Search failed", "href": "", "body": str(e)}]


def search_company_ddg(company: dict) -> list[dict]:
    """Run 3 DDG queries for a company. Returns combined raw search results."""
    name = company["name"]
    queries = [
        f"{name} MLOps LLMOps AI platform engineer jobs India 2026",
        f"{name} machine learning platform engineer careers India",
        f"site:linkedin.com/jobs {name} MLOps platform engineer India",
    ]
    results = []
    for q in queries:
        hits = ddg_search(q)
        results.extend(hits)
        time.sleep(DDG_DELAY)
    return results


# ── LLM extraction (one call per company) ─────────────────────────────────────

def extract_json(raw: str) -> dict | None:
    """Extract first JSON object from a string, robust to surrounding prose."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def build_extraction_prompt(company: dict, search_results: list[dict]) -> str:
    name = company["name"]
    results_text = json.dumps(search_results, ensure_ascii=False)
    return f"""You are extracting structured job data from web search results.

[CANDIDATE PROFILE]
- Role: Senior AI Platform Engineer / MLOps / LLMOps
- Experience: ~7 years
- Stack: GCP, Kubernetes, LangGraph, FastAPI, MLflow, Python, CI/CD, LLMOps, RAG pipelines
- Target salary: 50+ LPA (Indian rupees)
- Location: Pune (office) OR Remote India

[COMPANY]
{name}

[RAW SEARCH RESULTS]
{results_text}

[TASK]
From the search results above, extract any REAL open job postings at {name} that match the candidate profile.
Only extract roles that have a real URL in the search results. Do not fabricate.

Return ONLY valid JSON (no markdown, no prose) with one key "roles" (array, may be empty).
Each role:
  company      (string)
  title        (string — exact job title)
  url          (string — direct job URL from search results)
  location     (string — "Pune", "Remote India", "Bengaluru", etc.)
  salary_lpa   (string "min-max" or null)
  match_reason (string — one sentence)
  source       (string — "linkedin", "careers_page", or "other")
"""


def llm_extract_roles(company: dict, search_results: list[dict], model: str, api_key: str) -> list[dict]:
    os.environ["OPENROUTER_API_KEY"] = api_key
    prompt = build_extraction_prompt(company, search_results)
    messages = [{"role": "user", "content": prompt}]

    try:
        response = litellm.completion(model=model, messages=messages)
    except (litellm.exceptions.RateLimitError, litellm.exceptions.NotFoundError) as e:
        if model != FALLBACK_MODEL:
            print(f"[warn] {model} rate-limited, falling back to {FALLBACK_MODEL}", file=sys.stderr)
            model = FALLBACK_MODEL
            response = litellm.completion(model=model, messages=messages)
        else:
            print(f"[warn] Both models rate-limited for {company['name']}: {e}", file=sys.stderr)
            return []

    raw = (response.choices[0].message.content or "").strip()
    data = extract_json(raw)
    if data is None:
        print(f"[warn] JSON parse failed for {company['name']}", file=sys.stderr)
        print(f"[debug] raw (first 400 chars): {raw[:400]}", file=sys.stderr)
        return []
    return data.get("roles", [])


# ── filter companies ───────────────────────────────────────────────────────────

def load_and_filter_companies(companies_path: Path) -> list[dict]:
    data = yaml.safe_load(companies_path.read_text(encoding="utf-8"))
    companies = data.get("companies", [])
    filtered, skipped = [], []
    for c in companies:
        name_lower = c.get("name", "").lower().strip()
        if name_lower in SKIP_COMPANIES or name_lower in SKIP_TIER2_SERVICES:
            skipped.append(c["name"])
        else:
            filtered.append(c)
    if skipped:
        print(f"[info] Skipped {len(skipped)}: {', '.join(skipped)}", file=sys.stderr)
    print(f"[info] Searching {len(filtered)} companies", file=sys.stderr)
    return filtered


# ── run ───────────────────────────────────────────────────────────────────────

def run(
    companies_path: Path,
    output_path: Path,
    model: str,
    api_key: str,
) -> None:
    if not companies_path.exists():
        print(f"Error: companies file not found at {companies_path}", file=sys.stderr)
        sys.exit(1)

    companies = load_and_filter_companies(companies_path)
    if not companies:
        print("Error: no companies left after filtering", file=sys.stderr)
        sys.exit(1)

    all_roles: list[dict] = []
    for company in companies:
        name = company["name"]
        print(f"[search] {name} ...", file=sys.stderr)
        results = search_company_ddg(company)
        print(f"  DDG: {len(results)} hits", file=sys.stderr)

        if not results:
            print("  → 0 roles (no search results)", file=sys.stderr)
            continue

        roles = llm_extract_roles(company, results, model, api_key)
        print(f"  → {len(roles)} role(s)", file=sys.stderr)
        all_roles.extend(roles)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Generated: {date.today()}\n"
        f"# Source: {companies_path.name}\n"
        "# Job URLs sourced from live web search — verify before applying.\n\n"
    )
    output_path.write_text(header + yaml.dump({"roles": all_roles}, allow_unicode=True, sort_keys=False))
    print(f"Saved: {output_path} ({len(all_roles)} roles total)")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Find open roles via DDG search + LLM extraction"
    )
    parser.add_argument("--companies", type=Path, default=DEFAULT_COMPANIES)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"roles-{date.today()}.yaml",
    )
    args = parser.parse_args()

    run(companies_path=args.companies, output_path=args.output, model=args.model, api_key=api_key)


if __name__ == "__main__":
    main()
