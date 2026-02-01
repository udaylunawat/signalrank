# Changelog

All notable changes to this project are documented here.

This changelog is **intentional**, not exhaustive.
It records **architectural, behavioral, and operational** changes that affect
correctness, determinism, or how the system is reasoned about.

---

## Unreleased

### Added
- Explicit architectural contracts in `rules.md`
- Domain-pure scoring layer (`domain/`) with zero I/O
- Immutable run model with `run_id` as the primary unit of execution
- DuckDB-backed embedding cache keyed by `(text_fp, config_fp, user, use_case)`
- Resume distillation as a first-class artifact
- Optional LLM veto as a bounded, post-ranking guard
- Interactive CLI with safe defaults and prompts
- Streamlit UI backed exclusively by historical runs
- Per-user override system expressing intent, not control flow
- Deterministic company, location, recency, and seniority signals
- Semantic explorer in UI for resume-to-job similarity inspection
- Onboarding tool for generating user overrides from resumes

### Changed
- Ranking pipeline is strictly ordered and stage-driven
- Semantic similarity is gated early to prevent late-stage distortion
- Skill extraction is deterministic and config-driven only
- Functional role classification is heuristic-first and LLM-free
- Embedding text is structured and stable
- UI no longer depends on filesystem artifacts
- Scheduler behavior moved fully into Python
- Logging is structured and run-scoped
- Configuration is static per run and fingerprinted

### Removed
- CSV snapshots and preview artifacts
- Filesystem-based caches for ranking state
- Runtime config mutation
- UI-triggered computation
- Implicit “latest” semantics
- Multi-writer execution paths
- Hidden background processes
- Side-effect-heavy workspaces
- Ad-hoc scripts without a clear lifecycle

---

## Behavioral Changes

### Ranking Semantics
- Rankings are now tied to immutable runs
- Re-running does not overwrite prior results
- Duplicate jobs are deterministically deduplicated post-scoring
- Short or low-quality descriptions are penalized early
- Company and location signals are bounded multipliers, never gates
- Experience constraints are enforced conservatively

### LLM Behavior
- LLMs no longer participate in role classification
- LLM output cannot hard-fail a run
- LLM veto applies a penalty, not removal
- All LLM usage is optional and advisory

---

## Operational Changes

### Execution
- One batch execution equals one database transaction
- Partial failures are recorded, not hidden
- UI can safely run concurrently in read-only mode

### Storage
- DuckDB is the only persistence layer
- All state is queryable via SQL
- Historical analysis is a first-class capability

---

## Migration Notes

- Existing historical data is not automatically migrated
- Embeddings will be recomputed lazily as needed
- Configuration must be expressed via base config plus user override
- Any reliance on filesystem artifacts should be removed

---

## Compatibility Notes

- Python ≥ 3.10 required
- LLM provider optional but recommended
- Designed for single-user or small-team operation

---

## Change Evaluation Policy

Every change is evaluated against three questions:

1. Did top-ranked results improve?
2. Did determinism degrade?
3. Did complexity increase?

If question 2 or 3 is answered “yes”, the change is rejected.

---

## Philosophy of This Changelog

This file exists to answer:
- “Why was this changed?”
- “What assumption no longer holds?”
- “What should not be reintroduced?”

If a change does not affect those questions, it does not belong here.