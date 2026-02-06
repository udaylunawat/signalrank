# app/db.py
from pathlib import Path

import duckdb
import streamlit as st


@st.cache_resource
def get_ui_db():
    """
    UI-only DuckDB connection.
    - read-only
    - cached across reruns
    - never conflicts with batch writer
    """
    root = Path(__file__).resolve().parents[1]
    db_path = root / "duckdb"
    con = duckdb.connect(str(db_path), read_only=True)
    return con
