# Architecture & Design Rationale

This document explains **why** the system is shaped the way it is.

It is intentionally opinionated.

---

## Primary Goal

Build a job ranking engine where **ranking quality improves over time**, without increasing architectural complexity.

Everything else is secondary.

---

## Non-goals

The system is **not**:
- A scraping platform
- A real-time system
- A SaaS backend
- A prompt experimentation playground
- A configuration framework

Rejecting these goals early is what keeps the system stable.

---

## Invariants (Do Not Violate)

### I1. Batch is the only writer
- Only batch code may mutate the database
- UI is strictly read-only
- No subprocess calls from Streamlit

### I2. Runs are immutable
- Every execution has a unique `run_id`
- No overwrites
- History is a feature, not a cost

### I3. DuckDB is the single source of truth
- No CSVs
- No dual persistence paths
- No shadow caches

### I4. Domain code is pure
- No I/O
- No database access
- No environment access
- Deterministic given inputs

### I5. LLMs are advisory only
- May propose, never decide
- Must fail open
- Ranking must function without them

Any feature that violates an invariant is rejected.

---

## Scoring Pipeline (Final Form)

Order matters.

```
SCRAPE
  ↓
CANONICALIZE
  ↓
JOB EMBEDDING
  ↓
RESUME EMBEDDING
  ↓
SEMANTIC SIMILARITY
  ↓
SEMANTIC GATE
  ↓
ROLE-AWARE ADJUSTMENT
  ↓
QUALITY PENALTIES
  ↓
FINAL SCORE
  ↓
OPTIONAL LLM VETO
```

Late-stage fixes are intentionally discouraged. If a signal matters, it should appear early.

---

## Why Immutable Runs

Immutable runs solve multiple problems at once:
- Reproducibility
- Debugging
- Regression analysis
- UI consistency
- Operational safety

They also remove the need for:
- Locking logic
- "Latest" semantics
- Defensive file handling

---

## Why DuckDB

DuckDB provides:
- Transactional safety
- Fast analytical queries
- Zero service management
- Deterministic behavior

It enables debugging with SQL instead of guesswork.

---

## Why Domain Purity Matters

Pure domain code allows:
- Unit testing without mocks
- Fast iteration on scoring logic
- Confidence that changes are localized

If domain code starts doing I/O, complexity explodes.

---

## Configuration Philosophy

Configuration expresses **intent**, not mechanics.

Good config:
- Changes ranking behavior
- Remains interpretable

Bad config:
- Introduces branching logic
- Encodes control flow
- Attempts to replace code

If configuration feels like programming, it has gone too far.

---

## Failure Model

Failure is expected and tolerated.

- Scraping can partially fail
- LLM calls can fail
- Embeddings can be missing

The system degrades gracefully and records what happened.

---

## How to Evaluate Changes

Every change must answer:

1. Did top results improve?
2. Did determinism degrade?
3. Did complexity increase?

If 2 or 3 is yes, the change is rejected.

---

## End State Vision

When the system is "done":

**Functional:**
- Top results feel consistently right
- Obvious mismatches are rare
- Re-runs are stable

**Operational:**
- One run equals one transaction
- No temporary artifacts
- No hidden state

**Cognitive:**
- You can explain why a job ranked highly
- Debugging happens via logs and SQL

---

## Final Guidance

The system is past architectural risk.

From here on:
- Favor small scoring improvements
- Resist feature creep
- Delete aggressively
- Protect invariants at all costs