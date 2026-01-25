# cache_loader.py
import pandas as pd
from pathlib import Path
import json
from datetime import datetime, timedelta

CACHE_DIR = Path("cache")

# -----------------------------
# CACHE POLICY (TUNE HERE)
# -----------------------------
MAX_QUERY_FILES = 50          # hard cap
MAX_CACHE_AGE_HOURS = 72      # 3 days


def _prune_cache(logger=None):
    """
    Remove old or excess cached query files.
    Safe, deterministic, idempotent.
    """
    meta_files = sorted(
        CACHE_DIR.glob("query_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # ---- age-based pruning ----
    cutoff = datetime.now() - timedelta(hours=MAX_CACHE_AGE_HOURS)

    for meta in meta_files:
        try:
            ts = datetime.fromisoformat(
                json.loads(meta.read_text()).get("ts")
            )
            if ts < cutoff:
                csv = meta.with_suffix(".csv")
                meta.unlink(missing_ok=True)
                csv.unlink(missing_ok=True)
                if logger:
                    logger.info(f"[CACHE PRUNE] expired {meta.stem}")
        except Exception:
            continue

    # ---- size-based pruning ----
    meta_files = sorted(
        CACHE_DIR.glob("query_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for meta in meta_files[MAX_QUERY_FILES:]:
        csv = meta.with_suffix(".csv")
        meta.unlink(missing_ok=True)
        csv.unlink(missing_ok=True)
        if logger:
            logger.info(f"[CACHE PRUNE] excess {meta.stem}")


def load_all_cached_jobs(logger=None) -> pd.DataFrame:
    """
    Load and merge all cached job CSVs.
    Automatically prunes cache first.
    """
    if not CACHE_DIR.exists():
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