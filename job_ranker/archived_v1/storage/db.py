# ================================
# FILE: storage/db.py
# ================================
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd


def _normalize_date_series(s):
    if s is None:
        return None

    # numeric → epoch milliseconds
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_datetime(s, unit="ms", errors="coerce", utc=True)

    # string → ISO / RFC
    return pd.to_datetime(s, errors="coerce", utc=True)


class JobStore:
    """
    DuckDB-backed storage spine.

    RULES (NON-NEGOTIABLE):
    - All data is user + use_case scoped
    - This class owns ALL persistence
    - No scoring logic here
    - No LLM calls here
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.con = duckdb.connect(str(db_path))
        self._init_schema()

    # --------------------------------------------------
    # SCHEMA
    # --------------------------------------------------
    def _init_schema(self):
        # -----------------------------
        # jobs_raw base table
        # -----------------------------
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS jobs_raw (
                job_url TEXT,
                job_url_direct TEXT,
                company_url TEXT,
                company_url_direct TEXT,

                title TEXT,
                company TEXT,
                description TEXT,
                location TEXT,
                date_posted TIMESTAMP,
                site TEXT,

                user TEXT,
                use_case TEXT,
                ingested_at TIMESTAMP,

                PRIMARY KEY (job_url, user, use_case)
            );
            """)

        # -----------------------------
        # SCHEMA MIGRATIONS (SAFE)
        # -----------------------------
        self.con.execute(
            "ALTER TABLE jobs_raw ADD COLUMN IF NOT EXISTS job_url_direct TEXT;"
        )
        self.con.execute(
            "ALTER TABLE jobs_raw ADD COLUMN IF NOT EXISTS company_url_direct TEXT;"
        )
        self.con.execute(
            "ALTER TABLE jobs_raw ADD COLUMN IF NOT EXISTS company_url TEXT;"
        )

        # -----------------------------
        # other tables unchanged
        # -----------------------------
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                text_fingerprint TEXT,
                cfg_fingerprint TEXT,
                vector FLOAT[],

                user TEXT,
                use_case TEXT,

                PRIMARY KEY (text_fingerprint, cfg_fingerprint, user, use_case)
            );
            """)

        self.con.execute("""
            CREATE TABLE IF NOT EXISTS ranked_snapshots (
                run_id TEXT,
                user TEXT,
                use_case TEXT,
                job_url TEXT,
                final_score DOUBLE,
                payload JSON,
                created_at TIMESTAMP
            );
            """)

        self.con.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                user TEXT,
                use_case TEXT,
                job_url TEXT,
                hidden BOOLEAN DEFAULT FALSE,
                starred BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP,
                PRIMARY KEY (user, use_case, job_url)
            );
            """)

    # --------------------------------------------------
    # RAW INGEST (REPLACES CACHE CSVs)
    # --------------------------------------------------
    def upsert_raw_jobs(
        self,
        df: pd.DataFrame,
        *,
        user: str,
        use_case: str,
    ):
        if df.empty:
            return

        df = df.copy()

        if "job_url_direct" not in df.columns:
            df["job_url_direct"] = None
        if "company_url_direct" not in df.columns:
            df["company_url_direct"] = None
        if "company_url" not in df.columns:
            df["company_url"] = None
        # Ensure columns exist in DF
        for col in [
            "job_url_direct",
            "company_url",
            "company_url_direct",
        ]:
            if col not in df.columns:
                df[col] = None

        df["date_posted"] = pd.to_datetime(
            df.get("date_posted"),
            errors="coerce",
            utc=True,
            unit="ms",
        )

        df["user"] = user
        df["use_case"] = use_case
        df["ingested_at"] = datetime.utcnow()

        self.con.execute("""
            INSERT INTO jobs_raw (
                job_url,
                job_url_direct,
                company_url,
                company_url_direct,
                title,
                company,
                description,
                location,
                date_posted,
                site,
                user,
                use_case,
                ingested_at
            )
            SELECT
                job_url,
                job_url_direct,
                company_url,
                company_url_direct,
                title,
                company,
                description,
                location,
                date_posted,
                site,
                user,
                use_case,
                ingested_at
            FROM df
            ON CONFLICT (job_url, user, use_case)
            DO UPDATE SET
                job_url_direct     = EXCLUDED.job_url_direct,
                company_url        = EXCLUDED.company_url,
                company_url_direct = EXCLUDED.company_url_direct,
                title              = EXCLUDED.title,
                company            = EXCLUDED.company,
                description        = EXCLUDED.description,
                location           = EXCLUDED.location,
                date_posted        = EXCLUDED.date_posted,
                site               = EXCLUDED.site,
                ingested_at        = EXCLUDED.ingested_at
            """)

    def load_raw_jobs(
        self,
        *,
        user: str,
        use_case: str,
        max_age_hours: Optional[int] = None,
    ) -> pd.DataFrame:
        where = ["user = ?", "use_case = ?"]
        params: list = [user, use_case]

        if max_age_hours is not None:
            where.append("ingested_at >= NOW() - INTERVAL ? HOUR")
            params.append(max_age_hours)

        query = f"""
            SELECT *
            FROM jobs_raw
            WHERE {' AND '.join(where)}
        """

        return self.con.execute(query, params).df()

    # --------------------------------------------------
    # CORPUS VIEW (REPLACES build_corpus.py)
    # --------------------------------------------------
    def ensure_corpus_view(self):
        """
        Deduplicated, latest-first corpus.
        """
        self.con.execute("""
            CREATE OR REPLACE VIEW jobs_corpus AS
            SELECT *
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY job_url, user, use_case
                        ORDER BY date_posted DESC NULLS LAST
                    ) AS rn
                FROM jobs_raw
            )
            WHERE rn = 1;
            """)

    def load_corpus(
        self,
        *,
        user: str,
        use_case: str,
    ) -> pd.DataFrame:
        return self.con.execute(
            """
            SELECT c.*
            FROM jobs_corpus c
            LEFT JOIN annotations a
            ON c.job_url = a.job_url
            AND a.user = ?
            AND a.use_case = ?
            WHERE
                c.user = ?
                AND c.use_case = ?
                AND COALESCE(a.hidden, FALSE) = FALSE
            """,
            [user, use_case, user, use_case],
        ).df()

    # --------------------------------------------------
    # EMBEDDINGS
    # --------------------------------------------------
    def fetch_embeddings(
        self,
        *,
        text_fingerprints,
        cfg_fingerprint: str,
        user: str,
        use_case: str,
    ) -> dict[str, list[float]]:
        if not text_fingerprints:
            return {}

        query = """
        SELECT e.text_fingerprint, e.vector
        FROM embeddings e
        JOIN UNNEST(?) AS t(fp)
        ON e.text_fingerprint = t.fp
        WHERE
            e.cfg_fingerprint = ?
            AND e.user = ?
            AND e.use_case = ?
        """

        rows = self.con.execute(
            query,
            [
                list(text_fingerprints),
                cfg_fingerprint,
                user,
                use_case,
            ],
        ).fetchall()

        return {k: v for k, v in rows}

    def store_embeddings(
        self,
        *,
        rows: list[tuple[str, str, list[float]]],
        user: str,
        use_case: str,
    ):
        if not rows:
            return

        df = pd.DataFrame(
            rows,
            columns=["text_fingerprint", "cfg_fingerprint", "vector"],
        )
        df["user"] = user
        df["use_case"] = use_case

        self.con.execute("""
            INSERT INTO embeddings
            SELECT * FROM df
            ON CONFLICT (text_fingerprint, cfg_fingerprint, user, use_case)
            DO NOTHING
            """)

    # --------------------------------------------------
    # RANKED SNAPSHOTS
    # --------------------------------------------------
    def write_ranked_snapshot(
        self,
        *,
        run_id: str,
        user: str,
        use_case: str,
        df: pd.DataFrame,
    ):
        if df.empty:
            return

        payload_cols = df.columns.tolist()

        records = []
        for _, row in df.iterrows():
            records.append(
                (
                    run_id,
                    user,
                    use_case,
                    row["job_url"],
                    float(row["final_score"]),
                    row[payload_cols].to_json(),
                    datetime.utcnow(),
                )
            )

        self.con.executemany(
            """
            INSERT INTO ranked_snapshots
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

    def load_latest_ranked(
        self,
        *,
        user: str,
        use_case: str,
    ) -> pd.DataFrame:
        return (
            self.con.execute(
                """
            SELECT payload
            FROM ranked_snapshots
            WHERE user = ? AND use_case = ?
            QUALIFY
                created_at = MAX(created_at) OVER ()
            """,
                [user, use_case],
            )
            .df()
            .apply(lambda r: pd.read_json(r["payload"]), axis=1)
            .reset_index(drop=True)
        )

    # --------------------------------------------------
    # ANNOTATIONS (UI ONLY)
    # --------------------------------------------------
    def annotate(
        self,
        *,
        user: str,
        use_case: str,
        job_url: str,
        hidden: Optional[bool] = None,
        starred: Optional[bool] = None,
    ):
        self.con.execute(
            """
            INSERT INTO annotations
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user, use_case, job_url)
            DO UPDATE SET
                hidden = COALESCE(EXCLUDED.hidden, annotations.hidden),
                starred = COALESCE(EXCLUDED.starred, annotations.starred),
                updated_at = EXCLUDED.updated_at
            """,
            [
                user,
                use_case,
                job_url,
                hidden,
                starred,
                datetime.utcnow(),
            ],
        )

    def cosine_similarity_bulk(
        self,
        *,
        query_vector: list[float],
        vectors: list[list[float]],
    ) -> list[float]:
        """
        Compute cosine similarity using DuckDB list_cosine_similarity.
        Deterministic and fast.
        """
        return [
            r[0]
            for r in self.con.execute(
                """
                SELECT list_cosine_similarity(v, ?)
                FROM UNNEST(?) AS t(v)
                """,
                [query_vector, vectors],
            ).fetchall()
        ]
