"""
NEW:
- List historical runs
- Compare runs
"""

# app/pages/runs.py
import streamlit as st

from job_ranker.app.session import get_session
from job_ranker.batch.context import resolve_ui_context


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


st.set_page_config(layout="wide")
st.title("🧾 Runs")


with st.sidebar:
    st.header("Session")
    user, use_case = get_session()

if not user or not use_case:
    st.stop()

ctx = resolve_ui_context(user, use_case)
from job_ranker.app.db import get_ui_db

con = get_ui_db()

df = con.execute(
    """
    SELECT
      run_id,
      status,
      started_at,
      finished_at
    FROM runs
    WHERE user = ? AND use_case = ?
    ORDER BY started_at DESC
    """,
    [user, use_case],
).df()

if df.empty:
    st.info("No runs found.")
    st.stop()

st.dataframe(
    df,
    hide_index=True,
    width="stretch",
)
