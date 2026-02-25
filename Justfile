# =====================================================
# Job Ranker – Project Commands (just)
# =====================================================

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

VENV := ".venv"
USER := "example"

# -----------------------------------------------------
# Help
# -----------------------------------------------------

help:
    @echo ""
    @echo "Job Ranker – available commands:"
    @echo ""
    @echo "  just install          Create venv + install dependencies"
    @echo "  just activate         Print command to activate venv"
    @echo ""
    @echo "  just lint             Auto-fix lint issues"
    @echo "  just check            Lint check only"
    @echo ""
    @echo "  just run              Interactive batch run"
    @echo "  just run-example         Batch run (user=example)"
    @echo "  just run-refresh      Force refresh scrape (user=example)"
    @echo "  just run-csv <file>   Ingest and rank pre-scraped CSV"
    @echo ""
    @echo "  just ui               Launch Streamlit UI"
    @echo "  just onboard          Onboard new user"
    @echo "  just doctor           Environment sanity check"
    @echo ""
    @echo "  just digest           Generate repository digest"
    @echo ""
    @echo "  just clean            Remove cache artifacts"
    @echo ""

# -----------------------------------------------------
# Environment / Install
# -----------------------------------------------------

install:
    uv venv {{VENV}} --python python3.11
    uv pip install -e .[dev]

activate:
    @echo ""
    @echo "Run this to activate the environment:"
    @echo ""
    @echo "  source {{VENV}}/bin/activate"
    @echo ""

# -----------------------------------------------------
# Code Quality
# -----------------------------------------------------

lint:
    uv run ruff check . --fix
    uv run isort .
    uv run black .

check:
    uv run ruff check .
    uv run isort . --check-only
    uv run black . --check

# -----------------------------------------------------
# Runtime
# -----------------------------------------------------

# Fully interactive
run:
    uv run job-ranker run

# Fast path for your default user
run-example:
    uv run job-ranker run --user {{USER}}

# Force scrape refresh for your persona
run-refresh:
    uv run job-ranker run \
        --user {{USER}} \
        --search "ai platform engineer|ml platform engineer|mlops|llmops|genai|agentic systems|ai infrastructure|forward deployed engineer|developer productivity engineer" \
        --hours-old 72 \
        --force-refresh

# CSV ingestion mode
run-csv file:
    uv run job-ranker run \
        --user {{USER}} \
        --csv {{file}}

ui:
    uv run job-ranker ui

doctor:
    uv run job-ranker doctor

onboard:
    uv run job-ranker onboard

# -----------------------------------------------------
# Utilities
# -----------------------------------------------------

digest:
    uv run python job_ranker/helpers/generate_digest.py

# -----------------------------------------------------
# Cleanup
# -----------------------------------------------------

clean:
    rm -rf cache .ruff_cache __pycache__ */__pycache__