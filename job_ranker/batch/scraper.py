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

# Google Jobs uses JobSpy's built-in Google scraper (no separate import needed)

# Observability / safety
MAX_QUERY_SECONDS = 180
LOG_HEARTBEAT_SECONDS = 15

# JobSpy serialization: delay between sequential Indeed requests to avoid 403
JOBSPY_INTER_QUERY_DELAY = 3.0  # seconds between queries when serialized


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
    sites_override: list[str] | None = None,
) -> List[dict]:
    """
    Run a single JobSpy query (serialized, one at a time).

    sites_override: if provided, use this instead of config sites.
                    Typically ["indeed"] when jobspy_only=true.
    """
    sites = sites_override or scraping_cfg.get("sites", {}).get("enabled", ["indeed"])

    kwargs = {
        "site_name": sites,
        "search_term": query,
        "location": scraping_cfg.get("country", "India"),
        "country_indeed": scraping_cfg.get("country", "India"),
        "results_wanted": scraping_cfg.get(
            "max_results",
            DEFAULT_RESULTS_WANTED,
        ),
    }

    # hours_old is supported by the speedyapply fork but not vanilla python-jobspy.
    # Try with it first; if the version doesn't support it, retry without.
    if scraping_cfg.get("supports_hours_old", True) and hours_old:
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
        if "hours_old" in str(e) and "hours_old" in kwargs:
            # Installed JobSpy version doesn't support hours_old — retry without it
            logger.warning(
                "[SCRAPE] JobSpy version doesn't support hours_old — retrying without it. "
                "Install speedyapply fork for hours_old support."
            )
            kwargs.pop("hours_old")
            try:
                jobs = scrape_jobs(**kwargs)
            except Exception as e2:
                logger.warning("[SCRAPE] ✖ JobSpy query=%r failed on retry: %s", query, e2)
                return []
        else:
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

def _is_valid_api_key(key: str | None) -> bool:
    """Return True only if key looks like a real credential (not a placeholder)."""
    if not key:
        return False
    placeholders = {"dd", "sk-", "your_key", "xxx", "test", "none", "null", ""}
    return key.strip().lower() not in placeholders and len(key.strip()) > 8


def scrape(
    *,
    ctx,
    search: str,
    hours_old: int,
    force_refresh: bool,
    jobspy_only: bool = False,
) -> pd.DataFrame:
    """
    Scrape jobs for a given user/use_case/search string.

    Strategy depends on config `scraping.jobspy_only`:

    jobspy_only: true  → JobSpy (Indeed) + Google Jobs (if enabled in config).
                         Serialized, one query at a time with delay to avoid 403s.
                         No RapidAPI, no free APIs (Himalayas/Remotive/Jobicy).

    jobspy_only: false (default) → All sources in parallel:
        1. RapidAPI sources (if RAPIDAPI_KEY valid)
        2. JobSpy Indeed — serialized sequentially to avoid 403
        3. Free direct APIs (Himalayas, Remotive, Jobicy) — always run

    All phases run; results are merged and deduplicated.
    """
    queries = [q.strip() for q in search.split("|") if q.strip()]
    if not queries:
        logger.warning("[SCRAPE] No queries parsed from search string")
        return pd.DataFrame()

    scraping_cfg = ctx.config.get("scraping", {})
    jobspy_only = scraping_cfg.get("jobspy_only", False)
    rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
    has_rapidapi = _is_valid_api_key(rapidapi_key) and not jobspy_only
    all_rows: List[dict] = []

    logger.info(
        "[SCRAPE] Starting scrape: queries=%d jobspy_only=%s rapidapi=%s",
        len(queries),
        jobspy_only,
        has_rapidapi,
    )
    logger.info(
        "[SCRAPE] Config: sites=%s max_results=%s hours_old=%s force_refresh=%s",
        scraping_cfg.get("sites", {}).get("enabled"),
        scraping_cfg.get("max_results"),
        hours_old,
        force_refresh,
    )

    if jobspy_only:
        logger.info(
            "[SCRAPE] jobspy_only=true — skipping RapidAPI and free-API sources. "
            "Running JobSpy/Indeed sequentially + Google Jobs (if enabled)."
        )
        _run_jobspy_sequential(
            queries=queries,
            scraping_cfg=scraping_cfg,
            hours_old=hours_old,
            all_rows=all_rows,
            sites_override=["indeed"],
        )
        # Google Jobs is NOT a RapidAPI source — run it even in jobspy_only mode
        _scrape_google_jobs(queries, scraping_cfg, hours_old, all_rows)
        return _finalize(all_rows, scraping_cfg, ctx)

    # --------------------------------------------------
    # Phase 1: RapidAPI (optional, when key is valid)
    # --------------------------------------------------
    if not has_rapidapi:
        logger.warning(
            "[SCRAPE] ⚠ RAPIDAPI_KEY is missing or invalid — "
            "RapidAPI sources skipped. JobSpy + free APIs will still run."
        )
    else:
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
                    logger.warning("[SCRAPE] ✖ RapidAPI query=%r exception: %s", query, e)
                    continue
                if rows:
                    all_rows.extend(rows)
                    logger.info("[SCRAPE] ✔ RapidAPI query=%r collected %d rows", query, len(rows))
                else:
                    logger.info("[SCRAPE] RapidAPI query=%r yielded no rows", query)

    # --------------------------------------------------
    # Phase 2: JobSpy Indeed    # --------------------------------------------------
    # Phase 2: JobSpy Indeed — serialized to avoid 403
    # --------------------------------------------------
    _run_jobspy_sequential(
        queries=queries,
        scraping_cfg=scraping_cfg,
        hours_old=hours_old,
        all_rows=all_rows,
        sites_override=["indeed"],
    )

    # --------------------------------------------------
    # Phase 3: Free direct APIs — always run (no key needed)
    # --------------------------------------------------
    logger.info("[SCRAPE] Running free direct APIs (Himalayas, Remotive, Jobicy)")
    _free_scraper = LinkedInRapidAPIScraper(
        api_key="__no_key__",
        cfg=ctx.config,
        logger=logger,
    )
    for q in queries:
        try:
            rows_h = _free_scraper._search_himalayas(q, scraping_cfg.get("max_results", 50))
            rows_r = _free_scraper._search_remotive(q)
            rows_j = _free_scraper._search_jobicy(q)
            free_rows = rows_h + rows_r + rows_j
            if free_rows:
                all_rows.extend(free_rows)
                logger.info(
                    "[SCRAPE] ✔ Free APIs query=%r collected %d rows "
                    "(himalayas=%d remotive=%d jobicy=%d)",
                    q, len(free_rows), len(rows_h), len(rows_r), len(rows_j),
                )
        except Exception as e:
            logger.warning("[SCRAPE] ✖ Free APIs query=%r exception: %s", q, e)

    # --------------------------------------------------
    # Phase 4: Google Jobs (optional, residential IP only)
    # Enable via config: scraping.google_jobs.enabled: true
    # --------------------------------------------------
    _scrape_google_jobs(queries, scraping_cfg, hours_old, all_rows)

    return _finalize(all_rows, scraping_cfg, ctx)


def _run_jobspy_sequential(
    *,
    queries: List[str],
    scraping_cfg: dict,
    hours_old: int,
    all_rows: List[dict],
    sites_override: list[str] | None = None,
) -> None:
    """
    Run JobSpy queries one at a time (serialized) to avoid Indeed 403s.
    Adds JOBSPY_INTER_QUERY_DELAY seconds between each request.
    """
    logger.info(
        "[SCRAPE] JobSpy sequential phase: %d queries (delay=%.1fs between each)",
        len(queries),
        JOBSPY_INTER_QUERY_DELAY,
    )
    for i, q in enumerate(queries):
        if i > 0:
            logger.info("[SCRAPE] JobSpy inter-query delay %.1fs", JOBSPY_INTER_QUERY_DELAY)
            time.sleep(JOBSPY_INTER_QUERY_DELAY)
        try:
            rows = _scrape_single_query_jobspy(
                query=q,
                scraping_cfg=scraping_cfg,
                hours_old=hours_old,
                sites_override=sites_override,
            )
        except Exception as e:
            logger.warning("[SCRAPE] ✖ JobSpy query=%r exception: %s", q, e)
            continue
        if rows:
            all_rows.extend(rows)
            logger.info("[SCRAPE] ✔ JobSpy query=%r collected %d rows", q, len(rows))


def _scrape_google_jobs(
    queries: List[str],
    scraping_cfg: dict,
    hours_old: int,
    all_rows: List[dict],
) -> None:
    """
    Placeholder — Google Jobs scraping via Gmail Job Alerts (coming soon).
    Direct Google scraping is unreliable (blocked on all IPs).
    See: job_ranker/scrapers/gmail_alerts.py
    """
    google_cfg = scraping_cfg.get("google_jobs", {})
    if not google_cfg.get("enabled", False):
        return

    logger.info(
        "[SCRAPE] Google Jobs: direct scraping disabled (blocked). "
        "Use Gmail Job Alerts scraper instead — see SETUP.md."
    )


def _finalize(all_rows: List[dict], scraping_cfg: dict, ctx) -> pd.DataFrame:
    """
    Normalize, deduplicate, filter, and persist the collected rows.
    Shared by all scrape strategies.
    """
    if not all_rows:
        logger.warning("[SCRAPE] No rows collected from any query")
        return pd.DataFrame()

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

    # Deduplicate by canonical job URL
    if "job_url" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=["job_url"])
        logger.info("[SCRAPE] Deduplicated by job_url: kept %d / %d", len(df), before)

    # Optional hard title blocklist (scrape-time)
    blocklist = ctx.config.get("ranking", {}).get("hard_title_blocklist", [])
    if blocklist:
        rx = re.compile(
            r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)),
            re.IGNORECASE,
        )
        before = len(df)
        df = df[~df["title"].str.contains(rx, na=False)]
        logger.info("[SCRAPE] Title blocklist applied: kept %d / %d", len(df), before)

    df = df.reset_index(drop=True)
    logger.info("[SCRAPE] Final rows=%d", len(df))

    df.to_csv(
        f"scraped_{ctx.user}_{ctx.use_case}_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
        index=False,
    )
    return df
