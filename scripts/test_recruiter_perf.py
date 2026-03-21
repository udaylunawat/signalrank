"""Performance test: recruiter search for 5 companies, with caching validation."""

import time

from job_ranker.scrapers.recruiter_finder import RecruiterFinder

DB_PATH = "job_ranker/duckdb"

COMPANIES = [
    ("Autodesk",   "Senior Software Engineer - Agentic AI"),
    ("Optum",      "AI/ML Engineer - LangChain, LangGraph and MCP"),
    ("Adobe",      "ML Platform Engineer"),
    ("ServiceNow", "Senior Machine Learning Engineer"),
    ("Atlassian",  "Staff Software Engineer - AI Platform"),
]

def run(label: str, refresh: bool):
    finder = RecruiterFinder(db_path=DB_PATH)
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    total_start = time.perf_counter()
    total_contacts = 0

    for company, title in COMPANIES:
        t0 = time.perf_counter()
        contacts = finder.find(company=company, job_title=title, refresh=refresh)
        elapsed = time.perf_counter() - t0
        total_contacts += len(contacts)

        source = "CACHE" if (not refresh and contacts and contacts[0].source != "ddg_linkedin") else "LIVE"
        # Detect cache hit: _load_cached returns contacts with original source field
        # A simpler signal: very fast = cache, slow = live
        source_label = "CACHE" if elapsed < 0.5 else "LIVE "

        print(f"\n  [{source_label} {elapsed:5.1f}s] {company}")
        for c in contacts:
            india = " [IN]" if c.linkedin_url and "in.linkedin.com" in c.linkedin_url else "     "
            llm = f" llm={c.llm_score:.0f}" if c.llm_score else ""
            print(f"    • {india} {c.name or '?':<30} {(c.title or '')[:50]}{llm}")
        if not contacts:
            print("    (no contacts found)")

    total = time.perf_counter() - total_start
    print(f"\n  {'─'*50}")
    print(f"  Total: {total:.1f}s  |  Companies: {len(COMPANIES)}  |  Contacts: {total_contacts}")
    print(f"  Avg per company: {total/len(COMPANIES):.1f}s")

run("RUN 1 — Live search (refresh=True)", refresh=True)
run("RUN 2 — Cache check (refresh=False)", refresh=False)
