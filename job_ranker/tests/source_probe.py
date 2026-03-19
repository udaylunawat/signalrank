#!/usr/bin/env python3
"""
source_probe.py — Quick health check for all job scraping sources.

Run: python -m job_ranker.tests.source_probe
     (or: uv run python job_ranker/tests/source_probe.py)
"""
from __future__ import annotations

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
QUERY = "mlops engineer"
LOCATION = "India"


def _check(label: str, fn) -> tuple[str, int, str]:
    start = time.time()
    try:
        count = fn()
        elapsed = time.time() - start
        status = "✅" if count > 0 else "⚠️ "
        return label, count, f"{status}  {count} jobs  ({elapsed:.1f}s)"
    except Exception as e:
        elapsed = time.time() - start
        return label, 0, f"❌  ERROR: {e}  ({elapsed:.1f}s)"


def probe_jobspy_indeed():
    from jobspy import scrape_jobs
    jobs = scrape_jobs(
        site_name=["indeed"],
        search_term=QUERY,
        location=LOCATION,
        results_wanted=5,
        country_indeed="India",
    )
    return len(jobs) if jobs is not None else 0


def probe_remotive():
    r = requests.get(
        "https://remotive.com/api/remote-jobs",
        params={"search": QUERY, "limit": 5},
        timeout=15,
    )
    r.raise_for_status()
    return len(r.json().get("jobs", []))


def probe_himalayas():
    r = requests.get(
        "https://himalayas.app/jobs/api",
        params={"q": QUERY, "limit": 5},
        timeout=15,
    )
    r.raise_for_status()
    return len(r.json().get("jobs", []))


def probe_jobicy():
    r = requests.get(
        "https://jobicy.com/api/v2/remote-jobs",
        params={"count": 5, "tag": QUERY},
        timeout=15,
    )
    r.raise_for_status()
    return len(r.json().get("jobs", []))


def probe_jsearch():
    if not RAPIDAPI_KEY or len(RAPIDAPI_KEY) < 8:
        raise ValueError("RAPIDAPI_KEY not set or invalid")
    r = requests.get(
        "https://jsearch.p.rapidapi.com/search",
        headers={"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "jsearch.p.rapidapi.com"},
        params={"query": f"{QUERY} in {LOCATION}", "page": 1, "num_pages": 1},
        timeout=15,
    )
    if r.status_code in (401, 403):
        raise ValueError(f"Auth error {r.status_code} — check RAPIDAPI_KEY")
    r.raise_for_status()
    return len(r.json().get("data", []))


def probe_linkedin_jb():
    if not RAPIDAPI_KEY or len(RAPIDAPI_KEY) < 8:
        raise ValueError("RAPIDAPI_KEY not set or invalid")
    import http.client
    import json
    from urllib.parse import quote
    host = "linkedin-job-search-api.p.rapidapi.com"
    conn = http.client.HTTPSConnection(host, timeout=15)
    path = f"/active-jb-7d?limit=5&offset=0&title_filter={quote(QUERY)}&location_filter={quote(LOCATION)}&description_type=text"
    conn.request("GET", path, headers={
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
    })
    res = conn.getresponse()
    if res.status in (401, 403):
        raise ValueError(f"Auth error {res.status} — check RAPIDAPI_KEY / subscription")
    data = json.loads(res.read())
    conn.close()
    if isinstance(data, list):
        return len(data)
    return len(data.get("data", data.get("results", [])))


def main():
    print(f"\n{'='*55}")
    print("  Job Ranker — Source Probe")
    print(f"  Query: {QUERY!r}  Location: {LOCATION!r}")
    print(f"  RAPIDAPI_KEY: {'set (' + str(len(RAPIDAPI_KEY)) + ' chars)' if RAPIDAPI_KEY else 'NOT SET'}")
    print(f"{'='*55}\n")

    probes = [
        ("JobSpy / Indeed (free)",   probe_jobspy_indeed),
        ("Remotive (direct/free)",    probe_remotive),
        ("Himalayas (direct/free)",   probe_himalayas),
        ("Jobicy (direct/free)",      probe_jobicy),
        ("JSearch (RapidAPI)",        probe_jsearch),
        ("LinkedIn JB (RapidAPI)",    probe_linkedin_jb),
    ]

    results = []
    for label, fn in probes:
        _, count, msg = _check(label, fn)
        results.append((label, count, msg))
        print(f"  {label:<30} {msg}")

    print(f"\n{'='*55}")
    working = sum(1 for _, c, _ in results if c > 0)
    print(f"  {working}/{len(results)} sources returned jobs\n")

    if working == 0:
        print("  ❌ No sources working — check env / network")
        sys.exit(1)


if __name__ == "__main__":
    main()
