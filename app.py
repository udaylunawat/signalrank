# app.py
import os
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from datetime import datetime, timezone
import math

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
RANKED_PATH = Path("outputs/ranked_jobs.csv")
CORPUS_PATH = Path("outputs/ranked_corpus.csv")
STATE_PATH = Path("outputs/.last_seen_jobs.csv")

RECENCY_HALF_LIFE_DAYS = 21

st.set_page_config(
    page_title="Calm-First Job Matches",
    layout="wide",
)

st.title("Calm-First Job Matches")
st.caption("Daily, batch-ranked senior IC roles")

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def normalize_date(val):
    try:
        return pd.to_datetime(val, utc=True)
    except Exception:
        return None

def recency_weight(dt):
    if dt is None:
        return 1.0
    age_days = (datetime.now(timezone.utc) - dt).days
    if age_days < 0:
        return 1.0
    return math.exp(-age_days / RECENCY_HALF_LIFE_DAYS)

def resolve_apply_link(row):
    if isinstance(row.get("job_url"), str):
        return row["job_url"]
    if isinstance(row.get("job_url_direct"), str):
        return row["job_url_direct"]
    return None

# --------------------------------------------------
# LOAD RANKED JOBS
# --------------------------------------------------
if not RANKED_PATH.exists():
    st.warning(
        "No ranked jobs found.\n\n"
        "Run the CLI first:\n"
        "`jobs run ...`"
    )
    st.stop()

df = pd.read_csv(RANKED_PATH)

if df.empty:
    st.warning("Ranked jobs file is empty.")
    st.stop()

# Normalize dates
if "date_posted" in df.columns:
    df["date_posted_dt"] = df["date_posted"].apply(normalize_date)
else:
    df["date_posted_dt"] = None

# Normalize scores
df["score_100"] = (df["final_score"] * 100).round().astype(int)
df["score_100"] = df["score_100"].clip(lower=1, upper=100)

# --------------------------------------------------
# DELTA: NEW JOBS SINCE LAST RUN
# --------------------------------------------------
current_ids = set(df["job_url"].dropna())

if STATE_PATH.exists():
    prev = pd.read_csv(STATE_PATH)
    prev_ids = set(prev["job_url"].dropna())
else:
    prev_ids = set()

new_ids = current_ids - prev_ids
new_jobs_df = df[df["job_url"].isin(new_ids)].copy()

# Persist state for next run
STATE_PATH.parent.mkdir(exist_ok=True)
df[["job_url"]].dropna().to_csv(STATE_PATH, index=False)

# --------------------------------------------------
# HIGH-LEVEL STATS
# --------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Total Matches", len(df))
c2.metric("New Since Last Run", len(new_jobs_df))
c3.metric("Top Score", df["score_100"].max())
c4.metric("Median Score", int(df["score_100"].median()))
c5.metric("Unique Companies", df["company"].nunique())

# --------------------------------------------------
# SECTION: NEW JOBS SINCE LAST RUN
# --------------------------------------------------
st.subheader("New Jobs Since Last Run")

if new_jobs_df.empty:
    st.info("No new jobs detected since the last run.")
else:
    nj = new_jobs_df.sort_values("final_score", ascending=False).head(30)
    nj["Apply"] = nj.apply(resolve_apply_link, axis=1)

    st.dataframe(
        nj.rename(columns={
            "title": "Role",
            "company": "Company",
            "location": "Location",
            "score_100": "Score",
            "date_posted": "Date Posted",
            "site": "Site",
        })[
            ["Role", "Company", "Location", "Score", "Date Posted", "Site", "Apply"]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Apply": st.column_config.LinkColumn(
                "Apply",
                display_text="Apply",
            ),
        },
    )

# --------------------------------------------------
# SECTION: RANKED JOBS
# --------------------------------------------------
st.subheader("Ranked Jobs")

top_n = st.slider(
    "Show top N jobs",
    min_value=10,
    max_value=min(200, len(df)),
    value=min(50, len(df)),
    step=10,
)

display_df = df.sort_values("final_score", ascending=False).head(top_n).copy()
display_df["Apply"] = display_df.apply(resolve_apply_link, axis=1)

st.dataframe(
    display_df.rename(columns={
        "title": "Role",
        "company": "Company",
        "location": "Location",
        "score_100": "Score",
        "date_posted": "Date Posted",
        "site": "Site",
    })[
        ["Role", "Company", "Location", "Score", "Date Posted", "Site", "Apply"]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "Apply": st.column_config.LinkColumn(
            "Apply",
            display_text="Apply",
        ),
    },
)

# --------------------------------------------------
# SECTION: RECENCY HISTOGRAM
# --------------------------------------------------
st.subheader("Job Recency Distribution")

if df["date_posted_dt"].notna().any():
    rec_df = df.copy()
    rec_df["age_days"] = (
        datetime.now(timezone.utc) - rec_df["date_posted_dt"]
    ).dt.days

    hist = (
        alt.Chart(rec_df.dropna(subset=["age_days"]))
        .mark_bar()
        .encode(
            x=alt.X(
                "age_days:Q",
                bin=alt.Bin(step=7),
                title="Job Age (days)",
            ),
            y=alt.Y("count()", title="Job Count"),
            tooltip=["count()"],
        )
        .properties(height=250)
    )

    st.altair_chart(hist, use_container_width=True)
else:
    st.info("No valid date_posted data available.")

# --------------------------------------------------
# SECTION: RECENCY DECAY CURVE
# --------------------------------------------------
st.subheader("Recency Decay Curve (Sanity Check)")

curve_df = pd.DataFrame({
    "age_days": list(range(0, 91)),
})
curve_df["weight"] = curve_df["age_days"].apply(
    lambda d: math.exp(-d / RECENCY_HALF_LIFE_DAYS)
)

curve = (
    alt.Chart(curve_df)
    .mark_line()
    .encode(
        x=alt.X("age_days:Q", title="Age (days)"),
        y=alt.Y("weight:Q", title="Recency Weight"),
        tooltip=["age_days", "weight"],
    )
    .properties(height=250)
)

st.altair_chart(curve, use_container_width=True)

# --------------------------------------------------
# SECTION: RANKED CORPUS VIEW
# --------------------------------------------------
st.subheader("Ranked Corpus (All Deduplicated Jobs)")

if CORPUS_PATH.exists():
    corpus = pd.read_csv(CORPUS_PATH)
    st.caption(f"Corpus size: {len(corpus)} jobs")

    show_corpus = st.checkbox("Show corpus table", value=False)
    if show_corpus:
        st.dataframe(
            corpus.rename(columns={
                "title": "Role",
                "company": "Company",
                "location": "Location",
                "final_score": "final_score",
                "date_posted": "Date Posted",
                "site": "Site",
            })[
                ["Role", "Company", "Location", "final_score", "Date Posted", "Site"]
            ],
            hide_index=True,
            use_container_width=True,
        )
else:
    st.info("Corpus not found. Run build_corpus.py to enable this view.")

# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------
st.download_button(
    "Download Ranked CSV",
    df.to_csv(index=False).encode(),
    file_name="ranked_jobs.csv",
)