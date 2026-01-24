import streamlit as st
from pathlib import Path
from datetime import datetime
import hashlib
import json
import tempfile

from logger import setup_logger
from runner import run_job_ranking


# ---------------- App Setup ----------------
st.set_page_config(page_title="Calm-First Job Ranker", layout="wide")
st.title("🧘 Calm-First Job Ranker")


# ---------------- User & Paths ----------------
username = st.sidebar.text_input("Username", value="Uday_Lunawat").strip()
user_dir = Path("users") / username
profiles_dir = user_dir / "profiles"
profiles_dir.mkdir(parents=True, exist_ok=True)


# ---------------- Sidebar: Search Controls ----------------
st.sidebar.header("Search Controls")

country = st.sidebar.selectbox(
    "Country",
    ["India", "United States"],
)

remote_only = st.sidebar.checkbox("Remote only", value=False)
hours_old = st.sidebar.slider("Job freshness (hours)", 12, 168, 48, 12)
force_refresh = st.sidebar.checkbox("Force fresh scrape")


# ---------------- Profiles ----------------
st.sidebar.header("Profiles")

existing_profiles = sorted(
    [p.stem for p in profiles_dir.glob("*.json")]
)

selected_profile = st.sidebar.selectbox(
    "Load profile",
    ["<none>"] + existing_profiles
)

profile_data = None
if selected_profile != "<none>":
    profile_data = json.loads(
        (profiles_dir / f"{selected_profile}.json").read_text()
    )


# ---------------- Job Search Terms ----------------
st.subheader("Job Search Terms")

default_terms = (
    profile_data["search_terms"]
    if profile_data
    else ["machine learning engineer", "mlops engineer", "generative ai engineer"]
)

search_terms_input = st.text_area(
    "One role per line",
    value="\n".join(default_terms),
    height=120,
)

search_terms = [s.strip() for s in search_terms_input.splitlines() if s.strip()]
search_query = " OR ".join(f'"{t}"' for t in search_terms)


# ---------------- Company Preferences ----------------
st.subheader("Company Preferences")

tier_a = st.multiselect(
    "Top priority companies",
    ["msci", "siemens", "walmart", "optum", "google", "microsoft"],
    default=(
        profile_data["tiers"]["tier_a"]["companies"]
        if profile_data else ["msci", "siemens"]
    ),
)

tier_b = st.multiselect(
    "Medium priority companies",
    ["atlassian", "blackrock", "adobe", "salesforce"],
    default=(
        profile_data["tiers"]["tier_b"]["companies"]
        if profile_data else []
    ),
)

preferences = {
    "default_weight": 0.5,
    "tiers": {
        "tier_a": {"weight": 1.0, "companies": tier_a},
        "tier_b": {"weight": 0.85, "companies": tier_b},
    },
}


# ---------------- Save Profile ----------------
st.sidebar.subheader("Save Profile")

new_profile_name = st.sidebar.text_input(
    "Profile name",
    value=selected_profile if selected_profile != "<none>" else "",
)

if st.sidebar.button("💾 Save Profile"):
    if not new_profile_name:
        st.sidebar.error("Profile name required")
    else:
        profile_payload = {
            "search_terms": search_terms,
            "country": country,
            "remote_only": remote_only,
            "hours_old": hours_old,
            "default_weight": 0.5,
            "tiers": preferences["tiers"],
        }

        (profiles_dir / f"{new_profile_name}.json").write_text(
            json.dumps(profile_payload, indent=2)
        )

        st.sidebar.success(f"Saved profile '{new_profile_name}'")


# ---------------- Resume Upload ----------------
st.subheader("Resume")
resume_file = st.file_uploader("Upload Resume (PDF or LaTeX)", ["pdf", "tex"])


# ---------------- Logs ----------------
st.subheader("Live Logs")
log_placeholder = st.empty()
logs = []


def log_callback(msg):
    logs.append(msg)
    log_placeholder.code("\n".join(logs[-80:]))


logger = setup_logger(log_callback)


# ---------------- Run Ranking ----------------
if st.button("🔍 Run Ranking"):
    if not resume_file:
        st.error("Please upload a resume")
        st.stop()

    # Write resume to temp file for unified runner
    suffix = Path(resume_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(resume_file.read())
        resume_path = tmp.name

    ranked, output_file = run_job_ranking(
        resume_path=resume_path,
        search_query=search_query,
        country=country,
        hours_old=hours_old,
        remote_only=remote_only,
        preferences=preferences,
        force_refresh=force_refresh,
        logger=logger,
    )

    if ranked is None or ranked.empty:
        st.warning("No jobs found")
        st.stop()

    # ---------------- Deduplication ----------------
    ranked = (
        ranked
        .sort_values("final_score", ascending=False)
        .drop_duplicates(
            subset=["company", "title"],
            keep="first"
        )
        .reset_index(drop=True)
    )

    st.success("Ranking complete")

    st.dataframe(
        ranked[
            [
                "title",
                "company",
                "location",
                "final_score",
                "explanation",
                "job_url",
            ]
        ].head(30),
        use_container_width=True,
    )

    st.download_button(
        "⬇️ Download CSV",
        output_file.read_bytes(),
        output_file.name,
        "text/csv",
    )