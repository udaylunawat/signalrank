from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

# --------------------------------------------------
# Config
# --------------------------------------------------
CSV_FILES = [
    # "mlops_bangalore_jobs.csv",
    # "pune_mlops_jobs.csv",
    # "mlops_bengaluru_jobs.csv",
    "ranked_jobs_20260225_042519.csv"
]

DB_PATH = Path("job_ranker/duckdb")
USER = "example"
USE_CASE = "default"

# --------------------------------------------------
# Load & Merge
# --------------------------------------------------
def load_all_csvs(files):
    dfs = []
    for f in files:
        path = Path(f)
        if not path.exists():
            print(f"Skipping missing file: {f}")
            continue
        df = pd.read_csv(path)
        dfs.append(df)

    if not dfs:
        raise RuntimeError("No CSV files loaded.")

    return pd.concat(dfs, ignore_index=True)


# --------------------------------------------------
# Preprocessing
# --------------------------------------------------
def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Normalize text columns
    text_cols = ["title", "company", "description", "location", "site"]
    for col in text_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

    # Normalize date
    if "date_posted" in df.columns:
        df["date_posted"] = pd.to_datetime(
            df["date_posted"],
            errors="coerce",
            utc=True,
        )

    # Ensure job_url_direct exists
    if "job_url_direct" not in df.columns:
        df["job_url_direct"] = None

    # Remove clearly broken rows
    df = df[df["title"].str.len() > 3]
    df = df[df["description"].str.len() > 20]

    # --------------------------------------------------
    # Cross-file deduplication
    # --------------------------------------------------

    if "job_url" in df.columns:
        df = df.drop_duplicates(subset=["job_url"])
    else:
        df["_dedupe_key"] = (
            df["company"].str.lower()
            + "||"
            + df["title"].str.lower()
            + "||"
            + df["location"].str.lower()
        )
        df = df.drop_duplicates(subset=["_dedupe_key"])
        df = df.drop(columns="_dedupe_key")

    return df.reset_index(drop=True)


# --------------------------------------------------
# Insert into DuckDB
# --------------------------------------------------
def insert_into_duckdb(df: pd.DataFrame):
    con = duckdb.connect(str(DB_PATH))

    df["user"] = USER
    df["use_case"] = USE_CASE
    df["ingested_at"] = datetime.utcnow()

    # Ensure only valid columns are passed
    expected_cols = [
        "job_url",
        "job_url_direct",
        "title",
        "company",
        "description",
        "location",
        "site",
        "date_posted",
        "user",
        "use_case",
        "ingested_at",
    ]

    df = df[expected_cols]

    con.register("temp_jobs", df)

    con.execute("""
        INSERT INTO jobs_raw (
            job_url,
            job_url_direct,
            title,
            company,
            description,
            location,
            site,
            date_posted,
            user,
            use_case,
            ingested_at
        )
        SELECT * FROM temp_jobs
        ON CONFLICT (job_url, user, use_case)
        DO UPDATE SET
            job_url_direct = excluded.job_url_direct,
            title          = excluded.title,
            company        = excluded.company,
            description    = excluded.description,
            location       = excluded.location,
            site           = excluded.site,
            date_posted    = excluded.date_posted,
            ingested_at    = excluded.ingested_at
    """)

    con.close()


# --------------------------------------------------
# Main
# --------------------------------------------------
if __name__ == "__main__":
    print("Loading CSV files...")
    df = load_all_csvs(CSV_FILES)

    print(f"Loaded rows: {len(df)}")

    df = preprocess(df)

    print(f"After preprocessing & dedupe: {len(df)}")

    insert_into_duckdb(df)

    print("Done. Data inserted into DuckDB.")