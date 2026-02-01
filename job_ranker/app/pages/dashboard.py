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
df["Category"] = (df["title"].fillna("") + " " + df["description"].fillna("")).apply(
    lambda t: classify_functional_role(t, ctx.config)
)

selected_category = st.selectbox(
    "Category filter",
    sorted(df["Category"].unique()),
)

df = df[df["Category"] == selected_category]


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
                    cat = classify_functional_role(f"{title} {desc}", ctx.config)
                    if cat_filter != "(any)" and cat != cat_filter:
                        continue

                    results.append(
                        {
                            "score": float(score),
                            "title": title,
                            "company": company,
                            "location": location,
                            "category": cat,
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
min_s, max_s = df["final_score"].min(), df["final_score"].max()
df["Score"] = (
    ((df["final_score"] - min_s) / (max_s - min_s) * 100).round().astype(int)
    if max_s > min_s
    else 100
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Jobs", len(df))
c2.metric("Top Score", df["Score"].max())
c3.metric("Median Score", int(df["Score"].median()))
c4.metric("Companies", df["company"].nunique())

st.divider()

top_n = st.slider("Show top N jobs", 5, min(200, len(df)), min(25, len(df)), 5)
view = st.radio("View", ["Table", "Cards"], horizontal=True)

show_df = df.sort_values("Score", ascending=False).head(top_n)

if view == "Table":
    table = show_df.copy()
    table["Apply"] = table["job_url"]

    table = table[
        [
            "title",
            "company",
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
            "company": "Company",
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
    for _, row in show_df.iterrows():
        cols = st.columns([8, 2])
        with cols[0]:
            st.markdown(f"""
**{row['title']}**  
{row['company']} · {row['location']} · `{row['Category']}`  
Score **{row['Score']}** · Posted {row['Posted']} · {row['days_old']} days ago
""")
        with cols[1]:
            st.link_button("Apply", row["job_url"])
        st.markdown("<hr style='opacity:0.25'>", unsafe_allow_html=True)
