# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project

**SignalRank** — deterministic batch-first job ranking engine. Full context is in `AGENTS.md`.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `just lint` | Auto-fix lint (ruff + isort + black) |
| `just check` | Lint check only (CI mode) |
| `just run-example` | Batch run with defaults |
| `just run-refresh` | Force refresh scrape |
| `just ui` | Streamlit dashboard |
| `just doctor` | Environment sanity check |

## Architecture Invariants

1. **Batch is only writer** — UI is read-only
2. **Runs are immutable** — unique `run_id`, no overwrites
3. **DuckDB is single source of truth** — no CSVs, no shadow caches
4. **Domain code is pure** — `domain/` has zero I/O/DB/env access
5. **LLMs are advisory** — propose only, must fail open

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `job_ranker/batch/` | Pipeline orchestration (scraper, ranker, enrich, veto) |
| `job_ranker/domain/` | Pure scoring functions — no side effects |
| `job_ranker/config/` | `base.yaml` + `overrides/<user>.yaml` |
| `job_ranker/storage/` | DuckDB schema and persistence |
| `job_ranker/app/` | Streamlit UI (read-only) |

## Code Style

- Line length 88, Python 3.11, black/ruff/isort
- No comments unless asked
- Domain functions: pure, deterministic, no side effects

## Before Every Change

1. Check if you're modifying `domain/` — if so, keep it pure
2. Check `docs/` for relevant design specs
3. Run `just lint` after editing

## Don't Touch

- Don't add I/O to `domain/`
- Don't write to DuckDB from the UI layer
- Don't make LLM output authoritative in ranking
- Don't use `country_indeed="IN"` — use `"India"`
- Don't run JobSpy Indeed in parallel — sequential with 3s delay
