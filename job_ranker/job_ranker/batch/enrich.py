# batch/enrich.py
"""
Enrich jobs that have empty descriptions by scraping the public job page.

Currently supports:
- LinkedIn public job pages (no login required)

Uses a token-bucket rate limiter shared across all workers to maintain
a safe global request rate while maximizing throughput.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

# ── Concurrency & rate limiting ──────────────────────────────────
# Lower workers + slower rate = fewer 429s from LinkedIn
# Tradeoff: slower enrichment but more reliable
MAX_WORKERS = 2            # was 5 — reduced to cut LinkedIn 429s
REQUESTS_PER_SECOND = 1   # was 3 — 1 req/s is well under LinkedIn's limit
TIMEOUT = 15
MAX_RETRIES = 3
RETRY_BACKOFF = 6  # was 3 — longer backoff on retry

# Rotating user-agents to reduce fingerprinting
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

_BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Regex to extract description from LinkedIn public page
_DESC_RE = re.compile(
    r'<div class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")

# First datetime attribute on the page is the job's posting date
_DATE_RE = re.compile(r'datetime="(\d{4}-\d{2}-\d{2})"')


class _TokenBucket:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float):
        self._rate = rate
        self._tokens = rate  # start full
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last = now

            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                self._lock.release()
                time.sleep(wait)
                self._lock.acquire()
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
                self._last = now

            self._tokens -= 1.0


# Global rate limiter shared by all workers
_limiter = _TokenBucket(REQUESTS_PER_SECOND)

# Track consecutive 429s — if we get too many, back off globally
# Reset on each enrich() call via reset_rate_state()
_consecutive_429 = 0
_429_lock = threading.Lock()


def _reset_rate_state():
    """Reset module-level rate state between runs."""
    global _consecutive_429, _limiter
    with _429_lock:
        _consecutive_429 = 0
    _limiter = _TokenBucket(REQUESTS_PER_SECOND)


def _get_headers(index: int) -> dict:
    headers = dict(_BASE_HEADERS)
    headers["User-Agent"] = _USER_AGENTS[index % len(_USER_AGENTS)]
    return headers


def _scrape_linkedin_page(job_url: str, worker_id: int) -> Tuple[str | None, str | None]:
    """Scrape description and posting date from a public LinkedIn job page."""
    global _consecutive_429

    for attempt in range(1, MAX_RETRIES + 1):
        _limiter.acquire()

        # If many 429s, add extra global backoff
        with _429_lock:
            if _consecutive_429 >= 3:
                backoff = min(30, _consecutive_429 * 5)
                logger.info("[ENRICH] global backoff %ds (429 count=%d)", backoff, _consecutive_429)
                time.sleep(backoff)

        try:
            r = requests.get(
                job_url,
                headers=_get_headers(worker_id + attempt),
                timeout=TIMEOUT,
                allow_redirects=True,
            )

            if r.status_code == 429:
                with _429_lock:
                    _consecutive_429 += 1
                wait = RETRY_BACKOFF * (2 ** attempt)
                logger.info("[ENRICH] 429 rate-limited, waiting %ds (attempt %d)", wait, attempt)
                time.sleep(wait)
                continue

            # Reset 429 counter on success
            with _429_lock:
                _consecutive_429 = max(0, _consecutive_429 - 1)

            if r.status_code != 200:
                return None, None

            if "authwall" in r.url:
                return None, None

            html = r.text

            # Extract description
            desc = None
            match = _DESC_RE.search(html)
            if match:
                clean = _TAG_RE.sub(" ", match.group(1))
                clean = re.sub(r"\s+", " ", clean).strip()
                if len(clean) >= 50:
                    desc = clean

            # Extract posting date (first datetime attribute)
            date_posted = None
            date_match = _DATE_RE.search(html)
            if date_match:
                date_posted = date_match.group(1)

            return desc, date_posted

        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
        except requests.exceptions.RequestException:
            return None, None

    return None, None


def _enrich_one(args: Tuple[int, str]) -> Tuple[str, str | None, str | None]:
    """Enrich a single job. Returns (job_url, description or None, date or None)."""
    worker_id, job_url = args
    desc, date_posted = _scrape_linkedin_page(job_url, worker_id)
    return job_url, desc, date_posted


def enrich_linkedin_jobs(db_con, *, batch_size: int = 5000) -> int:
    """
    Find LinkedIn jobs missing descriptions or posting dates and scrape them.

    Args:
        db_con: DuckDB connection (read-write)
        batch_size: max jobs to enrich per run

    Returns:
        Number of jobs enriched
    """
    rows = db_con.execute(
        """
        SELECT job_url
        FROM jobs_raw
        WHERE site = 'linkedin'
          AND (
            (description IS NULL OR LENGTH(description) <= 20)
            OR date_posted IS NULL
          )
          AND job_url IS NOT NULL
          AND job_url LIKE '%linkedin.com/jobs/view/%'
        ORDER BY ingested_at DESC
        LIMIT ?
        """,
        [batch_size],
    ).fetchall()

    if not rows:
        logger.info("[ENRICH] No LinkedIn jobs need enrichment")
        return 0

    job_urls = [r[0] for r in rows]
    total = len(job_urls)
    logger.info(
        "[ENRICH] Enriching %d LinkedIn jobs (workers=%d, rate=%d req/s)",
        total, MAX_WORKERS, REQUESTS_PER_SECOND,
    )

    # Reset rate-limiter state from any previous run
    _reset_rate_state()

    enriched = 0
    failed = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_enrich_one, (i, url)): url
            for i, url in enumerate(job_urls)
        }

        for i, fut in enumerate(as_completed(futures), 1):
            url = futures[fut]
            try:
                _, desc, date_posted = fut.result(timeout=60)
            except Exception as e:
                logger.info("[ENRICH] exception for %s: %s", url, e)
                failed += 1
                continue

            got_something = False

            if desc:
                db_con.execute(
                    "UPDATE jobs_raw SET description = ? WHERE job_url = ? AND (description IS NULL OR LENGTH(description) <= 20)",
                    [desc, url],
                )
                got_something = True

            if date_posted:
                db_con.execute(
                    "UPDATE jobs_raw SET date_posted = ? WHERE job_url = ? AND date_posted IS NULL",
                    [date_posted, url],
                )
                got_something = True

            if got_something:
                enriched += 1
            else:
                failed += 1

            if i % 50 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                logger.info(
                    "[ENRICH] progress: %d/%d (enriched=%d, failed=%d, %.1f jobs/s)",
                    i, total, enriched, failed, rate,
                )

    elapsed = time.time() - start_time
    logger.info(
        "[ENRICH] Done: enriched=%d, failed=%d, total=%d, time=%.1fs (%.1f jobs/s)",
        enriched, failed, total, elapsed, total / elapsed if elapsed > 0 else 0,
    )
    return enriched
