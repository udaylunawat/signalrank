"""
HTML/JSON parsing for Google Jobs results.

Google embeds job data in the initial HTML and subsequent async responses.
This module handles both formats.
"""
from __future__ import annotations

import json
import re
from typing import Optional


# ─────────────────────────────────────────────
# Initial page parser
# ─────────────────────────────────────────────

def extract_forward_cursor(html: str) -> Optional[str]:
    """
    Extract the pagination cursor (data-async-fc) from initial page HTML.
    Returns None if not found (no more pages or blocked).
    """
    match = re.search(r'<div jsname="Yust4d"[^>]+data-async-fc="([^"]+)"', html)
    return match.group(1) if match else None


def extract_jobs_from_initial_page(html: str) -> list[list]:
    """
    Extract raw job arrays from the initial Google search HTML.
    Google embeds job data as JSON inside a script tag.
    """
    jobs = []

    # Primary: look for the jobs JSON block
    # Pattern from JobSpy's Google scraper
    matches = re.findall(
        r'data-async-context="[^"]*"[^>]*>.*?(<c-wiz[^>]*jsmodel="[^"]*"[^>]*>)',
        html,
        re.DOTALL,
    )

    # Fallback: scan for the embedded JSON array pattern
    # Each job is encoded as a nested array starting with title at [0]
    pattern = re.compile(
        r'\[\["([^"]{3,})",\s*"([^"]{2,})",\s*"([^"]*)"',
    )

    # Try the script-embedded JSON approach (more reliable)
    script_matches = re.findall(
        r'AF_initDataCallback\(\{[^}]*key:\s*[\'"]ds:(\d+)[\'"][^}]*,\s*data:(.*?),\s*sideChannel',
        html,
        re.DOTALL,
    )

    for _, data_str in script_matches:
        try:
            data = json.loads(data_str)
            if isinstance(data, list):
                _walk(data, jobs)
        except (json.JSONDecodeError, Exception):
            continue

    return jobs


def _walk(node, collector: list, depth: int = 0):
    """Recursively walk JSON tree looking for job array patterns."""
    if depth > 15:
        return
    if isinstance(node, list):
        # Heuristic: a job array has a string title at [0], company at [1], location at [2]
        if (
            len(node) > 20
            and isinstance(node[0], str)
            and len(node[0]) > 3
            and isinstance(node[1], str)
            and len(node[1]) > 1
            and isinstance(node[2], str)
        ):
            collector.append(node)
            return
        for item in node:
            _walk(item, collector, depth + 1)


# ─────────────────────────────────────────────
# Async page parser
# ─────────────────────────────────────────────

def extract_jobs_from_async_page(response_text: str) -> tuple[list[list], Optional[str]]:
    """
    Parse jobs and next cursor from Google's async callback response.
    Returns (job_arrays, next_cursor).
    """
    jobs: list[list] = []

    # Extract next cursor
    cursor_match = re.search(r'data-async-fc="([^"]+)"', response_text)
    next_cursor = cursor_match.group(1) if cursor_match else None

    # Extract the main JSON payload — it starts with [[[
    start = response_text.find("[[[")
    end = response_text.rfind("]]]")
    if start == -1 or end == -1:
        return jobs, next_cursor

    try:
        parsed = json.loads(response_text[start : end + 3])
    except json.JSONDecodeError:
        return jobs, next_cursor

    if not isinstance(parsed, list) or not parsed:
        return jobs, next_cursor

    for entry in parsed[0]:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        _, inner = entry[0], entry[1] if len(entry) > 1 else None
        if not inner or not isinstance(inner, str) or not inner.startswith("[[["):
            continue
        try:
            job_data = json.loads(inner)
            _walk(job_data, jobs)
        except (json.JSONDecodeError, Exception):
            continue

    return jobs, next_cursor
