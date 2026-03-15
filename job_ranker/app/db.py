# app/db.py
from pathlib import Path
import duckdb

_DB_PATH = Path(__file__).resolve().parents[1] / "duckdb"

def get_ui_db():
    """
    UI-only DuckDB connection.
    - read-only
    - fresh connection each call so new batch data is visible
    - never conflicts with batch writer
    """
    return duckdb.connect(str(_DB_PATH), read_only=True)
