# app/utils.py — shared helpers for Streamlit pages
from datetime import datetime

import pandas as pd
import streamlit as st

from job_ranker.domain.roles import classify_functional_role


def format_date(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.date().isoformat()
    try:
        return pd.to_datetime(val, utc=True).date().isoformat()
    except Exception:
        return ""


def classify_categories(title: str, description: str, cfg: dict) -> list[str]:
    primary = classify_functional_role(title, description, cfg)
    if not primary:
        return []
    return [primary]


def load_recruiter_map(con) -> dict[str, dict]:
    """Returns {company_lower: {name, linkedin_url}} — best-confidence recruiter per company."""
    try:
        rows = con.execute("""
            SELECT company, name, linkedin_url
            FROM recruiters
            WHERE company IS NOT NULL AND company != ''
            ORDER BY
                CASE confidence WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END
        """).fetchall()
    except Exception:
        return {}
    result: dict[str, dict] = {}
    for company, name, linkedin_url in rows:
        key = company.strip().lower()
        if key not in result:
            result[key] = {"name": name or "", "linkedin_url": linkedin_url or ""}
    return result


def make_apply_column():
    return st.column_config.LinkColumn("Apply", display_text="Apply ↗")


def make_recruiter_column():
    return st.column_config.LinkColumn("Recruiter", display_text="→ LinkedIn")
