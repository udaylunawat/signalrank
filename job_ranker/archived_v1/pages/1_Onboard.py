# ================================
# FILE: pages/1_Onboard.py
# ================================
from pathlib import Path

import streamlit as st
import yaml
from config_loader import settings
from utils.session import save_session
from utils.session_guard import require_login
from utils.ui import discover_use_cases, discover_users

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("🔐 Login / 👤 Onboard")

USERS_DIR = Path(settings.paths.users_dir)

# --------------------------------------------------
# SESSION GUARD
# --------------------------------------------------
require_login()

# ==================================================
# LOGIN
# ==================================================
st.subheader("Login")

users = discover_users()

if users:
    default_user_idx = (
        users.index(st.session_state.user) if st.session_state.user in users else 0
    )
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
        save_session({"logged_in": True, "user": user, "use_case": use_case})
        st.rerun()
else:
    st.info("No users exist yet. Please onboard below.")

st.divider()

# ==================================================
# ONBOARD
# ==================================================
st.subheader("Create New User / Use Case")

new_user = st.text_input("New user name")
new_use_case = st.text_input("Use case", value="default")

uploaded_resume = st.file_uploader("Upload resume (PDF or TEX)", type=["pdf", "tex"])

# --------------------------------------------------
# ROLE PRESETS (NEW – EXPLICIT)
# --------------------------------------------------
st.markdown("### 🧠 Role Preset (Recommended)")

PRESETS = {
    "Strategy / Innovation": {
        "allowed_roles": ["product", "customer_facing", "software_general"],
        "anchors": [
            "innovation lead",
            "technology strategist",
            "digital transformation lead",
            "head of innovation",
            "r&d lead",
        ],
        "min_semantic": 0.40,
        "description": "Filters out hands-on engineering noise. Focuses on strategy, GTM, architecture framing.",
    },
    "Product Management": {
        "allowed_roles": ["product", "customer_facing", "software_general"],
        "anchors": [
            "technical product manager",
            "product manager",
            "product owner",
        ],
        "min_semantic": 0.35,
        "description": "Optimized for TPM / PM roles with technical depth.",
    },
    "AI / ML Engineering": {
        "allowed_roles": ["agentic_systems", "mlops_llmops", "software_general"],
        "anchors": [
            "ml engineer",
            "mlops engineer",
            "genai engineer",
            "llm engineer",
        ],
        "min_semantic": 0.30,
        "description": "Hands-on AI, MLOps, LLM systems. Excludes product-heavy roles.",
    },
    "Architecture / Platform": {
        "allowed_roles": ["platform_devops", "software_general", "customer_facing"],
        "anchors": [
            "solutions architect",
            "enterprise architect",
            "platform architect",
        ],
        "min_semantic": 0.35,
        "description": "System-level ownership, platform and infra design.",
    },
    "Network / Infra Engineer": {
        "allowed_roles": ["platform_devops", "software_general"],
        "anchors": [
            "network engineer",
            "infrastructure engineer",
            "site reliability engineer",
        ],
        "min_semantic": 0.30,
        "description": "Infra-first roles. Minimal AI/product contamination.",
    },
}

preset_name = st.selectbox(
    "Choose a starting preset",
    options=list(PRESETS.keys()),
    index=0,
)

preset = PRESETS[preset_name]

st.info(f"Preset intent: {preset['description']}")

# --------------------------------------------------
# MATCH STRICTNESS (OVERRIDEABLE)
# --------------------------------------------------
st.markdown("### 🎚 Matching Strictness")

strictness = st.select_slider(
    "Semantic strictness",
    options=["Broad", "Balanced", "Strict"],
    value="Balanced",
)

STRICTNESS_MAP = {
    "Broad": preset["min_semantic"] - 0.05,
    "Balanced": preset["min_semantic"],
    "Strict": preset["min_semantic"] + 0.10,
}

# --------------------------------------------------
# FUNCTIONAL ROLE ALLOWLIST
# --------------------------------------------------
st.markdown("### 🧭 Allowed Functional Roles")

ROLE_LABELS = {
    "product": "Product",
    "customer_facing": "Customer-facing / Solutions",
    "software_general": "General Software",
    "agentic_systems": "Agentic / AI Systems",
    "mlops_llmops": "MLOps / LLMOps",
    "platform_devops": "Platform / DevOps",
}

allowed_roles = st.multiselect(
    "These roles are allowed to enter ranking",
    options=list(ROLE_LABELS.keys()),
    format_func=lambda r: ROLE_LABELS[r],
    default=preset["allowed_roles"],
    help="Anything not selected here is dropped BEFORE embeddings.",
)

# --------------------------------------------------
# SEARCH ANCHORS
# --------------------------------------------------
st.markdown("### 🔍 Search Anchors (Editable)")

anchors_text = st.text_area(
    "Canonical job titles used for search planning",
    value="\n".join(preset["anchors"]),
    help="These drive scraping + query expansion. Edit freely.",
)

anchors = [
    a.strip().lower()
    for a in anchors_text.replace("\n", ",").split(",")
    if len(a.strip()) >= 3
]

if not anchors:
    st.warning("At least one search anchor is required")

# --------------------------------------------------
# COMPANIES
# --------------------------------------------------
st.markdown("### 🏢 Company Preferences")

preferred = st.text_area("Preferred companies (comma-separated)")
excluded = st.text_area("Exclude keywords (comma-separated)")

# --------------------------------------------------
# CREATE
# --------------------------------------------------
if st.button("Create user / use case"):
    if not new_user or not anchors:
        st.error("User name and anchors are required")
        st.stop()

    base = USERS_DIR / new_user / new_use_case
    resume_dir = base / "resume"
    base.mkdir(parents=True, exist_ok=True)
    resume_dir.mkdir(exist_ok=True)

    if uploaded_resume:
        (resume_dir / uploaded_resume.name).write_bytes(uploaded_resume.read())

    # ----------------------------------
    # BUILD OVERRIDE
    # ----------------------------------
    override = {}

    override["profile_intent"] = {
        "preset": preset_name,
    }

    override.setdefault("ranking", {})
    override["ranking"]["min_semantic_score"] = round(STRICTNESS_MAP[strictness], 2)
    override["ranking"]["allowed_functional_roles"] = allowed_roles

    # penalties: allowed → 1.0, others → 0.0
    penalties = {}
    for role in ROLE_LABELS:
        penalties[role] = 1.0 if role in allowed_roles else 0.0
    override["ranking"]["functional_role_penalties"] = penalties

    if preferred:
        override.setdefault("company_scoring", {})["preferred_companies"] = [
            x.strip() for x in preferred.split(",") if x.strip()
        ]

    if excluded:
        override.setdefault("profiles", {}).setdefault("senior_ic", {})[
            "exclude_keywords"
        ] = [x.strip() for x in excluded.split(",") if x.strip()]

    override.setdefault("search", {})["anchors"] = anchors

    (base / "settings.override.yaml").write_text(
        yaml.safe_dump(override, sort_keys=False)
    )

    st.success(f"Created {new_user} / {new_use_case}")
    st.session_state.user = new_user
    st.session_state.use_case = new_use_case
    st.session_state.logged_in = True
    save_session({"logged_in": True, "user": new_user, "use_case": new_use_case})
    st.rerun()
