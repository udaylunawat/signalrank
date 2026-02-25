# SignalRank

**SignalRank** is a deterministic, batch-first hybrid relevance engine
for ranking semi-structured market listings against a user intent.

It was originally built for job discovery.\
It is architected as a configurable scoring engine.

This system optimizes for:

-   Ranking correctness
-   Determinism
-   Explainability
-   Operational calm
-   Long-term evolvability

Not for feature velocity.

------------------------------------------------------------------------

# What This System Actually Is

SignalRank is **not** a job board.\
It is **not** a scraper.\
It is **not** an LLM wrapper.

It is a **hybrid retrieval and scoring engine** over noisy listings.

It answers one question well:

> Given a structured intent and a noisy corpus, what deserves attention
> today?

The engine combines:

-   Semantic similarity (embeddings)
-   Deterministic gates
-   Taxonomy-based classification
-   Persona-conditioned multipliers
-   Hard caps
-   Optional bounded LLM advisory signals
-   Immutable run tracking

Everything is versioned.\
Everything is reproducible.

------------------------------------------------------------------------

# Core Properties

## Batch-first by design

-   All scraping, embedding, and ranking occurs in batch
-   No ranking logic executes inside the UI
-   Every execution produces an immutable run

The UI is read-only. Always.

------------------------------------------------------------------------

## Deterministic scoring spine

Same inputs → same outputs.

Heuristics run before probabilistic signals.

LLMs are advisory, never authoritative.

------------------------------------------------------------------------

## Immutable runs

Each execution creates a new `run_id`.

-   Historical results are never overwritten
-   Config fingerprinting ensures reproducibility
-   Embeddings are cached and version-scoped

Ranking is auditable.

------------------------------------------------------------------------

## Single state backbone

DuckDB is the only persistence layer.

-   No CSV snapshots
-   No shadow caches
-   No background state mutation

One writer. Many readers.

------------------------------------------------------------------------

# High-Level Architecture

    CLI / Scheduler
            ↓
    Batch Pipeline
            ↓
    DuckDB
    (runs, jobs_raw, embeddings, results)
            ↓
    Streamlit UI (read-only)

Only the batch layer writes.

The UI cannot mutate system state.

------------------------------------------------------------------------

# Ranking Model Overview

SignalRank uses a staged ranking pipeline:

1.  Pre-filters\
2.  Skill extraction and canonicalization\
3.  Embedding generation or cache reuse\
4.  Semantic similarity scoring\
5.  Role-aware semantic gates\
6.  Deterministic multipliers
    -   Role/skill match
    -   Company weighting
    -   Location weighting
    -   Recency decay
    -   Seniority alignment
7.  Hard caps for misaligned roles\
8.  Optional LLM veto (bounded)\
9.  Safe deduplication\
10. Immutable persistence

Design principle:

> No downstream multiplier may resurrect a bad semantic match.

------------------------------------------------------------------------

# Why This Exists

Modern listing ecosystems are noisy.

Titles are inconsistent.\
Descriptions are padded.\
Intent is implicit.\
Signal is buried under boilerplate.

SignalRank exists to:

-   Extract semantic signal
-   Apply deterministic structure
-   Bound bias
-   Preserve explainability
-   Maintain operational stability

It is closer to a relevance engine than a scraper.

------------------------------------------------------------------------

# Repository Structure

    job_ranker/
    ├── app/            # Streamlit UI (read-only)
    ├── batch/          # Batch orchestration pipeline
    ├── config/         # Base config + user overrides
    ├── domain/         # Pure scoring and classification logic
    ├── llm/            # Bounded advisory LLM utilities
    ├── runtime/        # Scheduling logic
    ├── storage/        # DuckDB schema + persistence
    ├── tools/          # Operational utilities
    └── tests/          # Ranking correctness tests

## Intent by directory

**domain/**\
Pure logic. No I/O. No environment access. No database calls.

**batch/**\
Coordinates scraping, embeddings, scoring, and persistence.

**storage/**\
Owns schema and state mutation rules.

**app/**\
Inspection and visualization only.

------------------------------------------------------------------------

# Configuration Model

## Base configuration

`config/base.yaml`

Engine-neutral defaults: - Embedding model - Semantic thresholds - Role
taxonomy - Ranking caps - Scraping defaults

Safe to version control.

------------------------------------------------------------------------

## User overrides

`config/overrides/<user>.yaml`

Overrides express intent, not mechanics.

They can adjust:

-   Resume embedding prefix
-   Functional role bias
-   Company preferences
-   Location weighting
-   Experience bounds
-   Title blocklists

Overrides are deep-merged and fingerprinted per run.

------------------------------------------------------------------------

# LLM Usage (Strictly Bounded)

LLMs are optional.

They are used only for:

-   Resume distillation
-   Advisory relevance veto
-   Onboarding assistance

Hard guarantees:

-   LLM failure never breaks a run
-   LLM output never directly defines ranking
-   LLM effects are bounded multipliers or filters
-   Determinism is preserved when LLM veto is disabled

------------------------------------------------------------------------

# Running the System

## Install (macOS recommended)

``` bash
uv pip install -e .
```

Verify:

``` bash
job-ranker doctor
```

------------------------------------------------------------------------

## Execute a batch run

``` bash
job-ranker run   --user example   --use-case default   --search "mlops|llmops|genai"   --hours-old 24
```

Each run:

-   Optionally scrapes
-   Ingests and canonicalizes
-   Generates or reuses embeddings
-   Scores deterministically
-   Persists immutable results

------------------------------------------------------------------------

## Launch the UI

``` bash
job-ranker ui
```

The UI:

-   Reads from DuckDB
-   Displays historical runs
-   Supports semantic exploration
-   Never executes ranking logic

------------------------------------------------------------------------

# What This System Avoids

-   Real-time ranking
-   UI-triggered computation
-   Hidden background jobs
-   Implicit mutation
-   CSV-based workflows
-   Unbounded configuration complexity
-   Silent LLM authority

Correctness is preferred over flexibility.

------------------------------------------------------------------------

# Design Principles

-   Prefer explicit data over inferred state
-   Prefer staged pipelines over magical heuristics
-   Prefer gates before multipliers
-   Prefer explainability over cleverness
-   Prefer deletion over abstraction
-   Prefer determinism over novelty

------------------------------------------------------------------------

# What This Can Become

Although originally built for job discovery, the architecture
generalizes to:

-   Talent matching
-   Vendor scoring
-   RFP filtering
-   Startup scouting
-   Grant discovery
-   Internal project matching
-   Any semi-structured listing relevance problem

It is a hybrid relevance engine with persona conditioning.

------------------------------------------------------------------------

# Future Evolution

To move from heuristic tuning to measurable system design:

-   Introduce labeled evaluation sets
-   Add offline relevance benchmarks
-   Track score distribution drift
-   Log score component breakdowns
-   Formalize weight calibration

When that layer is added, this becomes a full search relevance
framework.

------------------------------------------------------------------------

# License

Intended for personal and internal use.
