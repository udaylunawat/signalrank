# ================================
# FILE: utils/session_guard.py
# ================================
import streamlit as st
from utils.session import load_session


def require_login(*, redirect_page: str = "pages/1_Onboard.py"):
    """
    Enforce login across Streamlit multipage app.

    Guarantees:
    - Restores persisted session on refresh
    - Blocks access if not logged in
    - Centralized logic (no copy-paste guards)
    """

    # ---------------------------------
    # One-time restore from disk
    # ---------------------------------
    if "session_restored" not in st.session_state:
        persisted = load_session()
        st.session_state.logged_in = persisted.get("logged_in", False)
        st.session_state.user = persisted.get("user")
        st.session_state.use_case = persisted.get("use_case")
        st.session_state.session_restored = True

    # ---------------------------------
    # Hard guard
    # ---------------------------------
    if not st.session_state.get("logged_in"):
        st.warning("Please log in to continue.")
        try:
            st.switch_page(redirect_page)
        except Exception:
            # Older Streamlit fallback
            st.stop()

    if not st.session_state.get("user") or not st.session_state.get("use_case"):
        st.error("Session corrupted. Please log in again.")
        try:
            st.switch_page(redirect_page)
        except Exception:
            st.stop()
