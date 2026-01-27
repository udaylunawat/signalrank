# ================================
# FILE: scrape_jobs.py
# ================================
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import json
import re
import logging
import os

from jobspy import scrape_jobs

from profiles import Profile
from llm.plan_search import plan_search_queries
from llm.classify_role import classify_roles_batch
from cache_loader import load_all_cached_jobs
from config_loader import settings
from scrapers.linkedin_api import LinkedInRapidAPIScraper

logging.getLogger("JobSpy").setLevel(logging.INFO)

# --------------------------------------------------
# CACHE (USER-SCOPED)
# --------------------------------------------------
CACHE_DIR = Path(
    os.environ.get(
        "JOBRANKER_CACHE_DIR",
        settings.paths.cache_dir,
    )
)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SCRAPE_CFG = settings.scraping

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def _key(**k):
    return hashlib.md5(json.dumps(k, sort_keys=True).encode()).hexdigest()

def _linkedin_cache_key(*, endpoint, title, location):
    return _key(
        source="linkedin_api",
        endpoint=endpoint,
        title=re.sub(r'\s+', ' ', title.lower()),
        location=location.lower(),
    )

def compile_linkedin_queries(queries: list[str]) -> list[str]:
    """
    Collapse expanded queries into OR-based LinkedIn-safe clusters.
    Deterministic, conservative.
    """

    clusters = {}

    for q in queries:
        base = q.lower()

        if "mlops" in base:
            clusters.setdefault("mlops", []).append(q)
        elif "llmops" in base or "genai" in base:
            clusters.setdefault("genai", []).append(q)
        elif "software engineer" in base or "swe" in base:
            clusters.setdefault("swe", []).append(q)
        else:
            clusters.setdefault(base, []).append(q)

    compiled = []

    for _, group in clusters.items():
        uniq = sorted(set(group))
        if len(uniq) == 1:
            compiled.append(uniq[0])
        else:
            joined = " OR ".join(f'"{q}"' for q in uniq[:3])
            compiled.append(joined)

    return compiled

def _now():
    return datetime.now().isoformat()


def _coerce_jobs(jobs):
    if jobs is None:
        return None
    if isinstance(jobs, pd.DataFrame):
        return None if jobs.empty else jobs
    if isinstance(jobs, list):
        return None if not jobs else pd.DataFrame(jobs)
    return None

def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize job rows defensively.
    Prevents NoneType crashes from upstream scrapers.
    """
    for col in ["title", "company", "description", "location"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    return df

def _append_and_flush(df: pd.DataFrame, csv_path: Path, meta_path: Path, logger):
    if df is None or df.empty:
        return

    if csv_path.exists():
        existing = pd.read_csv(csv_path)
        df = (
            pd.concat([existing, df], ignore_index=True)
            .drop_duplicates(subset=["job_url"])
            .reset_index(drop=True)
        )

    csv_path.write_text(df.to_csv(index=False))
    meta_path.write_text(json.dumps({"ts": _now()}))
    if logger:
        logger.info(f"[FLUSH] cache updated → {len(df)} jobs")


# --------------------------------------------------
# MAIN
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
    logger=None,
    view_mode: bool = False,
) -> pd.DataFrame:

    # --------------------------------------------------
    # LinkedIn API config (MUST be resolved first)
    # --------------------------------------------------
    api_cfg = settings.scraping.linkedin_api
    max_api_calls = getattr(api_cfg, "max_calls_per_run", 10)
    api_calls_used = 0

    if view_mode:
        return load_all_cached_jobs(logger)

    logger.info("Planning search queries")

    queries = (
        plan_search_queries(
            search_query,
            effective_settings=effective_settings,
        )
        if profile.use_llm_search
        else [search_query]
    )

    logger.info(f"Planned {len(queries)} queries")
    if not queries:
        return pd.DataFrame()

    # --------------------------------------------------
    # SITE SELECTION (CONFIG-DRIVEN)
    # --------------------------------------------------
    country_key = country.lower()
    sites_cfg = settings.scraping.sites

    if country_key == "india":
        sites = list(sites_cfg.india.enabled)
        country_indeed = "India"
    else:
        sites = list(sites_cfg["global"].enabled)
        country_indeed = None

    all_dfs = []

    # --------------------------------------------------
    # JobSpy sources
    # --------------------------------------------------
    for q in queries:
        for site in sites:
            q_key = _key(
                q=q,
                site=site,
                country=country,
                hours=hours_old,
                remote=remote_only,
                profile=profile.name,
            )

            q_csv = CACHE_DIR / f"query_{q_key}.csv"
            q_meta = CACHE_DIR / f"query_{q_key}.json"

            if q_csv.exists() and q_meta.exists() and not force_refresh:
                try:
                    ts = datetime.fromisoformat(
                        json.loads(q_meta.read_text())["ts"]
                    )
                    if datetime.now() - ts < timedelta(
                        hours=SCRAPE_CFG.cache_ttl_hours
                    ):
                        df = pd.read_csv(q_csv)
                        all_dfs.append(df)
                        continue
                except Exception:
                    pass

            logger.info(f"[SCRAPE] {site} :: {q}")

            try:
                jobs = scrape_jobs(
                    site_name=[site],
                    search_term=q,
                    location=country,
                    hours_old=hours_old,
                    is_remote=remote_only,
                    results_wanted=results_wanted,
                    country_indeed=country_indeed if site == "indeed" else None,
                    use_multiprocessing=SCRAPE_CFG.use_multiprocessing,
                    verbose=1,
                )
            except Exception as e:
                if logger:
                    logger.warning(f"[{site.upper()} ERROR] {e}")
                continue

            df = _coerce_jobs(jobs)
            if df is not None:
                df = df.fillna("")
                df = df[
                    df["description"].str.len()
                    >= SCRAPE_CFG.min_description_length
                ]
                if not df.empty:
                    _append_and_flush(df, q_csv, q_meta, logger)
                    all_dfs.append(df)

    # --------------------------------------------------
    # LinkedIn RapidAPI (budget + cache + compiled queries)
    # --------------------------------------------------
    api_key = os.environ.get("RAPIDAPI_KEY")

    if api_cfg.enabled and api_key:
        scraper = LinkedInRapidAPIScraper(
            api_key=api_key,
            cfg=api_cfg,
            logger=logger,
        )

        linkedin_queries = compile_linkedin_queries(queries)

        for q in linkedin_queries:
            if api_calls_used >= max_api_calls:
                if logger:
                    logger.warning(
                        f"[LINKEDIN_API] Budget exhausted "
                        f"({api_calls_used}/{max_api_calls}), stopping"
                    )
                break

            for endpoint in api_cfg.sources:
                cache_key = _linkedin_cache_key(
                    endpoint=endpoint,
                    title=q,
                    location=country,
                )

                q_csv = CACHE_DIR / f"query_{cache_key}.csv"
                q_meta = CACHE_DIR / f"query_{cache_key}.json"

                if q_csv.exists() and q_meta.exists() and not force_refresh:
                    try:
                        ts = datetime.fromisoformat(
                            json.loads(q_meta.read_text())["ts"]
                        )
                        if datetime.now() - ts < timedelta(
                            hours=SCRAPE_CFG.cache_ttl_hours
                        ):
                            df = pd.read_csv(q_csv)
                            all_dfs.append(df)
                            continue
                    except Exception:
                        pass

                try:
                    api_jobs = scraper.search(
                        title=q,
                        location=country,
                    )

                    api_calls_used += 1

                    if api_jobs:
                        df_api = pd.DataFrame(api_jobs)
                        _append_and_flush(df_api, q_csv, q_meta, logger)
                        all_dfs.append(df_api)

                except Exception as e:
                    if logger:
                        logger.warning(f"[LINKEDIN_API SKIP] {e}")

    if not all_dfs:
        return pd.DataFrame()

    # --------------------------------------------------
    # Merge + filters
    # --------------------------------------------------
    df = (
        pd.concat(all_dfs, ignore_index=True)
        .drop_duplicates(subset=["job_url"])
        .reset_index(drop=True)
    )

    roles = classify_roles_batch(df["title"].tolist(), logger=logger)
    df["role"] = roles

    if profile.skip_junior_roles:
        df = df[df["role"] != "junior"]
    if profile.skip_manager_roles:
        df = df[df["role"] != "manager"]

    for k in profile.exclude_keywords:
        mask = (
            (df["title"] + " " + df["description"])
            .str.lower()
            .str.contains(re.escape(k), na=False)
        )
        df = df.loc[~mask]

    return df