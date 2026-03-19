# ================================
# FILE: scrape_jobs.py
# ================================
"""
Deterministic, observable JobSpy-based scraper.

Guarantees:
- Per-query + per-site accounting (raw → kept → meta)
- No silent ingestion of junk rows
- Google Jobs recency phrasing handled explicitly
- Structured scrape diagnostics for UI
- Zero caching, zero ranking logic
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd
from config_loader import settings
from jobspy import scrape_jobs
from llm.classify_role import classify_roles_batch
from llm.plan_search import plan_search_queries
from profiles import Profile

# Silence JobSpy noise
logging.getLogger("JobSpy").setLevel(logging.WARNING)

SCRAPE_CFG = settings.scraping


# --------------------------------------------------
# Data contracts
# --------------------------------------------------
@dataclass
class SiteResult:
    site: str
    raw: int
    kept: int
    meta_only: int
    status: str  # ok | pruned | empty | blocked


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("title", "company", "description", "location"):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    return df


def _coerce_jobs(jobs):
    if jobs is None:
        return None
    if isinstance(jobs, pd.DataFrame):
        return None if jobs.empty else jobs
    if isinstance(jobs, list):
        return None if not jobs else pd.DataFrame(jobs)
    return None


def _google_recency_phrase(hours_old: int) -> str:
    if hours_old <= 24:
        return "in last 1 day"
    if hours_old <= 168:
        return f"in last {max(1, hours_old // 24)} days"
    if hours_old <= 720:
        return f"in last {max(1, hours_old // 168)} weeks"
    return f"in last {max(1, hours_old // 720)} months"


# --------------------------------------------------
# MAIN ENTRY
# --------------------------------------------------
def fetch_jobs(
    *,
    search_query: str,
    country: str,
    hours_old: int,
    remote_only: bool,
    profile: Profile,
    effective_settings: dict,
    force_refresh: bool = False,
    results_wanted: int = 150,
    sites: Optional[List[str]] = None,
    logger=None,
    view_mode: bool = False,
) -> pd.DataFrame:
    logger = logger or logging.getLogger(__name__)

    logger.info("[SCRAPE] Planning search queries")

    # ----------------------------------------------
    # Query planning
    # ----------------------------------------------
    base_queries = (
        plan_search_queries(search_query, effective_settings=effective_settings)
        if profile.use_llm_search
        else [search_query]
    )

    if not base_queries:
        logger.warning("[SCRAPE] No queries produced")
        return pd.DataFrame()

    # ----------------------------------------------
    # Site resolution
    # ----------------------------------------------
    country_key = country.lower()
    sites_cfg = settings.scraping.sites

    default_sites = (
        list(sites_cfg.india.enabled)
        if country_key == "india"
        else list(sites_cfg["global"].enabled)
    )

    active_sites = sites or default_sites
    country_indeed = "India" if country_key == "india" else None

    all_dfs: List[pd.DataFrame] = []

    scrape_report = {
        "generated_at": datetime.utcnow().isoformat(),
        "queries": [],
        "by_site": {},
    }

    # ----------------------------------------------
    # Execute per query
    # ----------------------------------------------
    for raw_q in base_queries:
        logger.info(f"[QUERY] {raw_q}")
        per_query: List[SiteResult] = []

        for site in active_sites:
            try:
                mp = site in {"indeed", "glassdoor"} and SCRAPE_CFG.use_multiprocessing

                common = dict(
                    site_name=[site],
                    results_wanted=results_wanted,
                    verbose=0,
                    use_multiprocessing=mp,
                )

                if site in {"indeed", "glassdoor"}:
                    jobs = scrape_jobs(
                        **common,
                        search_term=raw_q,
                        location=country,
                        hours_old=hours_old,
                        country_indeed=country_indeed,
                    )

                elif site == "linkedin":
                    jobs = scrape_jobs(
                        **common,
                        search_term=raw_q,
                        location=country,
                    )

                elif site == "google":
                    google_q = f"{raw_q} {_google_recency_phrase(hours_old)}"
                    jobs = scrape_jobs(
                        **common,
                        google_search_term=google_q,
                    )

                else:
                    continue

            except Exception as e:
                logger.warning(f"[SCRAPE] {site} blocked: {e}")
                per_query.append(SiteResult(site, 0, 0, 0, "blocked"))
                continue

            df = _coerce_jobs(jobs)
            raw = len(jobs) if jobs is not None else 0

            if df is None:
                per_query.append(SiteResult(site, raw, 0, 0, "empty"))
                continue

            df = _sanitize_df(df)

            full = df[df["description"].str.len() >= SCRAPE_CFG.min_description_length]
            meta = df[df["description"].str.len() < SCRAPE_CFG.min_description_length]

            kept = len(full)
            meta_only = len(meta)

            status = "ok" if (kept or meta_only) else "empty"

            # ---- KEEP BOTH ----
            if kept:
                full = full.copy()
                full["meta_only"] = False
                all_dfs.append(full)
                scrape_report["by_site"][site] = (
                    scrape_report["by_site"].get(site, 0) + kept
                )

            if meta_only:
                meta = meta.copy()
                meta["meta_only"] = True
                meta["description"] = meta["description"].fillna("")
                all_dfs.append(meta)

            # Explicit warning when raw > 0 but nothing usable
            if raw > 0 and kept == 0:
                logger.warning(
                    f"[SCRAPE] {site} returned {raw} jobs but 0 passed "
                    f"min_description_length={SCRAPE_CFG.min_description_length}"
                )

        # ---- per-query summary ----
        for r in per_query:
            logger.info(
                f"  {r.site:<10} raw={r.raw:<4} kept={r.kept:<4} "
                f"meta={r.meta_only:<4} status={r.status}"
            )

        scrape_report["queries"].append(
            {
                "query": raw_q,
                "results": [r.__dict__ for r in per_query],
            }
        )

    # ----------------------------------------------
    # Persist scrape diagnostics
    # ----------------------------------------------
    out_dir = os.path.join(settings.paths.cache_dir, "scrape_reports")
    os.makedirs(out_dir, exist_ok=True)

    with open(
        os.path.join(
            out_dir, f"scrape_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        ),
        "w",
    ) as f:
        json.dump(scrape_report, f, indent=2)

    if not all_dfs:
        logger.warning("[SCRAPE] No usable jobs collected")
        return pd.DataFrame()

    # ----------------------------------------------
    # Merge + dedupe
    # ----------------------------------------------
    df = (
        pd.concat(all_dfs, ignore_index=True)
        .drop_duplicates(subset=["job_url"])
        .reset_index(drop=True)
    )

    logger.info(f"[SCRAPE DIAG] raw_rows={df.shape[0]}")
    logger.info(f"[SCRAPE DIAG] post_filter_rows={len(df)}")

    # ----------------------------------------------
    # Role classification
    # ----------------------------------------------
    df["role"] = classify_roles_batch(df["title"].tolist(), logger=logger)

    if profile.skip_junior_roles:
        df = df[df["role"] != "junior"]
    if profile.skip_manager_roles:
        df = df[df["role"] != "manager"]

    for k in profile.exclude_keywords:
        df = df[
            ~(
                (df["title"] + " " + df["description"])
                .str.lower()
                .str.contains(re.escape(k), na=False)
            )
        ]

    return df.reset_index(drop=True)
