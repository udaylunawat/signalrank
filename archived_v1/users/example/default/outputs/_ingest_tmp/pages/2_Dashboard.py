# ================================
# FILE: pages/2_Dashboard.py
# ================================
import math
from datetime import datetime, timezone
from io import StringIO

import altair as alt
import duckdb
import pandas as pd
import streamlit as st
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
# SESSION GUARD
# --------------------------------------------------
require_login()

ctx = resolve_user_context(
    user=st.session_state.user,
    use_case_override=st.session_state.use_case,
    require_resume=False,
)

RECENCY_HALF_LIFE_DAYS = settings.ranking.recency_half_life_days

st.caption(f"Resolved path: users/{ctx.user}/{ctx.use_case}")


# --------------------------------------------------
# HELPERS (PURE)
# --------------------------------------------------
def normalize_date(val):
    if val is None or val == "":
        return None

    # epoch milliseconds
    if isinstance(val, (int, float)):
        return pd.to_datetime(val, unit="ms", utc=True, errors="coerce")

    return pd.to_datetime(val, utc=True, errors="coerce")


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
# LOAD DUCKDB
# --------------------------------------------------
db_path = ctx.base_dir / "jobs.duckdb"
if not db_path.exists():
    st.warning(
        f"No ranked jobs found for:\n\n"
        f"User: **{ctx.user}**\n"
        f"Use case: **{ctx.use_case}**"
    )
    st.stop()

try:
    con = duckdb.connect(str(db_path))
except duckdb.IOException:
    st.warning("Database is being updated. Please refresh in a moment.")
    st.stop()

# --------------------------------------------------
# LOAD LATEST RANKED SNAPSHOT
# --------------------------------------------------
rows = con.execute(
    """
    WITH latest_run AS (
        SELECT run_id
        FROM ranked_snapshots
        WHERE user = ? AND use_case = ?
        ORDER BY created_at DESC
        LIMIT 1
    )
    SELECT payload
    FROM ranked_snapshots
    WHERE run_id = (SELECT run_id FROM latest_run)
      AND user = ?
      AND use_case = ?
    """,
    [ctx.user, ctx.use_case, ctx.user, ctx.use_case],
).df()

if rows.empty:
    st.warning("No ranked jobs found yet. Run the batch pipeline first.")
    st.stop()

records = [pd.read_json(StringIO(p), typ="series") for p in rows["payload"]]
df = pd.DataFrame(records)

if df.empty:
    st.warning("Ranked snapshot is empty.")
    st.stop()

# --------------------------------------------------
# NORMALIZE DISPLAY FIELDS
# --------------------------------------------------
if "site" in df.columns:
    df["site"] = df["site"].apply(normalize_site_display)

df["date_posted_dt"] = (
    df["date_posted"].apply(normalize_date) if "date_posted" in df.columns else None
)
df["date_posted_display"] = df["date_posted"].apply(format_date_only)

df["score_100"] = (df["final_score"] * 100).round().astype(int)
df["score_100"] = df["score_100"].clip(lower=1, upper=100)

# --------------------------------------------------
# METRICS
# --------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Matches", len(df))
c2.metric("Top Score", df["score_100"].max())
c3.metric("Median Score", int(df["score_100"].median()))
c4.metric("Unique Companies", df["company"].nunique())

# --------------------------------------------------
# NEW SINCE LAST RUN (PURE SQL DIFF)
# --------------------------------------------------
st.subheader("🆕 New Since Last Run")

new_rows = con.execute(
    """
    WITH runs AS (
        SELECT DISTINCT run_id, created_at
        FROM ranked_snapshots
        WHERE user = ? AND use_case = ?
        ORDER BY created_at DESC
        LIMIT 2
    ),
    latest AS (
        SELECT job_url, payload
        FROM ranked_snapshots
        WHERE run_id = (SELECT run_id FROM runs LIMIT 1)
    ),
    previous AS (
        SELECT job_url
        FROM ranked_snapshots
        WHERE run_id = (SELECT run_id FROM runs OFFSET 1 LIMIT 1)
    )
    SELECT l.payload
    FROM latest l
    LEFT JOIN previous p
      ON l.job_url = p.job_url
    WHERE p.job_url IS NULL
    """,
    [ctx.user, ctx.use_case],
).df()

if new_rows.empty:
    st.info("No new jobs since last run.")
else:
    records = [pd.read_json(StringIO(p), typ="series") for p in rows["payload"]]
    new_df = pd.DataFrame(records)

    new_df["Apply"] = new_df.apply(resolve_apply_link, axis=1)
    new_df["score_100"] = (new_df["final_score"] * 100).round().astype(int)

    st.dataframe(
        new_df.rename(
            columns={
                "title": "Role",
                "company": "Company",
                "location": "Location",
                "score_100": "Score",
            }
        )[["Role", "Company", "Location", "Score", "Apply"]],
        hide_index=True,
        column_config={"Apply": st.column_config.LinkColumn("Apply")},
        width="stretch",
    )
# --------------------------------------------------
# RANKED JOBS (CARDS / TABLE + ANNOTATIONS)
# --------------------------------------------------
st.subheader("🏆 Ranked Jobs")

from storage.db import JobStore

store = JobStore(db_path)  # ONE instance per render

# -------------------------------
# View toggle
# -------------------------------
view_mode = st.radio(
    "View mode",
    options=["Cards", "Table"],
    horizontal=True,
    index=0,
)

top_n = st.slider(
    "Show top N jobs",
    min_value=1,
    max_value=min(200, len(df)),
    value=min(1, len(df)),
    step=10,
)

display_df = (
    df.sort_values("final_score", ascending=False).head(top_n).reset_index(drop=True)
)

display_df["Apply"] = display_df.apply(resolve_apply_link, axis=1)

# -------------------------------
# Load annotations once
# -------------------------------
annotations = con.execute(
    """
    SELECT job_url, starred, hidden
    FROM annotations
    WHERE user = ? AND use_case = ?
    """,
    [ctx.user, ctx.use_case],
).df()

ann_map = {r["job_url"]: r for _, r in annotations.iterrows()}

# ==================================================
# CARDS VIEW (default)
# ==================================================
if view_mode == "Cards":
    for idx, row in display_df.iterrows():
        ann = ann_map.get(row["job_url"], {})
        is_starred = bool(ann.get("starred", False))

        with st.container():
            cols = st.columns([7, 1.2, 1.2])

            # -------- LEFT: job info --------
            with cols[0]:
                st.markdown(f"""
**{row['title']}**  
{row['company']} · {row['location']}  
Score: `{row['score_100']}` · Posted: `{row['date_posted_display']}`
""")

                if row["Apply"]:
                    st.markdown(f"[Apply]({row['Apply']})")

                overlap = row.get("skill_overlap_top")
                if isinstance(overlap, list) and overlap:
                    st.caption("Skill overlap: " + ", ".join(overlap))

                if is_starred:
                    st.caption("⭐ Starred")

            # -------- STAR --------
            with cols[1]:
                star_label = "⭐ Starred" if is_starred else "⭐ Star"
                if st.button(star_label, key=f"star_{row['job_url']}"):
                    store.annotate(
                        user=ctx.user,
                        use_case=ctx.use_case,
                        job_url=row["job_url"],
                        starred=not is_starred,
                    )
                    st.toast("Star updated")
                    st.rerun()

            # -------- HIDE --------
            with cols[2]:
                if st.button("🙈 Hide", key=f"hide_{row['job_url']}"):
                    store.annotate(
                        user=ctx.user,
                        use_case=ctx.use_case,
                        job_url=row["job_url"],
                        hidden=True,
                    )
                    st.toast("Hidden")
                    st.rerun()

            st.divider()

# ==================================================
# TABLE VIEW (compact)
# ==================================================
else:
    table_df = display_df.copy()

    # Annotation columns
    table_df["Starred"] = table_df["job_url"].apply(
        lambda u: "⭐" if ann_map.get(u, {}).get("starred") else ""
    )

    table_df["Hide"] = table_df["job_url"].apply(lambda u: "🙈")

    table_df = table_df.rename(
        columns={
            "title": "Role",
            "company": "Company",
            "location": "Location",
            "score_100": "Score",
            "date_posted_display": "Date Posted",
        }
    )

    st.dataframe(
        table_df[
            ["Starred", "Role", "Company", "Location", "Score", "Date Posted", "Apply"]
        ],
        hide_index=True,
        column_config={
            "Apply": st.column_config.LinkColumn("Apply"),
        },
        width="stretch",
    )

    st.caption("Table view is read-only. " "Use **Cards view** to Star or Hide jobs.")

# --------------------------------------------------
# RECENCY HISTOGRAM
# --------------------------------------------------
st.subheader("📆 Job Recency Distribution")

if df["date_posted_dt"].notna().any():
    rec_df = df.copy()
    rec_df["age_days"] = (datetime.now(timezone.utc) - rec_df["date_posted_dt"]).dt.days

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

    st.altair_chart(hist, use_container_width=True)
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

st.altair_chart(curve)

# --------------------------------------------------
# RANKED CORPUS (GLOBAL SIMILARITY)
# --------------------------------------------------
st.subheader("📚 Ranked Corpus (Global Similarity)")
st.caption("Scores are global similarity, not search-context fit.")

corpus_rows = con.execute(
    """
    SELECT *
    FROM jobs_corpus
    WHERE user = ? AND use_case = ?
    """,
    [ctx.user, ctx.use_case],
).df()

if corpus_rows.empty:
    st.info("Corpus is empty for this user/use case.")
else:
    corpus_view = corpus_rows.copy()

    # Normalize site
    if "site" in corpus_view.columns:
        corpus_view["site"] = corpus_view["site"].apply(normalize_site_display)

    # Date display (explicit)
    corpus_view["Date Posted"] = corpus_view["date_posted"].apply(format_date_only)

    # Apply link (explicit)
    corpus_view["Apply"] = corpus_view.apply(resolve_apply_link, axis=1)

    # Company link (prefer direct)
    corpus_view["Company Link"] = corpus_view.apply(
        lambda r: r.get("company_url_direct") or r.get("company_url"),
        axis=1,
    )

    corpus_view = corpus_view.rename(
        columns={
            "title": "Role",
            "company": "Company",
            "location": "Location",
        }
    )

    if st.checkbox("Show corpus table"):
        st.dataframe(
            corpus_view[
                [
                    "Role",
                    "Company",
                    "Company Link",
                    "Location",
                    "Date Posted",
                    "site",
                    "Apply",
                ]
            ],
            hide_index=True,
            column_config={
                "Apply": st.column_config.LinkColumn(
                    "Apply",
                    display_text="Apply",
                ),
                "Company Link": st.column_config.LinkColumn(
                    "Company",
                    display_text="Company",
                ),
            },
            width="stretch",
        )

# --------------------------------------------------
# DOWNLOAD (ON-DEMAND EXPORT)
# --------------------------------------------------
st.download_button(
    "Download Ranked CSV",
    df.to_csv(index=False).encode(),
    file_name="ranked_jobs.csv",
)
