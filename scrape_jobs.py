import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import json
import re
import time
import random
import requests

from jobspy import scrape_jobs
from profiles import Profile
from llm.plan_search import plan_search_queries
from llm.classify_role import classify_roles_batch
from cache_loader import load_all_cached_jobs

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

CACHE_TTL_HOURS = 6

MAX_RETRIES = 3
BASE_BACKOFF = 2.0        # seconds
JITTER_RANGE = (0.3, 1.5) # seconds


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def _key(**k):
    return hashlib.md5(json.dumps(k, sort_keys=True).encode()).hexdigest()


def _now():
    return datetime.now().isoformat()


def _sleep_with_jitter(attempt: int, logger):
    delay = BASE_BACKOFF ** attempt + random.uniform(*JITTER_RANGE)
    logger.warning(f"Retrying after {delay:.2f}s (attempt {attempt})")
    time.sleep(delay)


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
    """
    Robust job fetch with:
    - per-query retries
    - jittered backoff
    - per-query caching
    - partial failure tolerance
    """

    # --------------------------------------------------
    # VIEW MODE
    # --------------------------------------------------
    if view_mode:
        logger.info("VIEW MODE enabled: loading cached jobs only")
        return load_all_cached_jobs(logger)

    # --------------------------------------------------
    # SEARCH PLANNING
    # --------------------------------------------------
    logger.info("Planning search queries")
    queries = (
        plan_search_queries(search_query)
        if profile.use_llm_search
        else [search_query]
    )

    if not queries:
        logger.warning("No queries planned; aborting fetch")
        return pd.DataFrame()

    logger.info(f"Planned {len(queries)} queries")

    # --------------------------------------------------
    # SITE SELECTION
    # --------------------------------------------------
    if country.lower() == "india":
        sites, country_indeed = ["indeed", "linkedin"], "India"
    else:
        sites, country_indeed = ["indeed", "linkedin"], None

    # --------------------------------------------------
    # SCRAPE PER QUERY (ISOLATED)
    # --------------------------------------------------
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

        # ---------- cache hit ----------
        if q_csv.exists() and q_meta.exists() and not force_refresh:
            ts = datetime.fromisoformat(json.loads(q_meta.read_text())["ts"])
            if datetime.now() - ts < timedelta(hours=CACHE_TTL_HOURS):
                logger.info(f"[CACHE HIT] {q}")
                try:
                    df_cached = pd.read_csv(q_csv)
                    if not df_cached.empty:
                        all_dfs.append(df_cached)
                        continue
                except Exception as e:
                    logger.debug(f"Cache read failed for {q}: {e}")

        # ---------- scrape with retries ----------
        logger.info(f"[SCRAPE] {q}")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                jobs = scrape_jobs(
                    site_name=sites,
                    search_term=q,
                    location=country,
                    hours_old=hours_old,
                    is_remote=remote_only,
                    results_wanted=results_wanted,
                    country_indeed=country_indeed,
                    verbose=0,
                )

                # normalize JobSpy return
                if jobs is None:
                    raise ValueError("JobSpy returned None")

                if isinstance(jobs, list):
                    if not jobs:
                        logger.warning(f"[EMPTY] {q}")
                        break
                    df = pd.DataFrame(jobs)

                elif isinstance(jobs, pd.DataFrame):
                    if jobs.empty:
                        logger.warning(f"[EMPTY] {q}")
                        break
                    df = jobs.copy()

                else:
                    raise TypeError(f"Unknown JobSpy return type: {type(jobs)}")

                # minimal sanity
                for col in ["title", "description", "company", "job_url"]:
                    df[col] = df.get(col, "").astype(str)

                df = df[df["description"].str.len() > 30]

                if df.empty:
                    logger.warning(f"[FILTERED EMPTY] {q}")
                    break

                # save per-query cache immediately
                q_csv.write_text(df.to_csv(index=False))
                q_meta.write_text(json.dumps({"ts": _now()}))

                logger.info(f"[SUCCESS] {q} → {len(df)} jobs")
                all_dfs.append(df)
                break  # success, exit retry loop

            except (requests.exceptions.RequestException, TimeoutError) as e:
                logger.warning(f"[TIMEOUT] {q}: {e}")
                if attempt < MAX_RETRIES:
                    _sleep_with_jitter(attempt, logger)
                else:
                    logger.error(f"[GIVE UP] {q}")

            except Exception as e:
                logger.error(f"[ERROR] {q}: {e}")
                break  # non-retryable

    # --------------------------------------------------
    # MERGE RESULTS
    # --------------------------------------------------
    if not all_dfs:
        logger.error("All queries failed; returning empty result")
        return pd.DataFrame()

    df = (
        pd.concat(all_dfs, ignore_index=True)
        .drop_duplicates(subset=["job_url"])
        .reset_index(drop=True)
    )

    # --------------------------------------------------
    # ROLE CLASSIFICATION
    # --------------------------------------------------
    logger.info("Classifying role intent (batched LLM)")
    df["role"] = classify_roles_batch(
        df["title"].tolist(),
        batch_size=10,
        logger=logger,
    )

    if profile.skip_junior_roles:
        df = df[df["role"] != "junior"]
    if profile.skip_manager_roles:
        df = df[df["role"] != "manager"]

    # --------------------------------------------------
    # KEYWORD EXCLUSIONS
    # --------------------------------------------------
    text = (df["title"] + " " + df["description"]).str.lower()
    for k in profile.exclude_keywords:
        df = df[~text.str.contains(re.escape(k))]

    logger.info(f"Final job count after filtering: {len(df)}")
    return df