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
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import pandas as pd
from dotenv import load_dotenv
from jobspy import scrape_jobs

from job_ranker.scrapers.linkedin_api import LinkedInRapidAPIScraper

load_dotenv()
logger = logging.getLogger(__name__)

# Concurrency
MAX_WORKERS = 4
DEFAULT_RESULTS_WANTED = 25
MIN_DESC_LEN = 20

# Observability / safety
MAX_QUERY_SECONDS = 180
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

def _scrape_single_query_rapidapi(
    *,
    query: str,
    ctx,
    hours_old: int,
) -> List[dict]:
    """
    Run a single query using RapidAPI-based scrapers.

    This replaces JobSpy but keeps the same contract:
    returns list[dict], fail-soft.
    """
    cfg = ctx.config
    rapidapi_key = os.getenv("RAPIDAPI_KEY")

    if not rapidapi_key:
        logger.warning("[SCRAPE] RAPIDAPI_KEY missing, skipping RapidAPI scrape")
        return []

    max_results = cfg.get("scraping", {}).get("max_results", 100)

    scraper = LinkedInRapidAPIScraper(
        api_key=rapidapi_key,
        cfg=cfg,
        logger=logger,
    )

    logger.info("[SCRAPE] ▶ RapidAPI query=%r max_results=%d", query, max_results)

    try:
        rows = scraper.search(
            title=query,
            location=cfg.get("scraping", {}).get("country", "India"),
            cfg=cfg,
            max_results=max_results,
        )
    except Exception as e:
        logger.warning("[SCRAPE] ✖ RapidAPI query=%r failed: %s", query, e)
        return []

    logger.info(
        "[SCRAPE] ✔ RapidAPI finished query=%r rows=%d",
        query,
        len(rows),
    )
    return rows

def _scrape_single_query_jobspy(
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

    logger.info("[SCRAPE] ▶ JobSpy starting query=%r", query)

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
        logger.warning("[SCRAPE] ✖ JobSpy query=%r failed (TypeError): %s", query, e)
        return []
    except Exception as e:
        logger.warning("[SCRAPE] ✖ JobSpy query=%r failed: %s", query, e)
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
        "[SCRAPE] ✔ JobSpy finished query=%r rows=%d time=%.1fs",
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

    Strategy:
    1. Try RapidAPI first (reliable, no IP blocking)
    2. Fall back to JobSpy if RapidAPI yields nothing
    """
    queries = [q.strip() for q in search.split("|") if q.strip()]
    if not queries:
        logger.warning("[SCRAPE] No queries parsed from search string")
        return pd.DataFrame()

    scraping_cfg = ctx.config.get("scraping", {})
    has_rapidapi = bool(os.getenv("RAPIDAPI_KEY"))
    all_rows: List[dict] = []

    logger.info(
        "[SCRAPE] Starting scrape: queries=%d workers=%d rapidapi=%s",
        len(queries),
        min(len(queries), MAX_WORKERS),
        has_rapidapi,
    )
    logger.info(
        "[SCRAPE] Config: sites=%s max_results=%s force_refresh=%s",
        scraping_cfg.get("sites", {}).get("enabled"),
        scraping_cfg.get("max_results"),
        force_refresh,
    )

    # --------------------------------------------------
    # Phase 1: RapidAPI (primary)
    # --------------------------------------------------
    failed_queries = []

    if has_rapidapi:
        workers = min(len(queries), MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _scrape_single_query_rapidapi,
                    query=q,
                    ctx=ctx,
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
                        "[SCRAPE] ✖ RapidAPI query=%r exception: %s", query, e
                    )
                    failed_queries.append(query)
                    continue

                if not rows:
                    logger.info(
                        "[SCRAPE] RapidAPI query=%r yielded no rows", query
                    )
                    failed_queries.append(query)
                    continue

                all_rows.extend(rows)
                logger.info(
                    "[SCRAPE] ✔ query=%r collected %d rows", query, len(rows)
                )
    else:
        failed_queries = list(queries)

    # --------------------------------------------------
    # Phase 2: JobSpy fallback for failed queries
    # --------------------------------------------------
    if failed_queries:
        logger.info(
            "[SCRAPE] JobSpy fallback for %d queries: %s",
            len(failed_queries),
            failed_queries,
        )
        with ThreadPoolExecutor(max_workers=min(len(failed_queries), MAX_WORKERS)) as pool:
            futures = {
                pool.submit(
                    _scrape_single_query_jobspy,
                    query=q,
                    scraping_cfg=scraping_cfg,
                    hours_old=hours_old,
                ): q
                for q in failed_queries
            }

            for fut in as_completed(futures):
                query = futures[fut]
                try:
                    rows = fut.result(timeout=MAX_QUERY_SECONDS + 10)
                except Exception as e:
                    logger.warning(
                        "[SCRAPE] ✖ JobSpy query=%r exception: %s", query, e
                    )
                    continue

                if rows:
                    all_rows.extend(rows)
                    logger.info(
                        "[SCRAPE] ✔ JobSpy query=%r collected %d rows",
                        query,
                        len(rows),
                    )

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

    df.to_csv(f"scraped_{ctx.user}_{ctx.use_case}_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.csv", index=False)

    return df
