# ================================
# FILE: pages/5_All_Jobs.py
# ================================
import duckdb
import pandas as pd
import streamlit as st
from user_context import resolve_user_context
from utils.session_guard import require_login

st.set_page_config(layout="wide")
st.title("🗂️ All Discovered Jobs")
st.caption("Every job ever scraped for this user/use case")

require_login()

ctx = resolve_user_context(
    user=st.session_state.user,
    use_case_override=st.session_state.use_case,
    require_resume=False,
)

db_path = ctx.base_dir / "jobs.duckdb"
if not db_path.exists():
    st.warning("No data available yet.")
    st.stop()

con = duckdb.connect(str(db_path))

df = con.execute(
    """
    SELECT
        title,
        company,
        location,
        date_posted,
        site,
        job_url,
        ingested_at
    FROM jobs_raw
    WHERE user = ? AND use_case = ?
    ORDER BY ingested_at DESC
    """,
    [ctx.user, ctx.use_case],
).df()

if df.empty:
    st.info("No jobs found yet.")
    st.stop()

# -------------------------
# Presentation helpers
# -------------------------
df["Date Posted"] = pd.to_datetime(df["date_posted"], utc=True, errors="coerce").dt.date
df["Apply"] = df["job_url"]
df["Company Link"] = None

df = df.rename(
    columns={
        "title": "Role",
        "company": "Company",
        "location": "Location",
        "site": "Source",
    }
)

# -------------------------
# Filters (cheap, useful)
# -------------------------
st.sidebar.header("Filters")
company_filter = st.sidebar.text_input("Company contains")
role_filter = st.sidebar.text_input("Role contains")

if company_filter:
    df = df[df["Company"].str.contains(company_filter, case=False, na=False)]
if role_filter:
    df = df[df["Role"].str.contains(role_filter, case=False, na=False)]

st.dataframe(
    df[
        [
            "Role",
            "Company",
            "Company Link",
            "Location",
            "Date Posted",
            "Source",
            "Apply",
        ]
    ],
    hide_index=True,
    column_config={
        "Apply": st.column_config.LinkColumn("Apply"),
        "Company Link": st.column_config.LinkColumn(
            "Website",
            display_text="Website",
        ),
    },
    width="stretch",
)
