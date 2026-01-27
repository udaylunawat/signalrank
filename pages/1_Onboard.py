# ================================
# FILE: pages/1_Onboard.py
# ================================
import streamlit as st
import yaml
from pathlib import Path

from config_loader import settings
from utils.ui import discover_users, discover_use_cases
from utils.session import save_session

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("🔐 Login / 👤 Onboard")

USERS_DIR = Path(settings.paths.users_dir)

# --------------------------------------------------
# SESSION STATE (DEFENSIVE INIT)
# --------------------------------------------------
from utils.session_guard import require_login

require_login()

# ==================================================
# LOGIN
# ==================================================
st.subheader("Login")

users = discover_users()

if users:
    default_user_idx = users.index(st.session_state.user) if st.session_state.user in users else 0
    user = st.selectbox("Select user", users, index=default_user_idx)

    use_cases = discover_use_cases(user)
    default_uc_idx = (
        use_cases.index(st.session_state.use_case)
        if st.session_state.use_case in use_cases
        else 0
    )
    use_case = st.selectbox("Select use case", use_cases, index=default_uc_idx)

    if st.button("Login", type="primary"):
        st.session_state.user = user
        st.session_state.use_case = use_case
        st.session_state.logged_in = True

        # 🔑 PERSIST LOGIN
        save_session(
            {
                "logged_in": True,
                "user": user,
                "use_case": use_case,
            }
        )

        st.success(f"Logged in as {user} / {use_case}")
        st.rerun()
else:
    st.info("No users exist yet. Please onboard below.")

# --------------------------------------------------
# LOGOUT (OPTIONAL BUT RECOMMENDED)
# --------------------------------------------------
if st.session_state.get("logged_in"):
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.use_case = None
        save_session({})
        st.rerun()

st.divider()

# ==================================================
# ONBOARD
# ==================================================
st.subheader("Create New User / Use Case")

new_user = st.text_input("New user name")
new_use_case = st.text_input("Use case", value="default")

uploaded_resume = st.file_uploader(
    "Upload resume (PDF or TEX)",
    type=["pdf", "tex"],
)

preferred = st.text_area(
    "Preferred companies (comma-separated)",
    placeholder="Cisco, Juniper, Cloudflare",
)

excluded = st.text_area(
    "Exclude keywords (comma-separated)",
    placeholder="helpdesk, L1 support, call center",
)

# --------------------------------------------------
# SEARCH ANCHORS (REQUIRED)
# --------------------------------------------------
anchors_text = st.text_area(
    "Search anchors (required)",
    placeholder=(
        "Examples:\n"
        "mlops engineer\n"
        "genai engineer\n"
        "llmops engineer\n\n"
        "Comma-separated also allowed:\n"
        "network engineer, datacenter network engineer"
    ),
    help=(
        "Search anchors define which job titles are considered valid "
        "for query planning in this use case.\n\n"
        "At least ONE anchor is required."
    ),
)

# Parse anchors (newline OR comma separated)
raw_anchors = []
for line in anchors_text.splitlines():
    raw_anchors.extend(line.split(","))

anchors = [
    a.strip().lower()
    for a in raw_anchors
    if len(a.strip()) >= 3
]

if anchors:
    st.success(f"{len(anchors)} search anchors detected")
else:
    st.warning("At least one search anchor is required")

# --------------------------------------------------
# CREATE USER / USE CASE
# --------------------------------------------------
if st.button("Create user / use case"):
    if not new_user:
        st.error("User name is required")
        st.stop()

    if not anchors:
        st.error("At least one valid search anchor is required")
        st.stop()

    base = USERS_DIR / new_user / new_use_case
    resume_dir = base / "resume"
    base.mkdir(parents=True, exist_ok=True)
    resume_dir.mkdir(exist_ok=True)

    if uploaded_resume:
        (resume_dir / uploaded_resume.name).write_bytes(uploaded_resume.read())

    override = {}

    if preferred:
        override.setdefault("company_scoring", {})["preferred_companies"] = [
            x.strip()
            for x in preferred.split(",")
            if x.strip()
        ]

    if excluded:
        override.setdefault("profiles", {}) \
            .setdefault("senior_ic", {})["exclude_keywords"] = [
                x.strip()
                for x in excluded.split(",")
                if x.strip()
            ]

    override.setdefault("search", {})["anchors"] = anchors

    (base / "settings.override.yaml").write_text(
        yaml.safe_dump(override, sort_keys=False)
    )

    st.success(f"Created {new_user} / {new_use_case}")

    # OPTIONAL: auto-login newly created user
    st.session_state.user = new_user
    st.session_state.use_case = new_use_case
    st.session_state.logged_in = True
    save_session(
        {
            "logged_in": True,
            "user": new_user,
            "use_case": new_use_case,
        }
    )
    st.rerun()