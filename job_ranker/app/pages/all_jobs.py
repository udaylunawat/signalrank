# app/pages/all_jobs.py
from datetime import datetime

import pandas as pd
import streamlit as st

from job_ranker.domain.roles import classify_functional_role

st.set_page_config(layout="wide")
st.title("🗂 All Discovered Jobs")


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def format_date(val):
    if val is None:
        return ""
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.date().isoformat()
    try:
        return pd.to_datetime(val, utc=True).date().isoformat()
    except Exception:
        return ""


def list_users_and_use_cases(con):
    users = (
        con.execute("SELECT DISTINCT user FROM runs ORDER BY user")
        .df()["user"]
        .tolist()
    )

    def use_cases_for(user):
        rows = con.execute(
            "SELECT DISTINCT use_case FROM runs WHERE user = ? ORDER BY use_case",
            [user],
        ).df()
        return rows["use_case"].tolist()

    return users, use_cases_for


# --------------------------------------------------
# Session
# --------------------------------------------------
from job_ranker.app.session import get_session

with st.sidebar:
    st.header("Session")
    user, use_case = get_session()

if not user or not use_case:
    st.stop()

from job_ranker.batch.context import resolve_ui_context

ctx = resolve_ui_context(user, use_case)
from job_ranker.app.db import get_ui_db

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
df["Category"] = (
    df["title"].fillna("").apply(lambda t: classify_functional_role(t, ctx.config))
)
df["Posted"] = df["date_posted"].apply(format_date)
df["Ingested"] = df["ingested_at"].apply(format_date)
df["Apply"] = df["job_url_direct"].fillna(df["job_url"])

st.dataframe(
    df.rename(
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
    width="stretch",
    column_config={
        "Apply": st.column_config.LinkColumn(
            "Apply",
            display_text="Apply",
        )
    },
)
