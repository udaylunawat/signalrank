# ================================
# FILE: pages/3_QuickScan.py
# ================================
import streamlit as st
import subprocess
import sys
import os
import yaml
from pathlib import Path

from user_context import resolve_user_context
from config_loader import load_effective_settings

st.set_page_config(layout="wide")
st.title("⚡ Scratch Full Scan (24–48h)")
st.caption("Full pipeline, limited time window, ephemeral output")

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

st.caption(f"Scratch scan for **{ctx.user} / {ctx.use_case}**")

# --------------------------------------------------
# RESUME
# --------------------------------------------------
resume_dir = ctx.base_dir / "resume"
resume_dir.mkdir(exist_ok=True)

uploaded = st.file_uploader("Upload resume (PDF or TEX)", type=["pdf", "tex"])
if uploaded:
    resume_path = resume_dir / uploaded.name
    resume_path.write_bytes(uploaded.read())
    st.success(f"Saved resume → {resume_path}")
else:
    choices = list(resume_dir.glob("*.pdf")) + list(resume_dir.glob("*.tex"))
    selected = st.selectbox(
        "Or select existing resume",
        [""] + [p.name for p in choices],
    )
    resume_path = resume_dir / selected if selected else None

if not resume_path or not resume_path.exists():
    st.info("Upload or select a resume to continue.")
    st.stop()

# --------------------------------------------------
# LOAD DEFAULT SEARCH FROM CONFIG
# --------------------------------------------------
effective_cfg = load_effective_settings(ctx)

anchors = []
search_cfg = effective_cfg.get("search", {})
raw_anchors = search_cfg.get("anchors", [])

if isinstance(raw_anchors, list):
    anchors = [a for a in raw_anchors if isinstance(a, str)]

default_query = " | ".join(anchors)

# --------------------------------------------------
# SCAN PARAMS
# --------------------------------------------------
query = st.text_input(
    "Search query",
    value=default_query,
    help="Preloaded from search.anchors in settings.override.yaml",
)

hours = st.number_input(
    "Hours back",
    min_value=1,
    max_value=720,
    value=24,
)

log_file = ctx.base_dir / "scratch.log"
log_file.write_text("")

# --------------------------------------------------
# RUN SCRATCH FULL SCAN
# --------------------------------------------------
if st.button("Run Scratch Full Scan"):
    if not query.strip():
        st.error("Search query cannot be empty.")
        st.stop()

    cmd = [
        sys.executable,
        "cli.py",
        "run",
        "--resume", str(resume_path),
        "--user", ctx.user,
        "--use-case", ctx.use_case,
        "--search", query,
        "--scratch-hours", str(hours),
        "--force-refresh",
    ]

    st.info(f"Executing:\n`{' '.join(cmd)}`")

    env = os.environ.copy()
    env["JOBRANKER_CACHE_DIR"] = str(ctx.cache_dir)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    with st.spinner("Running scratch full scan..."):
        for line in proc.stdout:
            print(line, end="")
            log_file.write_text(log_file.read_text() + line)
            st.write(line.rstrip())

    st.success("Scratch full scan complete.")

# --------------------------------------------------
# LOGS
# --------------------------------------------------
if log_file.exists():
    st.subheader("Logs")
    st.code(log_file.read_text(), language="text")