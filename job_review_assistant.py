"""
job_review_assistant.py — LLM-powered job triage using OpenRouter free models.

Loads unreviewed jobs from the latest job_ranker run, evaluates them 5 at a time
against your profile, and lets you add good ones to job_tracker.csv.

Usage:
    python job_review_assistant.py                  # interactive, 5 at a time
    python job_review_assistant.py --top 100        # scan top N ranked jobs
    python job_review_assistant.py --auto           # add all LLM-approved without prompting
    python job_review_assistant.py --batch 10       # larger batch size
    python job_review_assistant.py --csv <file>     # use mini_ranker CSV instead of DB
    python job_review_assistant.py --dry-run        # show decisions without writing
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))

# ruff: noqa: E402
import re

from job_ranker.llm.client import (
    llm_text,  # noqa: E402 — must come after sys.path patch
)

TRACKER_PATH = Path("job_ranker/users/example/job_tracker.csv")
DB_PATH = Path("job_ranker/duckdb")
RESUME_PATH = Path("job_ranker/users/example/resume.tex")


def _load_resume() -> str:
    """Load and clean resume, stripping LaTeX markup."""
    if not RESUME_PATH.exists():
        return ""
    raw = RESUME_PATH.read_text(encoding="utf-8", errors="ignore")
    # Strip LaTeX comments
    raw = re.sub(r"%.*$", "", raw, flags=re.MULTILINE)
    # \begin{}/\end{} blocks
    raw = re.sub(r"\\(?:begin|end)\{[^}]*\}", " ", raw)
    # \command[opt]{content} → content
    raw = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", raw)
    # remaining \commands
    raw = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", raw)
    # braces, backslashes, special chars
    raw = re.sub(r"[{}\\~^&$#_]", " ", raw)
    # collapse whitespace
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


RESUME_TEXT = _load_resume()

_SYSTEM_TEMPLATE = """You are a job triage assistant helping an ML/AI engineer decide which jobs to apply to.

=== CANDIDATE RESUME ===
{resume}
========================

Additional context:
- 7 years of experience total
- Target salary: 60L+ INR
- Preferred locations: Pune, Bangalore, Remote (India)
- Target companies: Tier S (Google, Microsoft, Nvidia, OpenAI, Anthropic, Salesforce, Adobe, Meta, Palantir),
                    Tier A (Intuit, Mastercard, Atlassian, Palo Alto Networks, CrowdStrike, Goldman Sachs,
                            Zendesk, Barclays, Citi, Qualcomm, Oracle, ServiceNow, NielsenIQ, Priceline,
                            Capital One, Red Hat, Autodesk, Apple, Snowflake, Databricks)
- Tier B acceptable: Siemens, GE Healthcare, Optum, MSCI, Wolters Kluwer, Razorpay, PhonePe

For each job in the batch, return a JSON array where each element has:
- "idx": job index (0-based integer)
- "decision": "ADD" or "SKIP"
- "priority": "P1" (strong match, apply today), "P2" (good match, apply this week), "P3" (backup) — only if ADD
- "reason": one sentence explaining the key reason

ADD only when ALL hold:
1. Role type matches: AI/ML platform, LLM systems, agentic AI, MLOps, GenAI, inference infra
2. Company is tier S/A (preferred) or tier B (acceptable) — no pure IT services/consulting
3. IC engineer role — not support, management, data analyst, or QA
4. Realistic for 7 YOE — skip roles requiring 10+ YOE, "senior staff", "principal", "VP", "director"
5. Skills overlap with resume — Python, LLMs, RAG, Kubernetes, GCP/AWS, LangGraph/LangChain

Be selective. SKIP borderline cases.
Return ONLY a valid JSON array, no markdown fences, no other text."""

SYSTEM_PROMPT = _SYSTEM_TEMPLATE.format(resume=RESUME_TEXT)

BAD_COMPANIES = {
    # config.yaml avoid_companies
    "wipro", "infosys", "tcs", "tata consultancy", "hcl", "tech mahindra",
    "cognizant", "capgemini", "ibm", "epam", "globallogic", "nagarro",
    "fractal", "genpact", "accenture", "deloitte", "ntt data",
    # IT services / staffing / consulting
    "luxoft", "perficient", "impetus", "kyndryl", "t&s consulting", "quest global",
    "bristlecone", "canorous", "expleo", "birlasoft", "ltimindtree",
    # Unknown / low-signal companies from past runs
    "simeio", "hrg group", "motm", "infinite computer", "win solutions", "bigcloudy",
    "cosmicfusion", "codeguardian", "codearray", "hajana", "eshkon", "fidelis",
    "lithan", "d4 insight", "transnational ai", "codersbay", "4bell", "synmatch",
    "netwin", "ipeople", "gnani", "employee hub", "fresherjob", "rosemallow",
    "vworker", "nextbrain", "onelab", "abstrabit", "abstract it", "inssemble",
    "tp digital", "humaniquee", "valuelabs", "mycareernet", "acronotics",
    "buzzboard", "sinaxis", "bridgeai",
}

BAD_TITLE_FRAGMENTS = [
    "support engineer", "data architect", "java developer", "automation lead",
    "test automation", "rtl front-end", "asp.net", "wpf", "embedded firmware",
    "principal", "senior staff", "data modeler", "deputy manager",
]

TRACKER_FIELDNAMES = [
    "Priority", "Group", "Company", "Title", "Location", "System Score",
    "Resume Match %", "Matching Skills", "Search Terms", "Gaps / Missing",
    "Date Posted", "Indeed URL", "Company Board URL", "Status", "Referral Contact",
    "Date Applied", "Interview Date", "Offer LPA", "Notes",
]

PRIORITY_LABELS = {
    "P1": "🔥 P1 - Apply Today",
    "P2": "⚡ P2 - Apply This Week",
    "P3": "📋 P3 - Low Priority",
}


def _extract_job_id(url: str) -> str | None:
    """Extract a platform-specific job ID from a URL for robust dedup.

    Handles Indeed (jk=), LinkedIn (/view/NNN), Glassdoor (jl=NNN),
    and Workday/Greenhouse/SmartRecruiters path slugs.
    """
    if not url:
        return None
    # Indeed: ?jk=abc123
    m = re.search(r"[?&]jk=([a-zA-Z0-9]+)", url)
    if m:
        return f"indeed:{m.group(1)}"
    # LinkedIn: /view/1234567890
    m = re.search(r"/view/(\d{7,})", url)
    if m:
        return f"linkedin:{m.group(1)}"
    # Glassdoor: jl=1234567890
    m = re.search(r"jl=(\d{7,})", url)
    if m:
        return f"glassdoor:{m.group(1)}"
    # Workday: job/<slug>_<JOBID>
    m = re.search(r"_([A-Z0-9]{6,}(?:-\d+)?(?:-\d+)?)(?:/|$|\?)", url)
    if m:
        return f"workday:{m.group(1)}"
    return None


def _norm_title(title: str) -> str:
    """Normalise a title for fuzzy dedup: lowercase, strip seniority words, drop punctuation."""
    t = title.lower()
    for word in ("senior", "sr.", "sr ", "lead", "staff", "junior", "jr.", "jr "):
        t = t.replace(word, " ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _norm_company(company: str) -> str:
    c = company.lower()
    c = re.sub(r"\b(inc|ltd|llc|pvt|private|limited|technologies|solutions|global|india)\b", "", c)
    return re.sub(r"[^a-z0-9]", "", c)


def load_tracker_urls() -> tuple[set[str], set[str], set[tuple[str, str]]]:
    """Return (full_urls, job_ids, company_title_pairs) from the tracker."""
    if not TRACKER_PATH.exists():
        return set(), set(), set()
    full_urls: set[str] = set()
    job_ids: set[str] = set()
    company_titles: set[tuple[str, str]] = set()
    with open(TRACKER_PATH) as f:
        for row in csv.DictReader(f):
            for field in ("Indeed URL", "Company Board URL"):
                u = row.get(field, "").strip()
                if not u:
                    continue
                full_urls.add(u)
                jid = _extract_job_id(u)
                if jid:
                    job_ids.add(jid)
            company = row.get("Company", "").strip()
            title = row.get("Title", "").strip()
            if company and title:
                company_titles.add((_norm_company(company), _norm_title(title)))
    return full_urls, job_ids, company_titles


def load_jobs_from_db(top: int) -> list[dict]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    run_id = con.execute(
        "SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()[0]
    rows = con.execute(
        "SELECT rr.final_score, rr.job_url, rr.payload "
        "FROM run_results rr WHERE rr.run_id = ? "
        "ORDER BY rr.final_score DESC LIMIT ?",
        [run_id, top],
    ).fetchall()
    con.close()
    jobs = []
    for score, url, payload in rows:
        p = json.loads(payload) if payload else {}
        jobs.append({
            "score": score,
            "url": url or "",
            "title": p.get("title", ""),
            "company": p.get("company", ""),
            "location": p.get("location", ""),
            "semantic": p.get("semantic_score", 0),
            "role": p.get("functional_role", ""),
            "date_posted": p.get("date_posted", ""),
            "description": (p.get("description") or "")[:800],
        })
    return jobs


def load_jobs_from_csv(csv_path: str, top: int) -> list[dict]:
    with open(csv_path) as f:
        rows = sorted(
            csv.DictReader(f),
            key=lambda r: float(r.get("final_score", 0)),
            reverse=True,
        )
    return [
        {
            "score": float(r.get("final_score", 0)),
            "url": r.get("job_url", ""),
            "title": r.get("title", ""),
            "company": r.get("company", ""),
            "location": r.get("location", ""),
            "semantic": float(r.get("semantic_score", 0)),
            "role": r.get("functional_role", ""),
            "date_posted": r.get("date_posted", ""),
            "description": (r.get("description") or "")[:800],
        }
        for r in rows[:top]
    ]


def filter_jobs(
    jobs: list[dict],
    known_urls: set[str],
    known_ids: set[str],
    known_ct: set[tuple[str, str]],
) -> list[dict]:
    out = []
    for j in jobs:
        url = j["url"]
        # 1. Exact URL match
        if url in known_urls:
            continue
        # 2. Platform job-ID match (catches cross-platform dupes e.g. Indeed vs Glassdoor)
        jid = _extract_job_id(url)
        if jid and jid in known_ids:
            continue
        # 3. Company + normalised title match (catches cross-platform dupes with no shared ID)
        ct = (_norm_company(j["company"]), _norm_title(j["title"]))
        if ct in known_ct:
            continue
        company = j["company"].lower()
        if any(b in company for b in BAD_COMPANIES):
            continue
        title = j["title"].lower()
        if any(b in title for b in BAD_TITLE_FRAGMENTS):
            continue
        out.append(j)
    return out


def location_group(location: str) -> str:
    loc = location.lower()
    for token, label in [
        ("pune", "Pune/Remote"), ("mh, in", "Pune/Remote"), ("maharashtra", "Pune/Remote"),
        ("bangalore", "Bangalore"), ("bengaluru", "Bangalore"),
        ("ka, in", "Bangalore"), ("karnataka", "Bangalore"),
        ("hyderabad", "Hyderabad"), ("ts, in", "Hyderabad"), ("telangana", "Hyderabad"),
        ("remote", "Remote"),
    ]:
        if token in loc:
            return label
    return location[:20]


def build_batch_prompt(batch: list[dict]) -> str:
    parts = []
    for i, j in enumerate(batch):
        parts.append(
            f"[{i}] {j['title']} @ {j['company']} | {j['location']} | "
            f"score={j['score']:.1f} sem={j['semantic']:.3f}\n"
            f"    {j['description'][:400]}"
        )
    return "\n\n".join(parts)


def _parse_evaluations(raw: str) -> list[dict]:
    text = raw.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    text = text.rstrip("`").strip()
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1:
        return json.loads(text[start : end + 1])
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        obj = json.loads(text[start : end + 1])
        for key in ("jobs", "results", "evaluations", "items"):
            if key in obj and isinstance(obj[key], list):
                return obj[key]
    raise ValueError(f"No JSON array found in: {text[:200]}")


def evaluate_batch(batch: list[dict]) -> list[dict]:
    raw = llm_text(
        SYSTEM_PROMPT,
        f"Evaluate these jobs:\n\n{build_batch_prompt(batch)}",
        max_tokens=600,
    )
    if not raw:
        print("  [LLM] empty response — all models exhausted or rate-limited")
        return []
    try:
        return _parse_evaluations(raw)
    except Exception as e:
        print(f"  [LLM parse error] {e}")
        print(f"  Raw response: {raw[:300]}")
        return []


def append_to_tracker(rows: list[dict]) -> None:
    with open(TRACKER_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDNAMES)
        for row in rows:
            writer.writerow(row)
    print(f"  Appended {len(rows)} row(s) to {TRACKER_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-powered job triage assistant")
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--batch", type=int, default=5)
    parser.add_argument("--auto", action="store_true", help="Add all approved without prompting")
    parser.add_argument("--csv", help="Use mini_ranker CSV instead of DB")
    parser.add_argument("--dry-run", action="store_true", help="Show decisions, don't write")
    args = parser.parse_args()

    print(f"\n  Job Review Assistant  [top={args.top} batch={args.batch} auto={args.auto}]\n")

    known_urls, known_ids, known_ct = load_tracker_urls()
    print(f"  Tracker: {len(known_urls)} URLs · {len(known_ids)} job IDs · {len(known_ct)} company+title pairs")

    all_jobs = load_jobs_from_csv(args.csv, args.top) if args.csv else load_jobs_from_db(args.top)
    candidates = filter_jobs(all_jobs, known_urls, known_ids, known_ct)
    print(f"  Candidates after filter: {len(candidates)} / {len(all_jobs)}\n")

    if not candidates:
        print("  Nothing new to review.")
        return

    to_add: list[dict] = []
    offset = 0

    while offset < len(candidates):
        batch = candidates[offset : offset + args.batch]
        batch_num = offset // args.batch + 1
        offset += args.batch

        print(f"  ── Batch {batch_num} ({len(batch)} jobs) " + "─" * 38)
        for i, j in enumerate(batch):
            print(f"  [{i}] {j['score']:.1f} | {j['title'][:45]:45} | {j['company'][:22]:22} | {j['location'][:18]}")
        print()

        evals = evaluate_batch(batch)

        if not evals:
            print("  [WARN] No evaluations — skipping batch\n")
            if not args.auto:
                if input("  Continue? [Y/n] ").strip().lower() == "n":
                    break
            continue

        batch_adds: list[tuple[dict, str, str]] = []
        for ev in evals:
            idx = int(ev.get("idx", -1))
            if not (0 <= idx < len(batch)):
                continue
            job = batch[idx]
            decision = str(ev.get("decision", "SKIP")).upper()
            priority = str(ev.get("priority", "P3"))
            reason = str(ev.get("reason", ""))
            marker = "ADD " if decision == "ADD" else "SKIP"
            tag = f"[{priority}]" if decision == "ADD" else "     "
            print(f"  {marker} {tag} {job['title'][:45]:45} @ {job['company']}")
            print(f"           {reason}")
            if decision == "ADD":
                batch_adds.append((job, priority, reason))

        print()

        if batch_adds:
            if args.auto or args.dry_run:
                confirmed = batch_adds
            else:
                print(f"  LLM recommends adding {len(batch_adds)} job(s):")
                for i, (j, p, _) in enumerate(batch_adds):
                    print(f"    [{i}] {p} | {j['title']} @ {j['company']}")
                ans = input("  Add all? [Y/n/indices e.g. 0,2] ").strip().lower()
                if ans == "n":
                    confirmed = []
                elif ans in ("", "y"):
                    confirmed = batch_adds
                else:
                    indices = {int(x) for x in ans.split(",") if x.strip().isdigit()}
                    confirmed = [batch_adds[i] for i in sorted(indices) if i < len(batch_adds)]

            for job, priority, reason in confirmed:
                to_add.append({
                    "Priority": PRIORITY_LABELS.get(priority, PRIORITY_LABELS["P3"]),
                    "Group": location_group(job["location"]),
                    "Company": job["company"],
                    "Title": job["title"],
                    "Location": job["location"],
                    "System Score": round(job["score"], 1),
                    "Resume Match %": round(job["semantic"] * 100),
                    "Matching Skills": "",
                    "Search Terms": job["role"].replace("_", " ").title(),
                    "Gaps / Missing": "",
                    "Date Posted": job.get("date_posted", ""),
                    "Indeed URL": job["url"],
                    "Company Board URL": "",
                    "Status": "", "Referral Contact": "", "Date Applied": "",
                    "Interview Date": "", "Offer LPA": "",
                    "Notes": reason,
                })

        if not args.auto and offset < len(candidates):
            if input("  Next batch? [Y/n] ").strip().lower() == "n":
                break
        print()

    if to_add and not args.dry_run:
        append_to_tracker(to_add)
    elif to_add:
        print(f"  [DRY RUN] Would add {len(to_add)} jobs:")
        for r in to_add:
            print(f"    {r['Priority'][:6]} | {r['Company']:25} | {r['Title']}")
    else:
        print("  No new jobs added.")

    print(f"\n  Done. Total added: {len(to_add)}\n")


if __name__ == "__main__":
    main()
