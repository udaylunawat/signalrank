"""
test_recruiter_finder.py — Manual test/probe for RecruiterFinder.

Tests each waterfall step independently so you can see what's working
without a full DuckDB or API keys.

Usage:
    cd ~/Projects/job_ranker
    uv run python job_ranker/tests/test_recruiter_finder.py

    # Test a specific company:
    uv run python job_ranker/tests/test_recruiter_finder.py --company "Adobe"

    # Test against a real job URL in your DB:
    uv run python job_ranker/tests/test_recruiter_finder.py --job-url "https://www.linkedin.com/jobs/view/4356172565"
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dotenv import load_dotenv
load_dotenv()

from job_ranker.scrapers.recruiter_finder import (
    RecruiterFinder,
    resolve_domain_via_clearbit,
    _fallback_domain_guess,
    search_linkedin_people,
    search_hunter_io,
    extract_poster_from_db,
)


def probe_clearbit(company: str):
    print(f"\n── Step 1: Clearbit domain resolution for '{company}' ──")
    domain = resolve_domain_via_clearbit(company)
    if domain:
        print(f"  ✅ Resolved domain: {domain}")
    else:
        fallback = _fallback_domain_guess(company)
        print(f"  ⚠  Clearbit returned nothing. Fallback guess: {fallback}")
    return domain or _fallback_domain_guess(company)


def probe_db(job_url: str, db_con):
    print(f"\n── Step 2: LinkedIn job description lookup ──")
    if not job_url:
        print("  ⚠  No job URL provided, skipping.")
        return
    contacts = extract_poster_from_db(db_con, job_url)
    if contacts:
        print(f"  ✅ Found {len(contacts)} contact(s) in description:")
        for c in contacts:
            print(f"    {c.display()}")
    else:
        print("  ℹ  No poster/recruiter info found in job description.")


def probe_linkedin_people(company: str):
    rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
    print(f"\n── Step 3: LinkedIn People Search (RapidAPI) for '{company}' ──")
    if not rapidapi_key or len(rapidapi_key) < 8:
        print("  ⚠  RAPIDAPI_KEY not set or too short — skipping.")
        print("     Subscribe to 'linkedin-data-api' on RapidAPI if you want this step.")
        return []
    contacts = search_linkedin_people(company, rapidapi_key)
    if contacts:
        print(f"  ✅ Found {len(contacts)} contact(s):")
        for c in contacts:
            print(f"    {c.display()}")
    else:
        print("  ⚠  No contacts found (check RapidAPI subscription to linkedin-data-api)")
    return contacts


def probe_hunter(domain: str):
    hunter_key = os.getenv("HUNTER_API_KEY", "")
    print(f"\n── Step 4: Hunter.io for domain '{domain}' ──")
    if not hunter_key:
        print("  ⚠  HUNTER_API_KEY not set — skipping.")
        print("     Sign up free at https://hunter.io (25 searches/month)")
        return []
    contacts = search_hunter_io(domain, hunter_key)
    if contacts:
        print(f"  ✅ Found {len(contacts)} contact(s):")
        for c in contacts:
            print(f"    {c.display()}")
    else:
        print(f"  ⚠  No HR/recruiter emails found by Hunter.io for {domain}")
    return contacts


def run_full_waterfall(company: str, job_url: str = None, db_con=None):
    print(f"\n{'='*60}")
    print(f"  RecruiterFinder — Full Waterfall")
    print(f"  Company: {company}")
    if job_url:
        print(f"  Job URL: {job_url}")
    print(f"{'='*60}")

    finder = RecruiterFinder(db_con=db_con)
    contacts = finder.find(company=company, job_url=job_url, max_results=10)

    print(f"\n── Final Results: {len(contacts)} contact(s) ──")
    if not contacts:
        print("  No contacts found.")
        print("\n  To improve results:")
        print("  - Add HUNTER_API_KEY=... to .env (free at https://hunter.io)")
        print("  - Subscribe to linkedin-data-api on RapidAPI")
    else:
        for i, c in enumerate(contacts, 1):
            print(f"  {i}. {c.display()}")


def main():
    parser = argparse.ArgumentParser(description="Test RecruiterFinder waterfall")
    parser.add_argument("--company", default="Adobe", help="Company to test (default: Adobe)")
    parser.add_argument("--job-url", help="LinkedIn job URL to test with")
    parser.add_argument("--step", choices=["all", "clearbit", "db", "linkedin", "hunter"],
                        default="all", help="Run only a specific step")
    args = parser.parse_args()

    company = args.company
    job_url = args.job_url

    # Try to open DuckDB read-only
    db_con = None
    db_path = Path(__file__).resolve().parents[2] / "duckdb"
    if db_path.exists():
        try:
            import duckdb
            db_con = duckdb.connect(str(db_path), read_only=True)
            print(f"\n✔ Connected to DuckDB at {db_path}")
        except Exception as e:
            print(f"\n⚠  Could not open DuckDB: {e}")
    else:
        print(f"\n⚠  DuckDB not found at {db_path} — step 2 will be skipped")

    if args.step == "all":
        # Individual probes for visibility
        domain = probe_clearbit(company)
        probe_db(job_url, db_con)
        probe_linkedin_people(company)
        probe_hunter(domain)
        # Full waterfall
        run_full_waterfall(company, job_url, db_con)
    elif args.step == "clearbit":
        probe_clearbit(company)
    elif args.step == "db":
        probe_db(job_url, db_con)
    elif args.step == "linkedin":
        probe_linkedin_people(company)
    elif args.step == "hunter":
        domain = probe_clearbit(company)
        probe_hunter(domain)


if __name__ == "__main__":
    main()
