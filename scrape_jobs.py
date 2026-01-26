# ================================
# FILE: scrape_jobs.py
# ================================
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import json
import re
import time
import logging

logging.getLogger("JobSpy").setLevel(logging.INFO)

from jobspy import scrape_jobs
from profiles import Profile
from llm.plan_search import plan_search_queries
from llm.classify_role import classify_roles_batch
from cache_loader import load_all_cached_jobs

# --------------------------------------------------
# SITE CONFIG
# --------------------------------------------------
LINKEDIN_SLEEP_SECONDS = 12
LINKEDIN_MAX_PAGES = 8
INDEED_HEARTBEAT_SECONDS = 15

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL_HOURS = 6

# --------------------------------------------------
# HARD TITLE BLOCKLIST (NON-NEGOTIABLE)
# --------------------------------------------------
TITLE_BLOCKLIST = [
    r"\bmanager\b",
    r"\bprincipal\b",
]

TITLE_BLOCK_RE = re.compile("|".join(TITLE_BLOCKLIST), re.IGNORECASE)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def _key(**k):
    return hashlib.md5(json.dumps(k, sort_keys=True).encode()).hexdigest()

def _now():
    return datetime.now().isoformat()

def _rate_limit_site(site: str, page: int, logger):
    if site == "linkedin":
        if page >= LINKEDIN_MAX_PAGES:
            raise StopIteration("LinkedIn page cap reached")
        logger.info(f"[RATE LIMIT] LinkedIn sleep {LINKEDIN_SLEEP_SECONDS}s (page {page})")
        time.sleep(LINKEDIN_SLEEP_SECONDS)

def _build_site_query(raw_query: str, site: str) -> str | None:
    raw_query = raw_query.strip()

    if site == "google":
        from llm.plan_search import is_google_style_query
        return raw_query if is_google_style_query(raw_query) else None

    if site == "linkedin":
        return raw_query.replace('"', "").replace(" OR ", " ")

    return raw_query

def _coerce_jobs(jobs):
    if jobs is None:
        return None

    if isinstance(jobs, pd.DataFrame):
        return None if jobs.empty else jobs

    if isinstance(jobs, list):
        return None if not jobs else pd.DataFrame(jobs)

    return None

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
    force_refresh: bool = False,
    results_wanted: int = 150,
    logger=None,
    view_mode: bool = False,
) -> pd.DataFrame:

    if view_mode:
        return load_all_cached_jobs(logger)

    logger.info("Planning search queries")

    queries = (
        plan_search_queries(search_query)
        if profile.use_llm_search
        else [search_query]
    )

    logger.info(f"Planned {len(queries)} queries")

    if not queries:
        return pd.DataFrame()

    if country.lower() == "india":
        sites = ["indeed", "glassdoor", "linkedin"] # "glassdoor", "linkedin", "google"]
        country_indeed = "India"
    else:
        sites = ["indeed", "glassdoor", "linkedin", "google"]
        country_indeed = None

    all_dfs = []

    for q in queries:
        q_key = _key(
            q=q,
            country=country,
            hours=hours_old,
            remote=remote_only,
            profile=profile.name,
        )

        q_csv = CACHE_DIR / f"query_{q_key}.csv"
        q_meta = CACHE_DIR / f"query_{q_key}.json"

        if q_csv.exists() and q_meta.exists() and not force_refresh:
            ts = datetime.fromisoformat(json.loads(q_meta.read_text())["ts"])
            if datetime.now() - ts < timedelta(hours=CACHE_TTL_HOURS):
                df = pd.read_csv(q_csv)
                all_dfs.append(df)
                continue

        logger.info(f"[SCRAPE] {q}")

        try:
            jobs = scrape_jobs(
                site_name=["indeed"],
                search_term=q,
                location=country,
                hours_old=hours_old,
                is_remote=remote_only,
                results_wanted=results_wanted,
                country_indeed=country_indeed,
                use_multiprocessing=True,
                verbose=1,
            )

            df = _coerce_jobs(jobs)
            if df is not None:
                df = df[df["description"].astype(str).str.len() >= 500]
                _append_and_flush(df, q_csv, q_meta, logger)
                all_dfs.append(df)

        except Exception as e:
            logger.warning(f"[INDEED ERROR] {e}")

    if not all_dfs:
        return pd.DataFrame()

    df = (
        pd.concat(all_dfs, ignore_index=True)
        .drop_duplicates(subset=["job_url"])
        .reset_index(drop=True)
    )

    # --------------------------------------------------
    # ROLE CLASSIFICATION (JUNIOR / MANAGER)
    # --------------------------------------------------
    roles = classify_roles_batch(df["title"].tolist(), logger=logger)
    df["role"] = roles

    if profile.skip_junior_roles:
        df = df[df["role"] != "junior"]
    if profile.skip_manager_roles:
        df = df[df["role"] != "manager"]

    # --------------------------------------------------
    # HARD TITLE BLOCK (MANAGER / PRINCIPAL)
    # --------------------------------------------------
    before = len(df)
    df = df[~df["title"].astype(str).str.contains(TITLE_BLOCK_RE)]
    after = len(df)

    if logger and before != after:
        logger.info(
            f"[FILTER] Dropped {before - after} Manager/Principal roles (hard block)"
        )

    # --------------------------------------------------
    # KEYWORD EXCLUSIONS
    # --------------------------------------------------
    for k in profile.exclude_keywords:
        mask = (
            (df["title"] + " " + df["description"])
            .str.lower()
            .str.contains(re.escape(k), na=False)
        )
        df = df.loc[~mask]

    return df

