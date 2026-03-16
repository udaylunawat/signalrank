"""
scripts/find_companies.py

Standalone script: feed resume to an OpenRouter LLM with DuckDuckGo web search
to discover top Pune/remote companies paying 50+ LPA.

Usage:
    uv run python scripts/find_companies.py
    uv run python scripts/find_companies.py --resume path/to/resume.tex
    uv run python scripts/find_companies.py --model openrouter/deepseek/deepseek-r1:free
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import litellm
import yaml
from duckduckgo_search import DDGS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── constants ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESUME = REPO_ROOT / "job_ranker" / "users" / "example" / "resume.tex"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs"
DEFAULT_MODEL = "openrouter/google/gemini-2.0-flash-exp:free"
MAX_ITERATIONS = 35
MAX_SEARCH_RESULTS = 5

# ── web search tool (client-side) ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information about companies, job openings, and salaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


def ddg_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Execute a DuckDuckGo search and return results."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return [{"title": "Search failed", "href": "", "body": str(e)}]


# ── prompt ────────────────────────────────────────────────────────────────────

def build_prompt(resume_text: str) -> str:
    return f"""You are a senior tech recruiter helping a candidate find the best companies to apply to.

[CANDIDATE RESUME]
{resume_text}

[REQUIREMENTS]
- Target: Senior AI Platform Engineer / MLOps / LLMOps roles
- Salary: 50+ LPA (Indian rupees, LPA = lakhs per annum)
- Location: Pune office OR Remote India
- Experience: ~7 years

[TASK]
Use web_search to find the top 20-30 companies that:
1. Are Tier 1 (FAANG-adjacent, AI-native, high-growth product companies) or
   Tier 2 (strong domain AI, well-funded, serious engineering culture)
2. Have a Pune office OR offer remote roles in India
3. Are actively hiring for roles matching this profile at 50+ LPA

Search for each promising company to find:
- Their current careers page URL
- Active job openings for AI/ML Platform roles

After your searches, return ONLY a JSON object (no markdown, no extra text) with one key "companies".
Each entry must have:
  name            (string)
  tier            ("1" or "2" as a string)
  location        ("pune", "remote", or "both")
  salary_est_lpa  ("min-max" string e.g. "60-90", or null)
  reason          (one sentence — why this company fits the profile)
  careers_url     (string URL found via search, or null)
  linkedin_search_url (LinkedIn Jobs search URL for this company + role, or null)
"""


# ── tool-use loop ─────────────────────────────────────────────────────────────

def run_search(model: str, api_key: str, prompt: str) -> dict:
    messages = [{"role": "user", "content": prompt}]

    for _ in range(MAX_ITERATIONS):
        response = litellm.completion(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            api_key=api_key,
        )

        choice = response.choices[0]
        msg = choice.message

        # No tool calls — LLM is done
        if not msg.tool_calls:
            break

        # Execute each tool call and collect results
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]})

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {"query": ""}
            results = ddg_search(args["query"])
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(results),
            })
    else:
        raise RuntimeError(
            f"Tool-use loop exceeded max iterations ({MAX_ITERATIONS}) without completing"
        )

    raw = (msg.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: failed to parse JSON response: {e}", file=sys.stderr)
        print(f"Raw response:\n{raw}", file=sys.stderr)
        sys.exit(1)


# ── run (importable for tests) ────────────────────────────────────────────────

def run(
    resume_path: Path,
    output_path: Path,
    model: str,
    api_key: str,
) -> None:
    if not resume_path.exists():
        print(f"Error: resume not found at {resume_path}", file=sys.stderr)
        sys.exit(1)

    resume_text = resume_path.read_text(encoding="utf-8", errors="ignore")
    prompt = build_prompt(resume_text)
    data = run_search(model=model, api_key=api_key, prompt=prompt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Generated: {date.today()}\n"
        "# URLs sourced from live web search — verify before applying.\n\n"
    )
    output_path.write_text(header + yaml.dump(data, allow_unicode=True, sort_keys=False))
    print(f"Saved: {output_path} ({len(data.get('companies', []))} companies)")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Find top companies via LLM + DuckDuckGo web search"
    )
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"companies-{date.today()}.yaml",
    )
    args = parser.parse_args()

    run(resume_path=args.resume, output_path=args.output, model=args.model, api_key=api_key)


if __name__ == "__main__":
    main()
