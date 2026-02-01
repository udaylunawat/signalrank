```
This document records the architectural reset that introduced the
batch-first, immutable-run job ranking system now on `main`.

It replaces the legacy system preserved on the `v1` branch.
```
Job Ranker – Batch-first, Immutable-run Architecture

## Summary

This reset introduces a **clean, batch-first job ranking engine** with immutable runs, a single DuckDB state spine, and a strictly read-only UI.

The intent is not feature parity or incremental refactor.
This is a **deliberate reset** to eliminate architectural drag and stabilize ranking quality over time.

---

## Motivation

The previous system accumulated complexity in three places:

1. **State sprawl**
   - CSV snapshots, caches, lockfiles, and partial persistence paths
   - Hard to reason about what was authoritative

2. **Blurry execution boundaries**
   - UI and batch shared responsibilities
   - Runtime behavior depended on execution order and environment

3. **Scoring iteration friction**
   - Ranking logic intertwined with I/O and config plumbing
   - Hard to make small, confident scoring changes

This reset addresses those issues by **reducing surface area**, not by adding abstractions.

---

## What This PR Delivers

### 1. Immutable, auditable runs
- Every execution produces a unique `run_id`
- Results are never overwritten
- Historical comparisons are first-class

### 2. Single persistence spine
- DuckDB is the only stateful system
- No CSV artifacts
- No dual caches for the same data

### 3. Hard separation of concerns
- Batch pipeline is the only writer
- UI is strictly read-only
- Domain logic is pure and deterministic

### 4. Ranking-first architecture
- Scoring logic is isolated and testable
- Heuristics precede probabilistic signals
- LLMs are bounded and optional

---

## Architectural Deltas (High-level)

### Execution Model
- From: mixed batch + UI-triggered logic  
- To: **batch-only execution with immutable results**

### Persistence
- From: CSVs + caches + DB  
- To: **DuckDB only**

### Scoring
- From: monolithic pipeline  
- To: **explicit staged ranking with pure domain code**

### UI
- From: stateful participant  
- To: **read-only inspector of runs**

---

## Explicit Non-goals

This reset intentionally does **not** attempt to:

- Preserve file-by-file structure
- Maintain legacy configuration patterns
- Support real-time ranking
- Add multi-user SaaS abstractions
- Optimize for feature velocity

Any missing feature is missing by design, not oversight.

---

## Migration Notes

### What is reset
- Previous CSV outputs
- Cached embeddings outside DuckDB
- Lockfile-based execution state
- Any “latest snapshot” semantics

### What persists conceptually
- Job scraping logic (simplified)
- Core ranking heuristics
- Skill canonicalization approach
- Resume distillation strategy

### Practical implication
- First run will rebuild embeddings
- Historical comparisons start from this PR forward
- No data migration is attempted or expected

---

## How to Review This reset

Suggested order to minimize cognitive load:

1. **`rules.md`**
   - Establishes invariants and design contract

2. **`storage/schema.sql`**
   - Understand the data model and immutability guarantees

3. **`batch/run.py`**
   - Entry point for execution
   - Defines the lifecycle of a run

4. **`batch/ranker.py`**
   - Core ranking pipeline
   - Most important logic in the system

5. **`domain/`**
   - Scoring primitives
   - Pure logic, easiest to reason about correctness

6. **`app/`**
   - UI wiring
   - Confirms read-only behavior

---

## Review Guidance

When reviewing changes, please focus on:

- Are invariants upheld?
- Is any hidden state introduced?
- Does scoring correctness improve or degrade?
- Is any complexity added without clear ROI?

If something feels harder to explain than before, that is a signal to question it.

---

## Final Note

This reset intentionally trades short-term familiarity for long-term clarity.

Once merged, future work should primarily consist of **small, local scoring changes**, not architectural work.