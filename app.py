import streamlit as st
from pathlib import Path
import tempfile

from resume_parser import load_resume
from scrape_jobs import fetch_jobs
from match_engine import rank_jobs
from logger import setup_logger
from profiles import PROFILES

st.set_page_config(page_title="Calm-First Job Ranker", layout="wide")
st.title("🧘 Calm-First Job Ranker")

log_box = st.empty()
logs = []


def log_callback(msg):
    logs.append(msg)
    log_box.code("\n".join(logs[-20:]))


logger = setup_logger(log_callback)

# ---- Sidebar ----
with st.sidebar:
    st.header("Profile")
    profile_key = st.selectbox(
        "Profile",
        list(PROFILES.keys()),
        format_func=lambda k: PROFILES[k].name,
    )
    profile = PROFILES[profile_key]

    st.header("Search")
    country = st.selectbox("Country", ["India", "United States"])
    remote_only = st.checkbox("Remote only")
    hours_old = st.slider("Job freshness (hours)", 12, 720, 48)
    force_refresh = st.checkbox("Force fresh scrape")

    st.header("Quality filters")
    skip_junior = st.checkbox("Skip junior / intern roles", value=True)
    exclude_text = st.text_input(
        "Exclude keywords (comma separated)",
        "tax, marketing, sales, hr"
    )
    exclude_keywords = [k.strip() for k in exclude_text.split(",") if k.strip()]

    st.header("Company preferences")
    preferred_text = st.text_input(
        "High-priority companies (comma separated)",
        "Walmart, Optum, MSCI, Siemens"
    )
    preferred = [c.strip() for c in preferred_text.split(",") if c.strip()]

    deprioritized = st.multiselect(
        "Deprioritize companies",
        ["Accenture", "Wipro", "Infosys", "EPAM"],
    )
    view_mode = st.checkbox("View mode (use cached jobs only)", value=False)

search_terms = st.text_area(
    "Job search terms (one per line)",
    "machine learning engineer\nmlops engineer"
)
search_query = " OR ".join(f'"{t.strip()}"' for t in search_terms.splitlines() if t.strip())

resume_file = st.file_uploader("Upload resume (PDF or LaTeX)", ["pdf", "tex"])

if st.button("🔍 Run ranking"):
    if not resume_file:
        st.error("Upload a resume first")
        st.stop()

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(resume_file.name).suffix) as f:
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
    progress.progress(50)

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
    progress.progress(100)

    ranked = ranked.drop_duplicates(subset=["company", "title"]).head(30)

    st.success("Ranking complete")
    st.dataframe(
        ranked[["title", "company", "final_score", "explanation", "why_not_matched"]],
        use_container_width=True
    )

    st.download_button(
        "⬇️ Download CSV",
        ranked.to_csv(index=False).encode(),
        f"ranked_jobs_{username}_{profile_title}.csv",
    )