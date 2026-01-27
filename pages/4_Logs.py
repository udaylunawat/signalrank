# ================================
# FILE: pages/4_Logs.py
# ================================
import streamlit as st
from user_context import resolve_user_context

st.set_page_config(layout="wide")
st.title("📜 Logs")

# --------------------------------------------------
# SESSION GUARD
# --------------------------------------------------
from utils.session_guard import require_login

require_login()

ctx = resolve_user_context(
    user=st.session_state.user,
    use_case_override=st.session_state.use_case,
    require_resume=False,
)

st.caption(f"Logs for **{ctx.user} / {ctx.use_case}**")

log_file = ctx.base_dir / "shortscan.log"

if not log_file.exists():
    st.info("No logs found for this user/use case.")
    st.stop()

st.code(log_file.read_text(), language="text")