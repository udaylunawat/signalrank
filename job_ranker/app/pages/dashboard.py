# app/pages/dashboard.py
import re
from datetime import datetime
from io import StringIO

import numpy as np
import pandas as pd
import streamlit as st

from job_ranker.app.db import get_ui_db
from job_ranker.app.session import get_session
from job_ranker.batch.context import resolve_ui_context
from job_ranker.domain.embed_math import cosine_similarity
from job_ranker.domain.roles import classify_functional_role

if "semantic_results" not in st.session_state:
    st.session_state.semantic_results = None

# ==================================================
# Page config
# ==================================================
st.set_page_config(layout="wide")
st.title("📊 Dashboard")


# ==================================================
# Helpers
# ==================================================
def format_date(val):
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.date().isoformat()
    try:
        return pd.to_datetime(val, utc=True).date().isoformat()
    except Exception:
        return ""


def tokenize(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()
    return set(re.findall(r"[a-zA-Z]{3,}", text.lower()))


def explain_overlap(resume_text: str, job_text: str, k: int = 6) -> str:
    r = tokenize(resume_text)
    j = tokenize(job_text)
    return ", ".join(sorted(r & j)[:k])


# ==================================================
# Cached dashboard dataframe (SAFE)
# ==================================================
@st.cache_data(show_spinner=False)
def load_dashboard_df(run_id: str, user: str, use_case: str) -> pd.DataFrame:
    con = get_ui_db()

    # ---- Load ranked payloads ----
    rows = con.execute(
        "SELECT payload FROM run_results WHERE run_id = ?",
        [run_id],
    ).df()

    records = [pd.read_json(StringIO(p), typ="series") for p in rows["payload"]]
    df = pd.DataFrame(records)

    if df.empty:
        return df

    # ---- Drop any payload date to avoid suffix conflicts ----
    if "date_posted" in df.columns:
        df = df.drop(columns=["date_posted"])

    # ---- Attach authoritative dates ----
    dates = con.execute(
        """
        SELECT job_url, date_posted
        FROM jobs_raw
        WHERE user = ? AND use_case = ?
        """,
        [user, use_case],
    ).df()

    df = df.merge(dates, on="job_url", how="left")

    # ---- Normalize dates ----
    df["date_posted"] = pd.to_datetime(
        df["date_posted"],
        errors="coerce",
        utc=True,
    )

    df.loc[df["date_posted"] <= pd.Timestamp("1971-01-01", tz="UTC"), "date_posted"] = (
        pd.NaT
    )

    # ---- Deduplicate by title+company (case-insensitive, keep highest score) ----
    df["_dedup_key"] = (
        df["title"].str.strip().str.lower() + "|" + df["company"].str.strip().str.lower()
    )
    df = df.sort_values("final_score", ascending=False).drop_duplicates(
        subset="_dedup_key", keep="first"
    )
    df = df.drop(columns=["_dedup_key"])

    # ---- Derived fields ----
    now = pd.Timestamp.utcnow()
    df["Posted"] = (
        df["date_posted"].dt.date.astype(str).where(df["date_posted"].notna(), "")
    )
    df["days_old"] = (now - df["date_posted"]).dt.days.where(df["date_posted"].notna())

    return df


# ==================================================
# Sidebar: Session
# ==================================================
with st.sidebar:
    st.header("Session")
    user, use_case = get_session()


# ==================================================
# Resolve UI context + DB
# ==================================================
ctx = resolve_ui_context(user, use_case)
con = get_ui_db()


# ==================================================
# Latest successful run
# ==================================================
row = con.execute(
    """
    SELECT run_id, finished_at
    FROM runs
    WHERE user = ? AND use_case = ? AND status = 'success'
    ORDER BY finished_at DESC
    LIMIT 1
    """,
    [user, use_case],
).fetchone()

if not row:
    st.info("No successful runs yet.")
    st.stop()

run_id, finished_at = row
st.success(f"Showing run `{run_id}` finished at `{finished_at}`")


# ==================================================
# Load dashboard dataframe (CACHED)
# ==================================================
df = load_dashboard_df(run_id, user, use_case)

if df.empty:
    st.warning("Run has no results.")
    st.stop()

for col in ["title", "description", "company", "location"]:
    if col not in df:
        df[col] = ""


# ==================================================
# Category filter
# ==================================================
# ==================================================
# Category (multi-valued)
# ==================================================
def classify_categories(text: str, cfg: dict) -> list[str]:
    """
    Conservative multi-label wrapper.
    Reuses existing classifier, but allows extension later.
    """
    primary = classify_functional_role(text, cfg)
    return [primary] if primary else []


df["Categories"] = (df["title"].fillna("") + " " + df["description"].fillna("")).apply(
    lambda t: classify_categories(t, ctx.config)
)

# Stable, display-only column
df["Category"] = df["Categories"].apply(lambda xs: ", ".join(sorted(xs)))

# ==================================================
# Category filter (multi-select)
# ==================================================
all_categories = sorted({c for cats in df["Categories"] for c in cats})
st.caption("Select one or more categories. Jobs matching any selection are shown.")
selected_categories = st.multiselect(
    "Category filter",
    options=all_categories,
    default=all_categories,  # show everything by default
)

if selected_categories:
    df = df[
        df["Categories"].apply(lambda cats: any(c in cats for c in selected_categories))
    ]


# ==================================================
# 🔍 Semantic Explorer (DB-only)
# ==================================================
st.divider()
st.subheader("🔍 Semantic Explorer — Find jobs similar to my resume")

with st.expander("Semantic Explorer", expanded=False):
    cat_filter = st.selectbox(
        "Filter by category",
        ["(any)"] + sorted(df["Category"].unique()),
    )

    top_k = st.slider("Top K matches", 5, 50, 20, 5)

    if st.button("Find jobs similar to my resume"):
        row = con.execute(
            """
            SELECT payload
            FROM resume_distillations
            WHERE user = ? AND use_case = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [ctx.user, ctx.use_case],
        ).fetchone()

        if not row:
            st.warning("Resume embedding not available yet. Run batch once.")
            st.session_state.semantic_results = []
        else:
            q_emb = np.array(pd.read_json(row[0]), dtype="float32")

            raw = con.execute(
                """
                SELECT
                j.job_url,
                j.title,
                j.company,
                j.location,
                j.description,
                e.vector
                FROM jobs_raw j
                JOIN embeddings e
                ON e.text_fp = sha256(
                    'ROLE: ' || j.title || '\nRESPONSIBILITIES: ' || j.description
                )
                WHERE e.user = ? AND e.use_case = ? AND e.cfg_fp = ?
                """,
                [ctx.user, ctx.use_case, ctx.config_fp],
            ).fetchall()

            results = []
            if raw:
                vecs = np.array([r[-1] for r in raw], dtype="float32")
                sims = cosine_similarity(q_emb, vecs)

                for (job_url, title, company, location, desc, _), score in zip(
                    raw, sims
                ):
                    cats = classify_categories(f"{title} {desc}", ctx.config)

                    if selected_categories and not any(
                        c in cats for c in selected_categories
                    ):
                        continue

                    results.append(
                        {
                            "score": float(score),
                            "title": title,
                            "company": company,
                            "location": location,
                            "category": ", ".join(sorted(cats)),
                            "job_url": job_url,
                            "explain": explain_overlap(ctx.resume_text, desc),
                        }
                    )

            st.session_state.semantic_results = sorted(
                results, key=lambda x: x["score"], reverse=True
            )[:top_k]

    results = st.session_state.semantic_results

    if results:
        st.divider()
        st.markdown("### Semantic Matches")

        for r in results:
            st.markdown(f"""
    **{r['title']}**  
    {r['company']} · {r['location']} · `{r['category']}`  
    Similarity **{r['score']:.3f}**  
    _Overlap_: {r['explain'] or "—"}
    """)
            st.link_button("Apply", r["job_url"])
            st.markdown("<hr style='opacity:0.25'>", unsafe_allow_html=True)
# ==================================================
# Ranking view
# ==================================================
df["Score"] = df["final_score"].round(1)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Jobs", len(df))
c2.metric("Top Score", df["Score"].max())
c3.metric("Median Score", int(df["Score"].median()))
# Normalize company/location for display (title-case, strip whitespace)
df["company_norm"] = df["company"].fillna("Unknown").str.strip().str.title()
df["location"] = df["location"].fillna("").str.strip().str.title()

c4.metric("Companies", df["company_norm"].nunique())

# ==================================================
# Charts
# ==================================================
st.divider()
st.subheader("Analytics")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**Top 20 Companies by Job Count**")
    company_counts = (
        df["company_norm"]
        .value_counts()
        .head(20)
        .reset_index()
    )
    company_counts.columns = ["Company", "Jobs"]
    st.bar_chart(company_counts, x="Company", y="Jobs", horizontal=True)

with chart_col2:
    st.markdown("**Avg Score by Top 20 Companies**")
    avg_score = (
        df.groupby("company_norm")["Score"]
        .agg(["mean", "count"])
        .query("count >= 2")
        .sort_values("mean", ascending=False)
        .head(20)
        .reset_index()
    )
    avg_score.columns = ["Company", "Avg Score", "Count"]
    st.bar_chart(avg_score, x="Company", y="Avg Score", horizontal=True)

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.markdown("**Jobs by Category**")
    cat_counts = (
        df["Category"]
        .value_counts()
        .reset_index()
    )
    cat_counts.columns = ["Category", "Jobs"]
    st.bar_chart(cat_counts, x="Category", y="Jobs", horizontal=True)

with chart_col4:
    st.markdown("**Score Distribution**")
    bins = list(range(0, 101, 5))
    labels = [f"{b}-{b+5}" for b in bins[:-1]]
    score_hist = (
        pd.cut(df["Score"], bins=bins, labels=labels, include_lowest=True)
        .value_counts()
        .reindex(labels, fill_value=0)
        .reset_index()
    )
    score_hist.columns = ["Score Range", "Count"]
    st.bar_chart(score_hist, x="Score Range", y="Count")

st.divider()

top_n = st.slider("Show top N jobs", 1, min(2000, len(df)), min(25, len(df)), 1)
view = st.radio("View", ["Table", "Cards"], horizontal=True)

show_df = df.sort_values("Score", ascending=False).head(top_n)

if view == "Table":
    table = show_df.copy()
    table["Apply"] = table["job_url_direct"].fillna(table["job_url"])

    table = table[
        [
            "title",
            "company_norm",
            "location",
            "Category",
            "Posted",
            "days_old",
            "Score",
            "Apply",
        ]
    ].rename(
        columns={
            "title": "Role",
            "company_norm": "Company",
            "location": "Location",
            "days_old": "Days Old",
        }
    )

    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Apply": st.column_config.LinkColumn("Apply", display_text="Apply ↗")
        },
    )
else:
    _has_breakdown = all(
        c in show_df.columns
        for c in ["skills_score", "company_score", "seniority_score_dim", "location_score", "recency_score"]
    )
    _dim_info = [
        ("Skills", "skills_score", 0.40),
        ("Company", "company_score", 0.20),
        ("Seniority", "seniority_score_dim", 0.15),
        ("Location", "location_score", 0.15),
        ("Recency", "recency_score", 0.10),
    ]

    for _, row in show_df.iterrows():
        cols = st.columns([8, 2])
        with cols[0]:
            st.markdown(f"""
**{row['title']}**
{row['company_norm']} · {row['location']} · `{row['Category']}`
Score **{row['Score']}** · Posted {row['Posted']} · {row['days_old']} days ago
""")
        with cols[1]:
            st.link_button(
                "Apply",
                row["job_url_direct"] or row["job_url"],
            )

        if _has_breakdown:
            with st.expander("Score breakdown"):
                for label, col, weight in _dim_info:
                    val = row[col]
                    contrib = val * weight
                    st.progress(val / 100, text=f"{label}: {val:.0f}/100 (w={weight}) = {contrib:.1f}")

        st.markdown("<hr style='opacity:0.25'>", unsafe_allow_html=True)
