# ================================
# FILE: pages/2_Dashboard.py
# ================================
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timezone
import math

from config_loader import settings
from user_context import resolve_user_context
from utils.session_guard import require_login

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("📊 Dashboard")
st.caption("Ranked jobs, trends, and freshness signals")

st.sidebar.header("Session")

# --------------------------------------------------
# SESSION GUARD (CENTRALIZED)
# --------------------------------------------------
require_login()

ctx = resolve_user_context(
    user=st.session_state.user,
    use_case_override=st.session_state.use_case,
    require_resume=False,
)

OUTPUTS_DIR = ctx.outputs_dir
RANKED_PATH = OUTPUTS_DIR / settings.outputs.ranked_jobs_file
STATE_PATH = OUTPUTS_DIR / ".last_seen_jobs.csv"
CORPUS_PATH = ctx.corpus_dir / settings.outputs.ranked_corpus_file

RECENCY_HALF_LIFE_DAYS = settings.ranking.recency_half_life_days

st.caption(f"Resolved path: users/{ctx.user}/{ctx.use_case}/outputs")

# --------------------------------------------------
# HELPERS (PURE, READ-ONLY)
# --------------------------------------------------
def normalize_date(val):
    try:
        return pd.to_datetime(val, utc=True)
    except Exception:
        return None


def format_date_only(val):
    try:
        return pd.to_datetime(val, utc=True).date().isoformat()
    except Exception:
        return ""


def resolve_apply_link(row):
    url = row.get("job_url_direct") or row.get("job_url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    return None


def normalize_site_display(site: str) -> str:
    if not isinstance(site, str):
        return ""
    s = site.lower().strip()
    if s == "linkedin":
        return "LinkedIn (API)"
    if s == "ats":
        return "ATS (LinkedIn)"
    return site


# --------------------------------------------------
# LOAD RANKED JOBS (READ-ONLY)
# --------------------------------------------------
if not RANKED_PATH.exists():
    st.warning(
        f"No ranked jobs found for:\n\n"
        f"User: **{ctx.user}**\n"
        f"Use case: **{ctx.use_case}**"
    )
    st.stop()

df = pd.read_csv(RANKED_PATH)
if df.empty:
    st.warning("Ranked jobs file is empty.")
    st.stop()

if "site" in df.columns:
    df["site"] = df["site"].apply(normalize_site_display)

# --------------------------------------------------
# DATE NORMALIZATION
# --------------------------------------------------
df["date_posted_dt"] = (
    df["date_posted"].apply(normalize_date)
    if "date_posted" in df.columns
    else None
)
df["date_posted_display"] = df["date_posted"].apply(format_date_only)

# --------------------------------------------------
# SCORE NORMALIZATION
# --------------------------------------------------
df["score_100"] = (df["final_score"] * 100).round().astype(int)
df["score_100"] = df["score_100"].clip(lower=1, upper=100)

# --------------------------------------------------
# NEW JOBS SINCE LAST BATCH RUN (READ-ONLY)
# --------------------------------------------------
current_ids = set(df.get("job_url", pd.Series()).dropna())

if STATE_PATH.exists():
    prev = pd.read_csv(STATE_PATH)
    prev_ids = set(prev.get("job_url", pd.Series()).dropna())
else:
    prev_ids = set()

new_ids = current_ids - prev_ids
new_jobs_df = df[df["job_url"].isin(new_ids)].copy()
new_jobs_df["date_posted_display"] = new_jobs_df["date_posted"].apply(format_date_only)

# --------------------------------------------------
# HIGH-LEVEL METRICS
# --------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Matches", len(df))
c2.metric("New Since Last Batch Run", len(new_jobs_df))
c3.metric("Top Score", df["score_100"].max())
c4.metric("Median Score", int(df["score_100"].median()))
c5.metric("Unique Companies", df["company"].nunique())

# --------------------------------------------------
# NEW JOBS
# --------------------------------------------------
st.subheader("🆕 New Jobs Since Last Batch Run")

if new_jobs_df.empty:
    st.info("No new jobs detected.")
else:
    nj = new_jobs_df.sort_values("final_score", ascending=False).head(30)
    nj["Apply"] = nj.apply(resolve_apply_link, axis=1)

    st.dataframe(
        nj.rename(columns={
            "title": "Role",
            "company": "Company",
            "location": "Location",
            "score_100": "Score",
            "date_posted_display": "Date Posted",
            "site": "Site",
        })[
            ["Role", "Company", "Location", "Score", "Date Posted", "Site", "Apply"]
        ],
        hide_index=True,
        column_config={
            "Apply": st.column_config.LinkColumn("Apply", display_text="Apply")
        },
        width="stretch",
    )

# --------------------------------------------------
# RANKED JOBS
# --------------------------------------------------
st.subheader("🏆 Ranked Jobs")

top_n = st.slider(
    "Show top N jobs",
    min_value=1,
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
        "date_posted_display": "Date Posted",
        "site": "Site",
        "skill_overlap_top": "Skill Overlap",
    })[
        ["Role", "Company", "Location", "Score", "Date Posted", "Site", "Apply", "Skill Overlap"]
    ],
    hide_index=True,
    column_config={
        "Apply": st.column_config.LinkColumn("Apply", display_text="Apply")
    },
    width="stretch",
)

# --------------------------------------------------
# RECENCY HISTOGRAM
# --------------------------------------------------
st.subheader("📆 Job Recency Distribution")

if df["date_posted_dt"].notna().any():
    rec_df = df.copy()
    rec_df["age_days"] = (
        datetime.now(timezone.utc) - rec_df["date_posted_dt"]
    ).dt.days

    hist = (
        alt.Chart(rec_df.dropna(subset=["age_days"]))
        .mark_bar()
        .encode(
            x=alt.X("age_days:Q", bin=alt.Bin(step=7), title="Job Age (days)"),
            y=alt.Y("count()", title="Job Count"),
            tooltip=["count()"],
        )
        .properties(height=250)
    )

    st.altair_chart(hist, width="stretch")
else:
    st.info("No valid date_posted data available.")

# --------------------------------------------------
# RECENCY DECAY CURVE
# --------------------------------------------------
st.subheader("📉 Recency Decay Curve (Sanity Check)")

curve_df = pd.DataFrame({"age_days": list(range(0, 91))})
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

st.altair_chart(curve, width="stretch")

# --------------------------------------------------
# CORPUS VIEW
# --------------------------------------------------
st.subheader("📚 Ranked Corpus (Global Similarity)")
st.caption("Scores are global similarity, not search-context fit.")

if CORPUS_PATH.exists():
    corpus = pd.read_csv(CORPUS_PATH)
    corpus["Apply"] = corpus.apply(resolve_apply_link, axis=1)
    corpus["date_posted_display"] = corpus["date_posted"].apply(format_date_only)

    if st.checkbox("Show corpus table"):
        st.dataframe(
            corpus.rename(columns={
                "title": "Role",
                "company": "Company",
                "location": "Location",
                "final_score": "Similarity Score",
                "date_posted_display": "Date Posted",
            })[
                ["Role", "Company", "Location", "Similarity Score", "Date Posted", "site", "Apply"]
            ],
            hide_index=True,
            column_config={
                "Apply": st.column_config.LinkColumn("Apply", display_text="Apply")
            },
            width="stretch",
        )
else:
    st.info("Corpus not found for this user/use case.")

# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------
st.download_button(
    "Download Ranked CSV",
    df.to_csv(index=False).encode(),
    file_name=settings.outputs.ranked_jobs_file,
)