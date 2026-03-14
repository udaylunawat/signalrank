# app/session.py
import streamlit as st

from job_ranker.app.db import get_ui_db


def get_session():
    """
    Centralized UI session selector.
    - NO resolve_context
    - NO Store
    - read-only DB only
    """

    if "user" not in st.session_state:
        st.session_state.user = None
    if "use_case" not in st.session_state:
        st.session_state.use_case = None

    con = get_ui_db()

    users = (
        con.execute("SELECT DISTINCT user FROM runs ORDER BY user")
        .df()["user"]
        .tolist()
    )

    if not users:
        st.warning("No users found.")
        st.stop()

    user = st.selectbox(
        "User",
        users,
        index=(
            users.index(st.session_state.user) if st.session_state.user in users else 0
        ),
        key="__user_select",
    )

    use_cases = (
        con.execute(
            "SELECT DISTINCT use_case FROM runs WHERE user = ? ORDER BY use_case",
            [user],
        )
        .df()["use_case"]
        .tolist()
    )

    if not use_cases:
        st.warning("No use cases found.")
        st.stop()

    use_case = st.selectbox(
        "Use case",
        use_cases,
        index=(
            use_cases.index(st.session_state.use_case)
            if st.session_state.use_case in use_cases
            else (use_cases.index("default") if "default" in use_cases else 0)
        ),
        key="__use_case_select",
    )

    st.session_state.user = user
    st.session_state.use_case = use_case

    return user, use_case
