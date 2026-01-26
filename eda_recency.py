#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

CSV = Path("outputs/ranked_jobs.csv")

if not CSV.exists():
    print("ranked_jobs.csv not found")
    exit(1)

df = pd.read_csv(CSV)

def age_days(d):
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None

df["age_days"] = df["date_posted"].apply(age_days)

print("\nRecency distribution (days):")
print(df["age_days"].describe())

print("\nBuckets:")
print(
    pd.cut(
        df["age_days"],
        bins=[-1, 3, 7, 14, 30, 60, 180, 10000],
        labels=["0-3", "4-7", "8-14", "15-30", "31-60", "61-180", "180+"],
    ).value_counts().sort_index()
)
