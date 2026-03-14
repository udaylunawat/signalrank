# ================================
# FILE: app.py
# ================================
import streamlit as st
from utils.session import load_session, save_session
from utils.ui import discover_use_cases, discover_users

# --------------------------------------------------
# SESSION RESTORE (ONCE PER BROWSER SESSION)
# --------------------------------------------------
if "initialized" not in st.session_state:
    persisted = load_session()
    st.session_state.logged_in = persisted.get("logged_in", False)
    st.session_state.user = persisted.get("user")
    st.session_state.use_case = persisted.get("use_case")
    st.session_state.initialized = True

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Calm-First Job Ranker · Home",
    layout="wide",
)

# --------------------------------------------------
# BRANDING / IDENTITY
# --------------------------------------------------
st.title("🌊 Calm-First Job Ranker")
st.caption(
    "A batch-first, deterministic system for discovering **senior IC AI / GenAI / MLOps roles** — without noise."
)

st.markdown("""
**Design principles**
- 🧠 Deterministic over probabilistic  
- 🧱 Batch-first (UI is read-only)  
- 🧘 Calm, senior-IC focused (no manager churn)  
- 🔍 Explainable scoring, not black-box recommendations  
""")

st.divider()

# --------------------------------------------------
# SESSION STATE (DEFENSIVE)
# --------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "use_case" not in st.session_state:
    st.session_state.use_case = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --------------------------------------------------
# LOGIN VIEW
# --------------------------------------------------
if not st.session_state.logged_in:
    st.subheader("🔐 Login")

    users = discover_users()
    if not users:
        st.error("No users found. Please onboard a user first.")
        st.stop()

    user = st.selectbox("User", users)

    use_cases = discover_use_cases(user)
    use_case = st.selectbox("Use case", use_cases)

    if st.button("Enter", type="primary"):
        st.session_state.user = user
        st.session_state.use_case = use_case
        st.session_state.logged_in = True

        # 🔑 Persist session
        save_session(
            {
                "logged_in": True,
                "user": user,
                "use_case": use_case,
            }
        )

        st.rerun()

    st.stop()

# --------------------------------------------------
# POST-LOGIN HOME
# --------------------------------------------------
st.success(f"Logged in as **{st.session_state.user} / {st.session_state.use_case}**")

# --------------------------------------------------
# CONTEXT SUMMARY
# --------------------------------------------------
with st.expander("📌 Current session context", expanded=True):
    st.markdown(f"""
**User:** `{st.session_state.user}`  
**Use case:** `{st.session_state.use_case}`  

This context controls:
- search anchors  
- ranking profile  
- company preferences  
- cache / corpus scope  

All batch runs and outputs are **isolated to this scope**.
""")

# --------------------------------------------------
# NAVIGATION GUIDE
# --------------------------------------------------
st.markdown("""
### 🧭 How to use this system

Use the **sidebar** to navigate:

- **📊 Dashboard**  
  View the latest **batch-ranked jobs**, new-since-last-run, and corpus similarity.

- **⚡ Quick Scan**  
  Run a **short-window, scratch scan** (24–48h) without disturbing daily state.

- **📜 Logs**  
  Inspect batch execution logs and debug scraping or ranking issues.

- **👤 Onboard**  
  Create users, define use cases, upload resumes, and set search anchors.

This home page never triggers scraping or ranking.  
It is **purely a control and navigation surface**.
""")

st.divider()

# --------------------------------------------------
# LOGOUT (GLOBAL)
# --------------------------------------------------
if st.button("Logout"):
    st.session_state.clear()
    save_session({})
    st.rerun()
