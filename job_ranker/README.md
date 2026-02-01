# Job Ranker

A batch-first, deterministic job ranking engine for senior individual contributor roles.

This system is designed to optimize for **ranking correctness, operational calm, and long-term evolvability**, not feature velocity or configurability.

---

## What This System Is

**Job Ranker** is a **job discovery and ranking engine**, not a job board.

It answers one question well:

> "Given a resume and a search intent, which jobs are most worth my attention today?"

Everything in the system exists to support that outcome with:
- Repeatable results
- Explainable scoring
- Minimal hidden state
- Low operational surprise

---

## Core Properties

### Batch-first by design
- All scraping, embedding, and ranking happens in batch
- No ranking logic is executed from the UI
- Every execution is explicit and auditable

### Immutable runs
- Each execution produces a new `run_id`
- Past results are never overwritten
- History is preserved by default

### Single state spine
- DuckDB is the only persistence layer
- No CSV snapshots
- No parallel caches for the same data

### Deterministic ranking
- Same inputs produce the same outputs
- Heuristics run before probabilistic signals
- LLMs are advisory, never authoritative

---

## High-level Architecture

One writer. Many readers. Always.

```
CLI / Scheduler
    ↓
Batch Run
    ↓
DuckDB (runs, jobs, embeddings, results)
    ↓
Streamlit UI (read-only)
```

---

## Repository Layout

```
job_ranker/
├── app/            # Streamlit UI (read-only)
├── batch/          # Batch execution pipeline (only writer)
├── config/         # Static config + per-user overrides
├── domain/         # Pure scoring and ranking logic
├── llm/            # Advisory LLM utilities
├── runtime/        # Scheduler / orchestration
├── storage/        # DuckDB schema and store
├── tools/          # One-off operational tools
└── tests/          # Scoring correctness tests
```

### Intent by directory

**`domain/`**  
Pure functions only. No I/O. No database. No environment access.

**`batch/`**  
Orchestrates scraping, embeddings, scoring, and persistence.

**`storage/`**  
Owns schema and persistence rules. No scoring logic allowed.

**`app/`**  
Visualization and inspection only. Never mutates state.

---

## Installation

### Requirements
- Python ≥ 3.10
- DuckDB
- A supported LLM provider (optional)

### Install (editable)

On macOS, use:

```bash
uv pip install -e .
```

Verify environment:

```bash
job-ranker doctor
```

---

## Running the System

### Batch execution (primary interface)

```bash
job-ranker run \
  --user example \
  --use-case default \
  --search "mlops|llmops|genai" \
  --hours-old 24
```

If arguments are omitted, the CLI will prompt interactively.

What happens in a run:
1. Optional scraping (skipped if recent data exists)
2. Job canonicalization
3. Embedding generation or reuse
4. Semantic similarity scoring
5. Deterministic adjustments (company, role, recency, experience)
6. Optional LLM veto
7. Immutable persistence of results

### Launching the UI

```bash
job-ranker ui
```

The UI:
- Reads from DuckDB only
- Never triggers batch logic
- Allows inspection of historical runs

---

## Configuration Model

### Base configuration
- Stored in `config/base.yaml`
- Engine-neutral defaults only
- Safe to version-control

### User overrides
- Stored in `config/overrides/<user>.yaml`
- Express intent, not mechanics
- Limited surface area by design

Overrides can affect:
- Resume embedding intent
- Role weighting
- Company preferences
- Experience bounds
- Location preference

---

## LLM Usage (Strictly Bounded)

LLMs are used only for:
- Resume distillation
- Optional relevance veto
- Optional onboarding assistance

Hard rules:
- LLM failure never breaks a run
- LLM output never directly determines ranking
- All LLM effects are bounded multipliers or filters

---

## What This System Explicitly Avoids

- Real-time ranking
- UI-triggered computation
- Hidden background jobs
- Filesystem-based snapshots
- Unbounded configuration matrices
- "Latest.csv" semantics

If you are looking for flexibility over correctness, this is not that system.

---

## Design Principles

- Prefer simple scoring tweaks over new subsystems
- Prefer explicit data over inferred state
- Prefer explainability over cleverness
- Prefer deletion over abstraction

---

## Getting Oriented as a Contributor

Suggested reading order:

1. `DESIGN.md` (see companion document)
2. `batch/run.py`
3. `batch/ranker.py`
4. `domain/scoring.py`
5. `storage/schema.sql`
6. `app/pages/dashboard.py`

---

## License and Usage

This project is intended for personal and internal use. Open-sourcing focuses on clarity and correctness, not general-purpose extensibility.