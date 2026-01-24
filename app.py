import streamlit as st
from pathlib import Path
import tempfile
import pandas as pd

from resume_parser import load_resume
from scrape_jobs import fetch_jobs
from match_engine import rank_jobs
from logger import setup_logger
from profiles import PROFILES
from config import DEFAULT_COUNTRY, DEFAULT_HOURS_OLD

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Calm-First Job Ranker",
    layout="wide",
)

st.title("Calm-First Job Ranker")
st.caption("Surface senior, calm, enterprise AI roles — not noise.")

# --------------------------------------------------
# LOGGER (collapsed by default)
# --------------------------------------------------
with st.expander("Logs", expanded=False):
    log_box = st.empty()
logs = []


def log_callback(msg):
    logs.append(msg)
    log_box.code("\n".join(logs[-30:]))


logger = setup_logger(log_callback)

def build_display_df(ranked: pd.DataFrame) -> pd.DataFrame:
    df = ranked.copy()

    # Use explicit URL column
    df["Apply"] = df["job_url"].fillna(df.get("job_url_direct"))
    df["Role"] = df["title"]
    df["Company"] = df["company"]
    df["Location"] = df["location"].fillna("—")
    df["Score"] = df["final_score"].round(2)

    return df[["Role", "Company", "Location", "Score", "Apply", "explanation"]]

# --------------------------------------------------
# SIDEBAR – CONFIGURATION
# --------------------------------------------------
with st.sidebar:
    st.header("Workspace")
    user_id = st.text_input("User ID", "example")

    st.divider()
    st.header("Profile")
    profile_key = st.selectbox(
        "Role profile",
        list(PROFILES.keys()),
        format_func=lambda k: PROFILES[k].name,
    )
    profile = PROFILES[profile_key]

    st.divider()
    st.header("Search Scope")
    country = st.selectbox("Country", [DEFAULT_COUNTRY, "United States"])
    remote_only = st.checkbox("Remote only")
    hours_old = st.slider("Job freshness (hours)", 12, 720, DEFAULT_HOURS_OLD)
    force_refresh = st.checkbox("Force fresh scrape")

    st.divider()
    st.header("Quality Filters")
    skip_junior = st.checkbox("Skip junior / intern roles", value=True)
    exclude_text = st.text_input(
        "Exclude keywords",
        "tax, marketing, sales, hr",
        help="Comma-separated keywords to exclude",
    )
    exclude_keywords = [k.strip() for k in exclude_text.split(",") if k.strip()]

    st.divider()
    st.header("Company Preferences")
    preferred_text = st.text_input(
        "High-priority companies",
        "Walmart, Optum, MSCI, Siemens",
    )
    preferred = [c.strip() for c in preferred_text.split(",") if c.strip()]

    deprioritized = st.multiselect(
        "Deprioritize companies",
        ["Accenture", "Wipro", "Infosys", "EPAM"],
    )

    st.divider()
    st.header("Result Controls")
    max_results = st.slider("Max results", 10, 100, 30)
    min_score = st.slider("Minimum score", 0.0, 1.0, 0.25, 0.05)
    show_explanations = st.checkbox("Show explanations", value=True)
    view_mode = st.checkbox("View cached jobs only")

# --------------------------------------------------
# MAIN INPUTS
# --------------------------------------------------
st.subheader("Job Search")

search_terms = st.text_area(
    "Job titles / keywords (one per line)",
    "mlops engineer\ngenai\nllmops\naiml engineer",
    height=120,
)

search_query = " OR ".join(
    f'"{t.strip()}"'
    for t in search_terms.splitlines()
    if t.strip()
)

resume_file = st.file_uploader(
    "Upload resume (PDF or LaTeX)",
    ["pdf", "tex"],
)

# --------------------------------------------------
# RUN PIPELINE
# --------------------------------------------------
if st.button("Run ranking", type="primary"):
    if not resume_file:
        st.error("Please upload a resume.")
        st.stop()

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=Path(resume_file.name).suffix,
    ) as f:
        f.write(resume_file.read())
        resume_path = f.name

    with st.spinner("Parsing resume"):
        resume_text = load_resume(resume_path)

    progress = st.progress(0)

    jobs_df = fetch_jobs(
        search_query=search_query,
        country=country,
        hours_old=hours_old,
        remote_only=remote_only,
        profile=profile,
        force_refresh=force_refresh,
        logger=logger,
        view_mode=view_mode,
    )
    progress.progress(40)

    profile.workspace_dir = f"workspaces/{user_id}/{profile.name}"
    profile.skip_junior_roles = skip_junior
    profile.exclude_keywords = exclude_keywords

    ranked = rank_jobs(
        resume_text,
        jobs_df,
        preferences={
            "preferred": preferred,
            "deprioritized": deprioritized,
        },
        profile=profile,
        logger=logger,
    )
    progress.progress(80)

    # --------------------------------------------------
    # POST-PROCESS
    # --------------------------------------------------
    ranked = (
        ranked
        .drop_duplicates(subset=["company", "title"])
        .query("final_score >= @min_score")
        .head(max_results)
        .reset_index(drop=True)
    )

    progress.progress(100)
    st.success(
        f"Found {len(ranked)} strong matches "
        f"(out of {len(jobs_df)} filtered jobs)"
    )

    # --------------------------------------------------
    # RESULTS TABLE (APPLY-READY)
    # --------------------------------------------------
    st.subheader("Top Matches")

    def make_link(row):
        url = row.get("job_url") or row.get("job_url_direct")
        if pd.isna(url) or not url:
            return row["title"]
        return f"[{row['title']}]({url})"

    display_df = ranked.copy()
    display_df["Role"] = display_df.apply(make_link, axis=1)

    columns = [
        "Role",
        "company",
        "location",
        "final_score",
    ]

    if show_explanations:
        columns.append("explanation")

    display_df = build_display_df(ranked)

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "Role": st.column_config.TextColumn(
                "Role",
                width="large",
            ),
            "Company": st.column_config.TextColumn(
                "Company",
                width="medium",
            ),
            "Location": st.column_config.TextColumn(
                "Location",
                width="small",
            ),
            "Score": st.column_config.ProgressColumn(
                "Fit Score",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
            "Apply": st.column_config.LinkColumn(
                "Apply",
                help="Open job posting",
                display_text="Apply",
            ),
            "explanation": st.column_config.TextColumn(
                "Why this fits",
                width="large",
            ),
        },
    )

    # --------------------------------------------------
    # EXPANDABLE JOB DETAILS
    # --------------------------------------------------
    st.subheader("Job Details")

    for _, row in ranked.iterrows():
        with st.expander(f"{row['title']} — {row['company']}"):
            if row.get("job_url"):
                st.markdown(f"**Apply:** {row['job_url']}")
            st.markdown(f"**Location:** {row.get('location', 'N/A')}")
            st.markdown(f"**Score:** {row['final_score']:.2f}")
            st.markdown("---")
            st.markdown(row.get("description", "")[:4000])

    # --------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------
    st.download_button(
        "Download CSV",
        ranked.to_csv(index=False).encode(),
        f"ranked_jobs_{user_id}_{profile.name}.csv",
    )