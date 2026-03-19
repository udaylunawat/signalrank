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
        con.commit()
    except Exception:
        con.close()
        raise
    return con


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
