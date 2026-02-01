# storage/store.py
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd


class Store:
    """
    DuckDB-backed storage spine (v2).

    RULES:
    - Single source of persistence
    - Immutable runs
    - No scoring logic
    - No LLM calls
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.con = duckdb.connect(str(db_path))
        self._init_schema()

    # --------------------------------------------------
    # Schema
    # --------------------------------------------------
    def _init_schema(self):
        schema_path = Path(__file__).parent / "schema.sql"
        self.con.execute(schema_path.read_text())

    # --------------------------------------------------
    # Runs
    # --------------------------------------------------
    def create_run(self, ctx) -> str:
        run_id = str(uuid.uuid4())
        self.con.execute(
            """
            INSERT INTO runs
            (run_id, user, use_case, config_fingerprint, started_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                ctx.user,
                ctx.use_case,
                ctx.config_fp,
                datetime.utcnow(),
                "running",
            ],
        )
        return run_id

    def finalize_run(self, run_id: str, status: str):
        self.con.execute(
            """
            UPDATE runs
            SET finished_at = ?, status = ?
            WHERE run_id = ?
            """,
            [datetime.utcnow(), status, run_id],
        )

    # --------------------------------------------------
    # Raw jobs
    # --------------------------------------------------
    def upsert_raw_jobs(self, df: pd.DataFrame, ctx):
        if df.empty:
            return

        df = df.copy()

        # --------------------------------------------------
        # HARD NORMALIZATION (DATE POSTED)
        # --------------------------------------------------
        if "date_posted" in df.columns:
            s = df["date_posted"]

            if pd.api.types.is_numeric_dtype(s):
                # epoch timestamps (seconds or ms)
                df["date_posted"] = pd.to_datetime(
                    s,
                    errors="coerce",
                    utc=True,
                    unit="ms",
                )
            else:
                # ISO strings like "2026-01-31"
                df["date_posted"] = pd.to_datetime(
                    s,
                    errors="coerce",
                    utc=True,
                )
        else:
            df["date_posted"] = pd.NaT

        # Kill epoch-zero explicitly
        df.loc[
            df["date_posted"] <= pd.Timestamp("1971-01-01", tz="UTC"), "date_posted"
        ] = pd.NaT

        df["user"] = ctx.user
        df["use_case"] = ctx.use_case
        df["ingested_at"] = datetime.utcnow()

        self.con.execute("""
            INSERT INTO jobs_raw
            SELECT
                job_url,
                title,
                company,
                description,
                location,
                site,
                date_posted,
                user,
                use_case,
                ingested_at
            FROM df
            ON CONFLICT (job_url, user, use_case)
            DO UPDATE SET
                title        = EXCLUDED.title,
                company      = EXCLUDED.company,
                description  = EXCLUDED.description,
                location     = EXCLUDED.location,
                site         = EXCLUDED.site,
                date_posted  = EXCLUDED.date_posted,
                ingested_at  = EXCLUDED.ingested_at
            """)

    # --------------------------------------------------
    # Corpus
    # --------------------------------------------------
    def load_corpus(self, ctx) -> pd.DataFrame:
        return self.con.execute(
            """
            SELECT *
            FROM jobs_raw
            WHERE user = ? AND use_case = ?
            """,
            [ctx.user, ctx.use_case],
        ).df()

    # --------------------------------------------------
    # Results
    # --------------------------------------------------
    def persist_results(self, run_id: str, df: pd.DataFrame):
        if df.empty:
            return

        records = []
        for _, row in df.iterrows():
            records.append(
                (
                    run_id,
                    row["job_url"],
                    float(row["final_score"]),
                    row.to_json(),
                )
            )

        self.con.executemany(
            """
            INSERT INTO run_results
            (run_id, job_url, final_score, payload)
            VALUES (?, ?, ?, ?)
            """,
            records,
        )

    # --------------------------------------------------
    # Query helpers (UI)
    # --------------------------------------------------
    def latest_successful_run(self, user: str, use_case: str):
        return self.con.execute(
            """
            SELECT run_id
            FROM runs
            WHERE user = ? AND use_case = ? AND status = 'success'
            ORDER BY finished_at DESC
            LIMIT 1
            """,
            [user, use_case],
        ).fetchone()

    @staticmethod
    def connect_readonly(db_path: Path):
        return duckdb.connect(str(db_path), read_only=True)
