# =====================================================
# Job Ranker – Project Commands (just)
# =====================================================
#
# This Justfile provides *workflow shortcuts only*.
# All arguments, defaults, and interactivity live in
# the `job-ranker` CLI itself.
#
# Usage examples:
#
#   just help
#   just install
#   just lint
#   just check
#
#   # Interactive run (CLI will prompt)
#   just run
#
#   # Fully scripted usage (use CLI directly)
#   # job-ranker run --user example --search "mlops|llmops"
#
#   just ui
#   just doctor
#
# =====================================================

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# -----------------------------
# Help
# -----------------------------

help:
    @echo ""
    @echo "Job Ranker – available commands:"
    @echo ""
    @echo "  just install    Install project and dependencies"
    @echo "  just lint       Auto-fix lint issues (ruff + isort + black)"
    @echo "  just check      Lint check only (no fixes)"
    @echo ""
    @echo "  just run        Run batch job (interactive CLI)"
    @echo "  just ui         Launch Streamlit UI"
    @echo "  just doctor     Environment sanity check"
    @echo ""
    @echo "For fully scripted runs, use:"
    @echo "  job-ranker run --user <user> --search <query> [options]"
    @echo ""

# -----------------------------
# Environment / Install
# -----------------------------

install:
    uv pip install -e .
    uv pip install -r job_ranker/requirements.txt

# -----------------------------
# Code Quality
# -----------------------------

lint:
    uv run ruff check . --fix
    uv run isort .
    uv run black .

check:
    uv run ruff check .
    uv run isort . --check-only
    uv run black . --check

# -----------------------------
# Runtime
# -----------------------------

run:
    uv run job-ranker run

ui:
    uv run job-ranker ui

doctor:
    uv run job-ranker doctor

# -----------------------------
# Cleanup
# -----------------------------

clean:
    rm -rf cache .ruff_cache __pycache__ */__pycache__

digest:
    python job_ranker/helpers/generate_digest.py