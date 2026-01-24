import pandas as pd
from pathlib import Path
import json


CACHE_DIR = Path("cache")


def load_all_cached_jobs(logger=None) -> pd.DataFrame:
    """
    Load and merge all cached job CSVs.
    Scraping is completely bypassed.
    """
    csv_files = list(CACHE_DIR.glob("*.csv"))

    if not csv_files:
        if logger:
            logger.warning("No cached job files found")
        return pd.DataFrame()

    dfs = []
    for csv in csv_files:
        try:
            df = pd.read_csv(csv)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            if logger:
                logger.debug(f"Failed to read cache file {csv}: {e}")

    if not dfs:
        return pd.DataFrame()

    merged = (
        pd.concat(dfs, ignore_index=True)
        .drop_duplicates(subset=["job_url"], keep="first")
        .reset_index(drop=True)
    )

    if logger:
        logger.info(f"Loaded {len(merged)} jobs from cache")

    return merged