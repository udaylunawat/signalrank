import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from jobspy import scrape_jobs

CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "jobs_cache.csv"
CACHE_TTL_HOURS = 6  # configurable


def is_cache_valid() -> bool:
    if not CACHE_FILE.exists():
        return False

    modified_time = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime)
    return datetime.now() - modified_time < timedelta(hours=CACHE_TTL_HOURS)


def load_cache() -> pd.DataFrame:
    return pd.read_csv(CACHE_FILE)


def save_cache(df: pd.DataFrame):
    CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(CACHE_FILE, index=False)


def fetch_jobs(force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and is_cache_valid():
        print("Using cached jobs...")
        return load_cache()

    print("Scraping fresh jobs...")
    jobs = scrape_jobs(
        site_name=["linkedin", "indeed", "glassdoor"],
        search_term=(
            '"machine learning engineer" OR "senior ai engineer" '
            'OR "generative ai engineer" OR "mlops engineer" -intern -junior'
        ),
        location="India",
        results_wanted=150,
        hours_old=48,
        country_indeed="India",
        linkedin_fetch_description=True,
        is_remote=False,
        verbose=1,
    )

    df = pd.DataFrame(jobs)
    df = df.dropna(subset=["description"])

    save_cache(df)
    return df