# batch/enrich.py
"""
Enrich jobs that have empty descriptions by scraping the public job page.

Currently supports:
- LinkedIn public job pages (no login required)
"""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import requests

logger = logging.getLogger(__name__)

# Throttle to avoid getting blocked
REQUEST_DELAY = 1.5  # seconds between requests per worker
MAX_WORKERS = 3
TIMEOUT = 15
MAX_RETRIES = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# Regex to extract description from LinkedIn public page
_DESC_RE = re.compile(
    r'<div class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _scrape_linkedin_description(job_url: str) -> str | None:
    """Scrape job description from a public LinkedIn job page."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                job_url,
                headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            if r.status_code == 429:
                wait = 5 * attempt
                logger.info("[ENRICH] 429 rate-limited, waiting %ds", wait)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                logger.info("[ENRICH] HTTP %d for %s", r.status_code, job_url)
                return None
            if "authwall" in r.url:
                logger.info("[ENRICH] authwall redirect for %s", job_url)
                return None

            match = _DESC_RE.search(r.text)
            if not match:
                return None

            clean = _TAG_RE.sub(" ", match.group(1))
            clean = re.sub(r"\s+", " ", clean).strip()
            return clean if len(clean) >= 50 else None

        except requests.exceptions.Timeout:
            logger.info("[ENRICH] timeout attempt=%d url=%s", attempt, job_url)
        except requests.exceptions.RequestException as e:
            logger.info("[ENRICH] request error: %s", e)
            return None

    return None


def _enrich_one(job_url: str) -> Tuple[str, str | None]:
    """Enrich a single job. Returns (job_url, description or None)."""
    time.sleep(REQUEST_DELAY)
    desc = _scrape_linkedin_description(job_url)
    return job_url, desc


def enrich_empty_descriptions(db_con, *, batch_size: int = 5000) -> int:
    """
    Find LinkedIn jobs with empty descriptions and scrape them.

    Args:
        db_con: DuckDB connection (read-write)
        batch_size: max jobs to enrich per run

    Returns:
        Number of jobs enriched
    """
    # Find LinkedIn jobs with empty/short descriptions
    rows = db_con.execute(
        """
        SELECT job_url
        FROM jobs_raw
        WHERE site = 'linkedin'
          AND (description IS NULL OR LENGTH(description) <= 20)
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
    logger.info("[ENRICH] Enriching %d LinkedIn jobs", len(job_urls))

    enriched = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_enrich_one, url): url for url in job_urls
        }

        for i, fut in enumerate(as_completed(futures), 1):
            url = futures[fut]
            try:
                _, desc = fut.result(timeout=30)
            except Exception as e:
                logger.info("[ENRICH] exception for %s: %s", url, e)
                failed += 1
                continue

            if desc:
                db_con.execute(
                    """
                    UPDATE jobs_raw
                    SET description = ?
                    WHERE job_url = ?
                    """,
                    [desc, url],
                )
                enriched += 1
            else:
                failed += 1

            if i % 20 == 0:
                logger.info(
                    "[ENRICH] progress: %d/%d (enriched=%d, failed=%d)",
                    i, len(job_urls), enriched, failed,
                )

    logger.info(
        "[ENRICH] Done: enriched=%d, failed=%d, total=%d",
        enriched, failed, len(job_urls),
    )
    return enriched
