#!/usr/bin/env python3
import sys
from pathlib import Path

# --------------------------------------------------
# Ensure project root is on PYTHONPATH
# --------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import json
from datetime import datetime
from logger import setup_logger

logger = setup_logger()

CACHE_DIR = PROJECT_ROOT / "cache"
CORPUS_DIR = PROJECT_ROOT / "corpus"
CORPUS_DIR.mkdir(exist_ok=True)

OUTPUT_PATH = CORPUS_DIR / "jobs_corpus.csv"

FALLBACK_COLS = ["company", "title", "location"]
DROP_IF_NULL = ["title", "company", "description"]


def normalize_date(val):
    try:
        return pd.to_datetime(val, utc=True).isoformat()
    except Exception:
        return None


def row_key(row):
    if pd.notna(row.get("job_url")) and row.get("job_url"):
        return row["job_url"].strip().lower()

    return "|".join(
        str(row.get(c, "")).strip().lower()
        for c in FALLBACK_COLS
    )


def main():
    csvs = list(CACHE_DIR.glob("query_*.csv"))

    if not csvs:
        logger.error("No cached query CSVs found")
        return

    logger.info(f"Loading {len(csvs)} cached CSVs")

    frames = []
    for p in csvs:
        try:
            df = pd.read_csv(p)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            logger.warning(f"Failed to read {p}: {e}")

    if not frames:
        logger.error("All cached CSVs empty or unreadable")
        return

    df = pd.concat(frames, ignore_index=True)

    # Drop broken rows
    for c in DROP_IF_NULL:
        df = df[df[c].notna()]

    logger.info(f"Rows before dedupe: {len(df)}")

    df["_dedupe_key"] = df.apply(row_key, axis=1)

    # Sort so newest scrape wins mutable fields
    if "date_posted" in df.columns:
        df["_date_norm"] = df["date_posted"].apply(normalize_date)
        df = df.sort_values("_date_norm", ascending=False)

    deduped = (
        df
        .drop_duplicates(subset="_dedupe_key", keep="first")
        .drop(columns=["_dedupe_key", "_date_norm"], errors="ignore")
        .reset_index(drop=True)
    )

    # Normalize date_posted
    if "date_posted" in deduped.columns:
        deduped["date_posted"] = deduped["date_posted"].apply(normalize_date)

    # Remove ranking-only columns
    for col in [
        "semantic_score",
        "company_weight",
        "low_priority_penalty",
        "final_score",
    ]:
        if col in deduped.columns:
            deduped.drop(columns=[col], inplace=True)

    deduped.to_csv(OUTPUT_PATH, index=False)

    logger.info(
        f"Corpus built: {len(deduped)} jobs → {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()