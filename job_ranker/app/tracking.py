"""
SQLite-backed tracking of user actions (applied / connected) for recruiter contacts.

DB path: $JR_TRACKING_DB env var (for tests) or ~/.job_ranker/tracking.db
"""
import os
import sqlite3
from pathlib import Path

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS recruiter_tracking (
    recruiter_id  TEXT PRIMARY KEY,
    applied       INTEGER DEFAULT 0,
    connected     INTEGER DEFAULT 0,
    notes         TEXT DEFAULT '',
    updated_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
"""

_CREATE_JOB_TABLE = """
CREATE TABLE IF NOT EXISTS job_tracking (
    job_id        TEXT PRIMARY KEY,
    user          TEXT NOT NULL DEFAULT 'example',
    applied       INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'Not Applied',
    date_applied  TEXT DEFAULT '',
    interview_date TEXT DEFAULT '',
    offer_lpa     REAL DEFAULT NULL,
    notes         TEXT DEFAULT '',
    updated_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
"""

_UPSERT_JOB = """
INSERT INTO job_tracking (job_id, user, applied, status, date_applied, interview_date, offer_lpa, notes, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%S', 'now'))
ON CONFLICT(job_id) DO UPDATE SET
    applied        = excluded.applied,
    status         = excluded.status,
    date_applied   = excluded.date_applied,
    interview_date = excluded.interview_date,
    offer_lpa      = excluded.offer_lpa,
    notes          = excluded.notes,
    updated_at     = strftime('%Y-%m-%dT%H:%M:%S', 'now');
"""

_UPSERT = """
INSERT INTO recruiter_tracking (recruiter_id, applied, connected, notes, updated_at)
VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%S', 'now'))
ON CONFLICT(recruiter_id) DO UPDATE SET
    applied    = excluded.applied,
    connected  = excluded.connected,
    notes      = excluded.notes,
    updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now');
"""


def _db_path() -> Path:
    env = os.getenv("JR_TRACKING_DB")
    if env:
        return Path(env)
    p = Path.home() / ".job_ranker" / "tracking.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_tracking_db() -> sqlite3.Connection:
    """Open tracking DB (creates if missing). check_same_thread=False for Streamlit."""
    con = sqlite3.connect(str(_db_path()), check_same_thread=False)
    try:
        con.execute(_CREATE_TABLE)
        con.execute(_CREATE_JOB_TABLE)
        con.commit()
    except Exception:
        con.close()
        raise
    return con


def load_job_tracking(user: str) -> dict[str, dict]:
    """Return {job_id: {applied, status, date_applied, interview_date, offer_lpa, notes, updated_at}}."""
    con = get_tracking_db()
    try:
        # Add offer_lpa column if missing (migration for existing DBs)
        cols = [r[1] for r in con.execute("PRAGMA table_info(job_tracking)").fetchall()]
        if "offer_lpa" not in cols:
            con.execute("ALTER TABLE job_tracking ADD COLUMN offer_lpa REAL DEFAULT NULL")
            con.commit()
        rows = con.execute(
            "SELECT job_id, applied, status, date_applied, interview_date, offer_lpa, notes, updated_at "
            "FROM job_tracking WHERE user = ?",
            [user],
        ).fetchall()
        return {
            row[0]: {
                "applied": bool(row[1]),
                "status": row[2] or "Not Applied",
                "date_applied": row[3] or "",
                "interview_date": row[4] or "",
                "offer_lpa": row[5],
                "notes": row[6] or "",
                "updated_at": row[7] or "",
            }
            for row in rows
        }
    finally:
        con.close()


def upsert_job_tracking(
    job_id: str,
    user: str,
    applied: bool,
    status: str,
    date_applied: str = "",
    interview_date: str = "",
    notes: str = "",
    offer_lpa: float | None = None,
) -> None:
    """Upsert one job tracking row."""
    con = get_tracking_db()
    try:
        con.execute(_UPSERT_JOB, (job_id, user, int(applied), status, date_applied, interview_date, offer_lpa, notes))
        con.commit()
    finally:
        con.close()


def load_tracking(ids: list[str]) -> dict[str, dict]:
    """Return {recruiter_id: {applied, connected, notes, updated_at}} for given ids only."""
    if not ids:
        return {}
    con = get_tracking_db()
    try:
        placeholders = ",".join("?" * len(ids))
        rows = con.execute(
            f"SELECT recruiter_id, applied, connected, notes, updated_at "
            f"FROM recruiter_tracking WHERE recruiter_id IN ({placeholders})",
            ids,
        ).fetchall()
        return {
            row[0]: {
                "applied": bool(row[1]),
                "connected": bool(row[2]),
                "notes": row[3] or "",
                "updated_at": row[4] or "",
            }
            for row in rows
        }
    finally:
        con.close()


def set_tracking(
    recruiter_id: str,
    applied: bool,
    connected: bool,
    notes: str = "",
) -> None:
    """Upsert one tracking row. Always updates updated_at."""
    con = get_tracking_db()
    try:
        con.execute(_UPSERT, (recruiter_id, int(applied), int(connected), notes))
        con.commit()
    finally:
        con.close()
