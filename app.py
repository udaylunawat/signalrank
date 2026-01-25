# app.py
import os
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

import streamlit as st
import pandas as pd
from pathlib import Path

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
DATA_PATH = Path("outputs/ranked_jobs.csv")

st.set_page_config(
    page_title="Calm-First Job Matches",
    layout="wide",
)

st.title("Calm-First Job Matches")
st.caption("Daily, batch-ranked senior IC roles")

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
if not DATA_PATH.exists():
    st.warning(
        "No ranked jobs found.\n\n"
        "Run the CLI first:\n"
        "`jobs run ...`"
    )
    st.stop()

df = pd.read_csv(DATA_PATH)

if df.empty:
    st.warning("Ranked jobs file is empty.")
    st.stop()

# --------------------------------------------------
# HIGH-LEVEL STATS
# --------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Matches", len(df))
c2.metric("Top Score", f"{df['final_score'].max():.2f}")
c3.metric("Median Score", f"{df['final_score'].median():.2f}")
c4.metric("Unique Companies", df["company"].nunique())

# --------------------------------------------------
# TOP JOBS BY SCORE (HORIZONTAL)
# --------------------------------------------------
st.subheader("Top Roles by Match Score")

top_jobs = (
    df[["title", "final_score"]]
    .head(15)
    .set_index("title")
)

st.bar_chart(
    top_jobs,
    width="stretch",
)

# --------------------------------------------------
# COMPANIES BY AVERAGE SCORE (SIGNAL, NOT COUNT)
# --------------------------------------------------
st.subheader("Companies by Average Match Quality")

company_quality = (
    df.groupby("company")["final_score"]
    .mean()
    .sort_values(ascending=False)
    .head(10)
)

st.bar_chart(
    company_quality,
    width="stretch",
)

# --------------------------------------------------
# TABLE FILTER
# --------------------------------------------------
st.subheader("Ranked Jobs")

top_n = st.slider(
    "Show top N jobs",
    min_value=10,
    max_value=min(100, len(df)),
    value=min(30, len(df)),
    step=5,
)

display_df = df.head(top_n).copy()

# --------------------------------------------------
# APPLY LINK
# --------------------------------------------------
def resolve_apply_link(row):
    if isinstance(row.get("job_url"), str):
        return row["job_url"]
    if isinstance(row.get("job_url_direct"), str):
        return row["job_url_direct"]
    return None

display_df["Apply"] = display_df.apply(resolve_apply_link, axis=1)

# --------------------------------------------------
# CLEAN TABLE
# --------------------------------------------------
table_df = (
    display_df
    .rename(columns={
        "title": "Role",
        "company": "Company",
        "location": "Location",
        "final_score": "Score",
    })
    [["Role", "Company", "Location", "Score", "Apply"]]
)

table_df["Score"] = table_df["Score"].round(2)

st.dataframe(
    table_df,
    hide_index=True,
    width="stretch",
    column_config={
        "Role": st.column_config.TextColumn(width="large"),
        "Company": st.column_config.TextColumn(width="medium"),
        "Location": st.column_config.TextColumn(width="small"),
        "Score": st.column_config.ProgressColumn(
            min_value=0.0,
            max_value=1.0,
            format="%.2f",
        ),
        "Apply": st.column_config.LinkColumn(
            "Apply",
            display_text="Apply",
        ),
    },
)

# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------
st.download_button(
    "Download CSV",
    df.to_csv(index=False).encode(),
    file_name="ranked_jobs.csv",
)