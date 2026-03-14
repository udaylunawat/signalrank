#!/usr/bin/env python3
"""
Merge all scraped_*, ranked_jobs_* CSVs into one deduplicated master CSV.

Usage:
    python scripts/merge_csvs.py [--output outputs/master_jobs.csv]

Deduplication uses job_url as the unique key. When duplicates exist,
the row with the most non-null columns is kept.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import pandas as pd


def find_csvs() -> list[Path]:
    """Find all relevant CSVs in root and outputs/ directories."""
    patterns = [
        "scraped_*_*.csv",
        "ranked_jobs_*.csv",
        "outputs/scraped_*_*.csv",
        "outputs/ranked_jobs_*.csv",
    ]
    files = []
    for pat in patterns:
        files.extend(Path(p) for p in glob.glob(pat))
    return sorted(set(files))


def merge(csv_files: list[Path], output: Path) -> pd.DataFrame:
    """Read, concat, deduplicate, and save."""
    frames = []
    for f in csv_files:
        try:
            df = pd.read_csv(f, dtype=str)
            df["_source_file"] = f.name
            frames.append(df)
            print(f"  {f.name}: {len(df)} rows, {len(df.columns)-1} cols")
        except Exception as e:
            print(f"  SKIP {f.name}: {e}")

    if not frames:
        print("No CSV files found to merge.")
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True, sort=False)
    print(f"\nTotal rows before dedup: {len(merged)}")

    # Deduplicate on job_url, keeping the row with the most data
    if "job_url" in merged.columns:
        merged["_filled"] = merged.notna().sum(axis=1)
        merged = merged.sort_values("_filled", ascending=False)
        merged = merged.drop_duplicates(subset=["job_url"], keep="first")
        merged = merged.drop(columns=["_filled"])
        print(f"Total rows after dedup:  {len(merged)}")

    output.parent.mkdir(exist_ok=True)
    merged.to_csv(output, index=False)
    print(f"\nSaved master CSV: {output} ({len(merged)} rows, {len(merged.columns)} cols)")
    return merged


def main():
    parser = argparse.ArgumentParser(description="Merge job CSVs into master file")
    parser.add_argument(
        "--output", "-o",
        default="outputs/master_jobs.csv",
        help="Output path (default: outputs/master_jobs.csv)",
    )
    args = parser.parse_args()

    csv_files = find_csvs()
    if not csv_files:
        print("No matching CSV files found.")
        return

    print(f"Found {len(csv_files)} CSV files:\n")
    output = Path(args.output)
    merge(csv_files, output)


if __name__ == "__main__":
    main()