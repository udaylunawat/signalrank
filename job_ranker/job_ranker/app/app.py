# app/app.py
import sys
from pathlib import Path

import streamlit as st

# Ensure repo root is on PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


st.set_page_config(
    page_title="Job Ranker v2",
    layout="wide",
)

st.title("🌊 Job Ranker v2")
st.caption("Batch-first · Immutable runs · Read-only UI")

st.markdown("""
**Invariants**
- UI never triggers scraping or ranking
- Every view is backed by an immutable run
- DuckDB is the single source of truth
""")

st.divider()

st.page_link("pages/dashboard.py", label="📊 Dashboard")
st.page_link("pages/runs.py", label="🧾 Runs")
st.page_link("pages/all_jobs.py", label="🗂 All Jobs")
