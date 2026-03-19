# AGENTS.md — Job Ranker (SignalRank)

## Project Overview

**SignalRank** is a deterministic, batch-first hybrid relevance engine for ranking job listings against user intent. It scrapes jobs from multiple sources, deduplicates, enriches descriptions, ranks via semantic embeddings + heuristics, and persists results to DuckDB.

**Core philosophy:** Correctness > Flexibility. Determinism > Novelty. Explainability > Cleverness.

## Tech Stack

- **Language:** Python 3.11+
- **Package manager:** `uv` (not pip directly)
- **Database:** DuckDB (single writer, many readers)
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU)
- **UI:** Streamlit (read-only)
- **Scraping:** JobSpy fork (speedyapply), SerpAPI, RapidAPI
- **LLM (optional):** litellm + OpenRouter (advisory only, never authoritative)
- **Task runner:** `just` (Justfile)

## Repository Structure

```
/
├── job_ranker/              # Main package
│   ├── app/                 # Streamlit UI (read-only)
│   ├── batch/               # Batch pipeline: scraper, enrich, ranker, veto
│   │   ├── run.py           # Main execute() entry point
│   │   ├── scraper.py       # Multi-source scraping orchestration
│   │   ├── ranker.py        # Scoring pipeline
│   │   ├── enrich.py        # LinkedIn description enrichment
│   │   └── veto.py          # Optional LLM advisory veto
│   ├── config/              # base.yaml + overrides/<user>.yaml
│   ├── domain/              # Pure scoring logic (no I/O, no DB)
│   ├── storage/             # DuckDB schema + persistence
│   ├── llm/                 # Bounded LLM utilities
│   ├── scrapers/            # Individual scraper implementations
│   ├── tools/               # Operational utilities
│   └── tests/               # Ranking correctness tests
├── mini_ranker.py           # Standalone single-file ranker (alternative)
├── config.example.yaml      # Example config for mini_ranker
├── Justfile                 # Task runner commands
├── pyproject.toml           # Package config + dependencies
└── docs/                    # Design docs, plans, specs
```

## Key Commands

```bash
# Install
uv venv .venv --python python3.11 && source .venv/bin/activate
uv pip install -e .[dev]
pip install git+https://github.com/speedyapply/JobSpy.git  # required fork

# Lint & format
just lint        # ruff + isort + black (auto-fix)
just check       # lint check only (CI mode)

# Run batch pipeline
just run-example                                           # quick run with defaults
just run-refresh                                        # force refresh, full search
job-ranker run --user example --search "mlops" --hours-old 72 --force-refresh --skip-enrich

# UI
just ui          # streamlit dashboard

# Utilities
just doctor      # environment sanity check
just digest      # generate repo digest
```

## Architecture Invariants (DO NOT VIOLATE)

1. **Batch is the only writer** — UI is read-only, no subprocess from Streamlit
2. **Runs are immutable** — every execution gets unique `run_id`, no overwrites
3. **DuckDB is single source of truth** — no CSVs, no shadow caches
4. **Domain code is pure** — no I/O, no DB access, no env access in `domain/`
5. **LLMs are advisory only** — may propose, never decide; must fail open

## Ranking Pipeline (order matters)

```
SCRAPE → CANONICALIZE → EMBED → SEMANTIC SIMILARITY → SEMANTIC GATE
→ ROLE-AWARE ADJUSTMENT → QUALITY PENALTIES → FINAL SCORE → OPTIONAL LLM VETO
```

## Configuration

- **Base:** `job_ranker/config/base.yaml` — engine defaults (safe to version control)
- **User overrides:** `job_ranker/config/overrides/<user>.yaml` — persona preferences
- **Env vars:** `.env` (gitignored) — API keys (OPENROUTER_API_KEY, RAPIDAPI_KEY, SERPAPI_KEY)

## Code Style

- Line length: 88 (black/ruff)
- Python 3.11 target
- No comments unless asked
- Domain code: pure functions, no side effects
- Imports: isort with `profile = "black"`

## Important Gotchas

- JobSpy Indeed must run sequentially (3s delay) — parallel causes 403s
- `country_indeed` must be `"India"` not `"IN"` (enum name resolution)
- speedyapply fork required for `hours_old` support
- Free APIs (Remotive, Himalayas, Jobicy) always run regardless of RapidAPI status
- SerpAPI > direct Google scraping (Google blocks all IPs)
