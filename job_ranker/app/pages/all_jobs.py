# app/pages/all_jobs.py
import pandas as pd
import streamlit as st
from job_ranker.domain.roles import classify_functional_role

st.set_page_config(layout="wide")
st.title("🗂 All Discovered Jobs")
st.caption("Browse every job scraped in the current run before ranking filters are applied.")

# --------------------------------------------------
# Session
# --------------------------------------------------
from job_ranker.app.session import get_session  # noqa: E402

with st.sidebar:
    st.markdown("## 🎯 SignalRank")
    st.caption("AI-powered job discovery")
    st.divider()
    user, use_case = get_session()
    st.divider()
    st.markdown("**Navigate**")
    st.page_link("pages/dashboard.py", label="📊 Dashboard")
    st.page_link("pages/tracker.py", label="📋 Job Tracker")
    st.page_link("pages/all_jobs.py", label="🗂 All Jobs")

if not user or not use_case:
    st.stop()

from job_ranker.app.utils import format_date, make_apply_column  # noqa: E402
from job_ranker.batch.context import resolve_ui_context  # noqa: E402

ctx = resolve_ui_context(user, use_case)

from job_ranker.app.db import get_ui_db  # noqa: E402

con = get_ui_db()

df = con.execute(
    """
    SELECT
    title,
    company,
    location,
    site,
    date_posted,
    job_url,
    job_url_direct,
    ingested_at
    FROM jobs_raw
    WHERE user = ? AND use_case = ?
    ORDER BY ingested_at DESC
    """,
    [user, use_case],
).df()

if df.empty:
    st.info("No jobs scraped yet.")
    st.stop()

# ---- Deduplicate by title+company (case-insensitive, keep latest) ----
total_before = len(df)
df["_dedup_key"] = (
    df["title"].str.strip().str.lower() + "|" + df["company"].str.strip().str.lower()
)
df = df.drop_duplicates(subset="_dedup_key", keep="first")
df = df.drop(columns=["_dedup_key"])
dupes_removed = total_before - len(df)
if dupes_removed:
    st.caption(f"Removed {dupes_removed:,} duplicates ({total_before:,} → {len(df):,} unique jobs)")

df["Category"] = df.apply(
    lambda r: classify_functional_role(r["title"] or "", r.get("description") or "", ctx.config),
    axis=1,
)
df["Posted"] = df["date_posted"].apply(format_date)
df["Ingested"] = df["ingested_at"].apply(format_date)
df["Apply"] = df["job_url_direct"].fillna(df["job_url"])

# --------------------------------------------------
# Filter row
# --------------------------------------------------
filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    search_q = st.text_input("Search (title, company)", "")

with filter_col2:
    site_options = sorted(df["site"].dropna().unique().tolist())
    sel_sites = st.multiselect("Site", site_options, default=site_options)

with filter_col3:
    cat_options = sorted(df["Category"].dropna().unique().tolist())
    sel_cats = st.multiselect("Category", cat_options, default=cat_options)

mask = pd.Series([True] * len(df), index=df.index)
if search_q:
    q = search_q.lower()
    mask &= (
        df["title"].fillna("").str.lower().str.contains(q, na=False)
        | df["company"].fillna("").str.lower().str.contains(q, na=False)
    )
if sel_sites:
    mask &= df["site"].isin(sel_sites)
if sel_cats:
    mask &= df["Category"].isin(sel_cats)

filtered = df[mask]
st.caption(f"Showing {len(filtered):,} of {len(df):,} jobs")

st.dataframe(
    filtered.rename(
        columns={
            "title": "Role",
            "company": "Company",
            "location": "Location",
            "site": "Source",
        }
    )[
        [
            "Role",
            "Company",
            "Location",
            "Category",
            "Source",
            "Posted",
            "Ingested",
            "Apply",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "Apply": make_apply_column(),
    },
)
