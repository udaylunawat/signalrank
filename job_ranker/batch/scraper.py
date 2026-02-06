# batch/scraper.py
"""
Job scraping for Job Ranker v2.

Design goals:
- Deterministic inputs, tolerant outputs
- Never appear "stuck" without logs
- Fail soft on individual queries
- Collect rows explicitly (no implicit side effects)
"""

from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import pandas as pd
from jobspy import scrape_jobs

logger = logging.getLogger(__name__)

# Conservative defaults
MAX_WORKERS = 1
DEFAULT_RESULTS_WANTED = 100
MIN_DESC_LEN = 20

# Observability / safety
MAX_QUERY_SECONDS = 90
LOG_HEARTBEAT_SECONDS = 15


# --------------------------------------------------
# Internal helpers
# --------------------------------------------------
def _normalize_jobs(jobs) -> List[dict]:
    """
    Normalize JobSpy output into a list[dict].

    JobSpy may return:
    - list[dict]
    - pandas.DataFrame
    - None
    """
    if jobs is None:
        return []

    if isinstance(jobs, pd.DataFrame):
        return jobs.to_dict("records")

    if isinstance(jobs, list):
        return [j for j in jobs if isinstance(j, dict)]

    logger.warning("[SCRAPE] Unsupported job payload type: %s", type(jobs))
    return []


def _scrape_single_query(
    *,
    query: str,
    scraping_cfg: dict,
    hours_old: int,
) -> List[dict]:
    """
    Run a single JobSpy query.

    This function is intentionally synchronous and noisy.
    If it blocks, we want to know exactly where.
    """
    kwargs = {
        "site_name": scraping_cfg.get("sites", {}).get("enabled", ["indeed"]),
        "search_term": query,
        "location": scraping_cfg.get("country", "India"),
        "country_indeed": scraping_cfg.get("country", "India"),
        "results_wanted": scraping_cfg.get(
            "max_results",
            DEFAULT_RESULTS_WANTED,
        ),
    }

    # Only pass hours_old if explicitly supported
    if scraping_cfg.get("supports_hours_old", False):
        kwargs["hours_old"] = hours_old

    logger.info("[SCRAPE] ▶ starting query=%r", query)

    stop_heartbeat = threading.Event()

    def _heartbeat():
        while not stop_heartbeat.wait(LOG_HEARTBEAT_SECONDS):
            logger.info(
                "[SCRAPE] … still running query=%r elapsed=%.1fs",
                query,
                time.time() - start,
            )

    hb_thread = threading.Thread(target=_heartbeat, daemon=True)
    hb_thread.start()

    start = time.time()
    try:
        jobs = scrape_jobs(**kwargs)
    except TypeError as e:
        logger.warning("[SCRAPE] ✖ query=%r failed (TypeError): %s", query, e)
        return []
    except Exception as e:
        logger.warning("[SCRAPE] ✖ query=%r failed: %s", query, e)
        return []
    finally:
        stop_heartbeat.set()

    elapsed = time.time() - start
    if elapsed > MAX_QUERY_SECONDS:
        logger.warning(
            "[SCRAPE] ⚠ query=%r exceeded %ds (elapsed=%.1fs)",
            query,
            MAX_QUERY_SECONDS,
            elapsed,
        )
    records = _normalize_jobs(jobs)

    logger.info(
        "[SCRAPE] ✔ finished query=%r rows=%d time=%.1fs",
        query,
        len(records),
        elapsed,
    )

    return records


# --------------------------------------------------
# Public API
# --------------------------------------------------
def scrape(
    *,
    ctx,
    search: str,
    hours_old: int,
    force_refresh: bool,
) -> pd.DataFrame:
    """
    Scrape jobs for a given user/use_case/search string.

    Rules:
    - Each query is independent
    - Partial failure is allowed
    - Empty result is valid
    """
    queries = [q.strip() for q in search.split("|") if q.strip()]
    if not queries:
        logger.warning("[SCRAPE] No queries parsed from search string")
        return pd.DataFrame()

    scraping_cfg = ctx.config.get("scraping", {})
    all_rows: List[dict] = []

    logger.info(
        "[SCRAPE] Starting scrape: queries=%d workers=%d",
        len(queries),
        min(len(queries), MAX_WORKERS),
    )
    logger.info(
        "[SCRAPE] Config: sites=%s max_results=%s force_refresh=%s",
        scraping_cfg.get("sites", {}).get("enabled"),
        scraping_cfg.get("max_results"),
        force_refresh,
    )

    # --------------------------------------------------
    # Parallel scraping (bounded)
    # --------------------------------------------------
    with ThreadPoolExecutor(max_workers=min(len(queries), MAX_WORKERS)) as pool:
        futures = {
            pool.submit(
                _scrape_single_query,
                query=q,
                scraping_cfg=scraping_cfg,
                hours_old=hours_old,
            ): q
            for q in queries
        }

        for fut in as_completed(futures):
            query = futures[fut]
            try:
                rows = fut.result(timeout=MAX_QUERY_SECONDS + 10)
            except Exception as e:
                logger.warning(
                    "[SCRAPE] ✖ query=%r raised exception or timeout: %s",
                    query,
                    e,
                )
                continue

            if not rows:
                logger.info("[SCRAPE] query=%r yielded no rows", query)
                continue

            all_rows.extend(rows)

    if not all_rows:
        logger.warning("[SCRAPE] No rows collected from any query")
        return pd.DataFrame()

    # --------------------------------------------------
    # Normalize + filter
    # --------------------------------------------------
    df = pd.DataFrame.from_records(all_rows)
    if df.empty:
        return df

    # Normalize common fields
    for col in ("title", "company", "description", "location"):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    # Minimum description length
    df = df[df["description"].str.len() >= MIN_DESC_LEN]

    # Ensure direct URL column exists
    if "job_url_direct" not in df.columns:
        df["job_url_direct"] = None

    # Deduplicate by canonical job URL if present
    if "job_url" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=["job_url"])
        logger.info(
            "[SCRAPE] Deduplicated by job_url: kept %d / %d",
            len(df),
            before,
        )

    # Optional hard title blocklist (scrape-time)
    blocklist = ctx.config.get("ranking", {}).get("hard_title_blocklist", [])
    if blocklist:
        rx = re.compile(
            r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)),
            re.IGNORECASE,
        )
        before = len(df)
        df = df[~df["title"].str.contains(rx, na=False)]
        logger.info(
            "[SCRAPE] Title blocklist applied: kept %d / %d",
            len(df),
            before,
        )

    df = df.reset_index(drop=True)

    logger.info("[SCRAPE] Final rows=%d", len(df))
    return df
