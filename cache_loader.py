# ================================
# FILE: cache_loader.py
# ================================
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

from config_loader import settings

# --------------------------------------------------
# CACHE DIRECTORY (USER / USE-CASE AWARE)
# --------------------------------------------------
CACHE_DIR = Path(
    os.environ.get(
        "JOBRANKER_CACHE_DIR",
        settings.paths.cache_dir,   # legacy fallback
    )
)

# --------------------------------------------------
# INTERNALS
# --------------------------------------------------
def _prune_cache(logger=None):
    """
    Remove expired or excess cached query files.
    Deterministic and idempotent.
    """
    if not CACHE_DIR.exists():
        return

    max_files = settings.cache.queries.max_files
    max_age = timedelta(hours=settings.cache.queries.max_age_hours)

    meta_files = sorted(
        CACHE_DIR.glob("query_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # --------------------------------
    # Age-based pruning
    # --------------------------------
    cutoff = datetime.now() - max_age

    for meta in meta_files:
        try:
            payload = json.loads(meta.read_text())
            ts = datetime.fromisoformat(payload["ts"])
            if ts < cutoff:
                csv = meta.with_suffix(".csv")
                meta.unlink(missing_ok=True)
                csv.unlink(missing_ok=True)
                if logger:
                    logger.info(f"[CACHE PRUNE] expired {meta.stem}")
        except Exception:
            continue

    # --------------------------------
    # Size-based pruning
    # --------------------------------
    meta_files = sorted(
        CACHE_DIR.glob("query_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for meta in meta_files[max_files:]:
        csv = meta.with_suffix(".csv")
        meta.unlink(missing_ok=True)
        csv.unlink(missing_ok=True)
        if logger:
            logger.info(f"[CACHE PRUNE] excess {meta.stem}")


def load_all_cached_jobs(logger=None) -> pd.DataFrame:
    """
    Load and merge all cached job CSVs.
    Applies pruning policy first.
    """
    if not CACHE_DIR.exists():
        if logger:
            logger.info(f"[CACHE] No cache dir at {CACHE_DIR}")
        return pd.DataFrame()

    _prune_cache(logger)

    csv_files = list(CACHE_DIR.glob("query_*.csv"))
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

    if logger and len(merged) > 500:
        logger.warning(
            f"Large cache detected: {len(merged)} jobs. "
            "Ranking may take several minutes."
        )

    return merged
