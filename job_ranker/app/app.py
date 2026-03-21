# app/app.py
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="SignalRank", layout="wide", page_icon="🎯")

st.title("🎯 SignalRank")
st.caption("AI-powered job ranking · Batch-first · Read-only UI")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.markdown("### Discover")
    st.page_link("pages/dashboard.py", label="📊 Discovery Dashboard", help="Explore top-ranked jobs from the latest run")
    st.page_link("pages/all_jobs.py", label="🗂 All Discovered Jobs", help="Browse the full raw scrape with filters")

with col2:
    st.markdown("### Manage")
    st.page_link("pages/tracker.py", label="📋 Job Tracker", help="Track your pipeline, offers, application status, and recruiter contacts")
