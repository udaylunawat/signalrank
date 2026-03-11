"""
GoogleJobsScraper — standalone scraper for Google Jobs (udm=8).

How it works:
  1. GET https://www.google.com/search?q=<query>&udm=8
     → HTML contains first ~10 jobs + a pagination cursor (data-async-fc)
  2. GET https://www.google.com/async/callback:550?fc=<cursor>&...
     → JSON blob with next batch of jobs + new cursor
  3. Repeat until results_wanted or no more cursor.

No API key required. Fails if Google blocks the IP — use proxies in that case.
"""
from __future__ import annotations

import logging
import math
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

from .headers import HEADERS_INITIAL, HEADERS_JOBS_PAGE
from .model import Job

log = logging.getLogger("google_jobs")

GOOGLE_SEARCH_URL = "https://www.google.com/search"
GOOGLE_ASYNC_URL = "https://www.google.com/async/callback:550"
JOBS_PER_PAGE = 10

# async param — required by Google's paginator; this is a stable value
ASYNC_PARAM = (
    "_basejs:/xjs/_/js/k=xjs.s.en_US.JwveA-JiKmg.2018.O/am=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAACAAAoICAAAAAAAKMAfAAAAIAQAAAAAAAAAAAAACCAAAEJDAAACAAAAAGABAIAAARBAAABAAAAAgAgQAABAASKAfv8JAAABAAAAAAwAQAQACQAAAAAAcAEAQABoCAAAABAAAIABAACAAAAEAAAAFAAAAAAAAAAAAAAAAAAAAAAAAACAQADoBwAAAAAAAAAAAAAQBAAAAATQAAoACOAHAAAAAAAAAQAAAIIAAAA_ZAACAAAAAAAAcB8APB4wHFJ4AAAAAAAAAAAAAAAACECCYA5If0EACAAAAAAAAAAAAAAAAAAAUgRNXG4AMAE/dg=0/br=1/rs=ACT90oGxMeaFMCopIHq5tuQM-6_3M_VMjQ"
)


class GoogleJobsScraper:
    """
    Scrapes Google Jobs search results.

    Args:
        proxies:     List of proxy strings, e.g. ["user:pass@host:port"]
        delay:       Seconds to sleep between paginated requests (default 2.0)
        timeout:     Request timeout in seconds (default 15)
    """

    def __init__(
        self,
        proxies: list[str] | None = None,
        delay: float = 2.0,
        timeout: int = 15,
    ):
        self.delay = delay
        self.timeout = timeout
        self.seen_ids: set[str] = set()
        self._session = self._build_session(proxies)

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def scrape(
        self,
        query: str,
        location: str = "",
        results_wanted: int = 50,
        hours_old: Optional[int] = None,
        is_remote: bool = False,
    ) -> list[Job]:
        """
        Scrape Google Jobs for the given query and filters.

        Args:
            query:           Search term, e.g. "machine learning engineer"
            location:        City/region, e.g. "Pune", "India", "Remote"
            results_wanted:  Max jobs to return (default 50, max ~900)
            hours_old:       Only return jobs posted within this many hours
            is_remote:       Append "remote" to query

        Returns:
            List of Job objects, deduplicated by URL.
        """
        results_wanted = min(results_wanted, 900)
        self.seen_ids.clear()
        jobs: list[Job] = []

        full_query = self._build_query(query, location, hours_old, is_remote)
        log.info("Google Jobs query: %r  (want %d results)", full_query, results_wanted)

        # Step 1: Initial page
        cursor, initial_jobs = self._fetch_initial(full_query)
        jobs.extend(initial_jobs)
        log.info("Initial page: %d jobs, cursor=%s", len(initial_jobs), bool(cursor))

        if not cursor:
            log.warning("No pagination cursor found — got at most ~10 results")
            return jobs[:results_wanted]

        # Step 2: Paginate
        max_pages = math.ceil(results_wanted / JOBS_PER_PAGE)
        for page in range(1, max_pages):
            if len(jobs) >= results_wanted:
                break
            if not cursor:
                log.info("No more pages after page %d", page)
                break

            log.info("Fetching page %d / %d (%d jobs so far)", page + 1, max_pages, len(jobs))
            time.sleep(self.delay)

            try:
                page_jobs, cursor = self._fetch_next_page(cursor)
            except Exception as e:
                log.warning("Failed to fetch page %d: %s", page + 1, e)
                break

            if not page_jobs:
                log.info("Empty page %d — stopping", page + 1)
                break

            jobs.extend(page_jobs)

        log.info("Total collected: %d jobs", len(jobs))
        return jobs[:results_wanted]

    def scrape_to_dataframe(self, *args, **kwargs):
        """Convenience wrapper — returns a pandas DataFrame."""
        import pandas as pd
        jobs = self.scrape(*args, **kwargs)
        return pd.DataFrame([j.to_dict() for j in jobs])

    # ─────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────

    def _build_query(
        self,
        query: str,
        location: str,
        hours_old: Optional[int],
        is_remote: bool,
    ) -> str:
        q = query.strip()
        if location:
            q += f" in {location.strip()}"
        if is_remote:
            q += " remote"
        if hours_old:
            if hours_old <= 24:
                q += " since yesterday"
            elif hours_old <= 72:
                q += " in the last 3 days"
            elif hours_old <= 168:
                q += " in the last week"
            else:
                q += " in the last month"
        return q

    def _get(self, url: str, headers: dict, params: dict):
        """Unified GET — tls_client doesn't accept timeout kwarg."""
        if getattr(self, "_is_tls_client", False):
            return self._session.get(url, headers=headers, params=params)
        return self._session.get(url, headers=headers, params=params, timeout=self.timeout)

    def _check_status(self, resp) -> None:
        """Raise on bad status — works for both requests and tls_client responses."""
        status = getattr(resp, "status_code", None)
        if status and status >= 400:
            raise Exception(f"HTTP {status}")

    def _fetch_initial(self, query: str) -> tuple[Optional[str], list[Job]]:
        """Fetch first page, return (cursor, jobs)."""
        params = {"q": query, "udm": "8"}
        try:
            resp = self._get(GOOGLE_SEARCH_URL, HEADERS_INITIAL, params)
            self._check_status(resp)
        except requests.RequestException as e:
            log.error("Initial request failed: %s", e)
            return None, []

        blocked, reason = self._is_blocked(resp.text)
        if blocked:
            log.error(
                "Google is blocking this request (%s). "
                "If running on your laptop, this may be a transient block — try again in a few minutes. "
                "On servers/Docker, use --proxy with a residential proxy.",
                reason,
            )
            return None, []

        cursor = self._extract_cursor(resp.text)
        jobs = self._parse_initial_html(resp.text)

        # Debug: log what we found
        has_widget = "Yust4d" in resp.text or "data-async-fc" in resp.text
        log.debug(
            "Initial page: status=%s len=%d has_widget=%s cursor=%s jobs=%d",
            getattr(resp, "status_code", "?"), len(resp.text), has_widget, bool(cursor), len(jobs)
        )
        return cursor, jobs

    def _is_blocked(self, html: str) -> tuple[bool, str]:
        """
        Detect actual Google blocking / CAPTCHA.
        Only returns True for clear hard-block signals — not for missing widget markers
        (the widget may just not appear for certain queries/regions).
        """
        # Hard block signals only — things that definitively mean we're blocked
        hard_blocks = {
            "detected unusual traffic": "unusual traffic detected",
            "our systems have detected unusual": "unusual traffic detected",
            "g-recaptcha": "CAPTCHA challenge",
            "/sorry/index": "Google sorry page",
            "sorry/index?continue": "Google sorry page",
        }
        lower = html.lower()
        for signal, reason in hard_blocks.items():
            if signal in lower:
                return True, reason

        # Soft signal: page is very short (< 2000 chars) — likely a redirect/error
        if len(html) < 2000:
            return True, f"response too short ({len(html)} chars)"

        return False, ""

    def _fetch_next_page(self, cursor: str) -> tuple[list[Job], Optional[str]]:
        """Fetch a paginated batch, return (jobs, next_cursor)."""
        params = {
            "fc": [cursor],
            "fcv": ["3"],
            "async": [ASYNC_PARAM],
        }
        resp = self._get(GOOGLE_ASYNC_URL, HEADERS_JOBS_PAGE, params)
        self._check_status(resp)
        return self._parse_async_response(resp.text)

    def _extract_cursor(self, html: str) -> Optional[str]:
        match = re.search(r'<div jsname="Yust4d"[^>]+data-async-fc="([^"]+)"', html)
        return match.group(1) if match else None

    def _parse_initial_html(self, html: str) -> list[Job]:
        """
        Pull jobs from initial HTML. Google embeds them in AF_initDataCallback scripts.
        Falls back to regex scanning if JSON extraction fails.
        """
        jobs: list[Job] = []

        # Try AF_initDataCallback blocks
        blocks = re.findall(
            r"AF_initDataCallback\(\{[^}]*data:([\s\S]*?),\s*sideChannel",
            html,
        )
        for block in blocks:
            try:
                data = _safe_json(block)
                if data:
                    _walk_for_jobs(data, jobs, self.seen_ids)
            except Exception:
                continue

        return jobs

    def _parse_async_response(self, text: str) -> tuple[list[Job], Optional[str]]:
        """Parse jobs and next cursor from async response."""
        jobs: list[Job] = []

        cursor_match = re.search(r'data-async-fc="([^"]+)"', text)
        next_cursor = cursor_match.group(1) if cursor_match else None

        start = text.find("[[[")
        end = text.rfind("]]]")
        if start == -1 or end == -1:
            return jobs, next_cursor

        try:
            parsed = _safe_json(text[start : end + 3])
        except Exception:
            return jobs, next_cursor

        if not isinstance(parsed, list) or not parsed:
            return jobs, next_cursor

        for entry in parsed[0]:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            inner = entry[1] if len(entry) > 1 else None
            if not inner or not isinstance(inner, str):
                continue
            if not inner.strip().startswith("["):
                continue
            try:
                job_data = _safe_json(inner)
                if job_data:
                    _walk_for_jobs(job_data, jobs, self.seen_ids)
            except Exception:
                continue

        return jobs, next_cursor

    def _build_session(self, proxies):
        """Try tls-client first (better TLS fingerprinting), fall back to requests."""
        try:
            import tls_client
            session = tls_client.Session(
                client_identifier="chrome_130",
                random_tls_extension_order=True,
            )
            if proxies:
                session.proxies = {"https": proxies[0], "http": proxies[0]}
            self._is_tls_client = True
            return session
        except ImportError:
            self._is_tls_client = False
            session = requests.Session()
            if proxies:
                session.proxies = {"https": proxies[0], "http": proxies[0]}
            return session


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _safe_json(s: str):
    """Parse JSON, stripping JS-style trailing commas and other quirks."""
    import json
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Strip trailing comma before } or ]
        cleaned = re.sub(r",\s*([}\]])", r"\1", s)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def _walk_for_jobs(node, collector: list[Job], seen: set, depth: int = 0):
    """
    Recursively walk JSON tree and extract jobs.

    A job node is a list where:
      [0] = title (str, len > 3)
      [1] = company (str, len > 1)
      [2] = location (str)
      [3] = [[url, ...], ...]  (list with URL)
      [12] = "X days ago" (str)
      [19] = description (str, len > 20)
      [28] = job id (str)
    """
    if depth > 20:
        return

    if not isinstance(node, list):
        return

    # Heuristic: check if this looks like a job node
    if (
        len(node) > 20
        and isinstance(node[0], str) and len(node[0]) > 3   # title
        and isinstance(node[1], str) and len(node[1]) > 1   # company
        and isinstance(node[2], str)                          # location
        and isinstance(node[19], str) and len(node[19]) > 20 # description
    ):
        job = _parse_job_node(node, seen)
        if job:
            collector.append(job)
        return

    for item in node:
        _walk_for_jobs(item, collector, seen, depth + 1)


def _parse_job_node(node: list, seen: set) -> Optional[Job]:
    """Convert a raw job array node to a Job object."""
    try:
        title = node[0]
        company = node[1]
        location = node[2]
        description = node[19] if len(node) > 19 else ""

        # URL lives at node[3][0][0]
        job_url = None
        if len(node) > 3 and isinstance(node[3], list) and node[3]:
            inner = node[3][0]
            if isinstance(inner, list) and inner:
                job_url = inner[0]

        # Dedup
        job_id = str(node[28]) if len(node) > 28 else job_url or f"{title}-{company}"
        if job_id in seen:
            return None
        seen.add(job_id)

        # Date
        date_posted = None
        if len(node) > 12 and isinstance(node[12], str):
            match = re.search(r"(\d+)", node[12])
            if match:
                days_ago = int(match.group(1))
                date_posted = (datetime.now() - timedelta(days=days_ago)).date()

        # Salary hint from node[11] or node[16]
        salary = None
        for idx in (11, 16):
            if len(node) > idx and isinstance(node[idx], str) and any(
                c in node[idx] for c in ("₹", "$", "€", "£", "LPA", "lakh", "k/yr", "/yr", "per year")
            ):
                salary = node[idx]
                break

        is_remote = bool(
            description and ("remote" in description.lower() or "wfh" in description.lower())
        )

        return Job(
            id=f"go-{job_id}",
            title=title,
            company=company,
            location=location,
            description=description,
            job_url=job_url,
            date_posted=date_posted,
            is_remote=is_remote,
            salary=salary,
            source="google",
        )
    except (IndexError, TypeError, KeyError):
        return None
