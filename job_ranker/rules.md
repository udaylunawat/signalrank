Below is the explicit design plan for v2.

This is not a description of what you’ve already built.
This is the operating contract for the system going forward.

If you follow this, v2 will not regress into v1 complexity.

⸻

1. What we are trying to build (clear goal)

One-sentence goal

A batch-first, deterministic job ranking engine where ranking quality improves over time, not architectural complexity.

Non-goals (explicit)
	•	Not a scraping platform
	•	Not a real-time system
	•	Not a multi-tenant SaaS
	•	Not a prompt playground

⸻

2. Core invariants (do not violate)

These are hard rules.
Any feature that violates one is rejected.

I1. Batch is the only writer
	•	Only batch/run.py can mutate state
	•	UI is read-only
	•	No subprocess calls from Streamlit

I2. Runs are immutable
	•	Each execution produces a new run_id
	•	No overwrites
	•	No “latest.csv” semantics

I3. DuckDB is the single state spine
	•	No CSV snapshots
	•	No cache directories for data
	•	No dual persistence paths

I4. Domain code is pure
	•	domain/ has no I/O
	•	No DB, no files, no env vars
	•	Deterministic given inputs

I5. LLMs are advisory only
	•	LLMs may propose, never decide
	•	LLM failure must never break a run
	•	Ranking must still work with LLMs disabled

⸻

3. What v2 explicitly is NOT

This explains why files were not moved.

v2 is NOT:
	•	A file-by-file port of v1
	•	A config-driven framework
	•	A cache-heavy system
	•	A UI-driven workflow

This was an intentional reset.

⸻

4. File-movement rules (explicit, not implicit)

Rule A: Do NOT move files just because they exist in v1

A file must earn its place in v2.

⸻

Rule B: Every v1 file must answer one question

“Does this file support scoring correctness, batch determinism, or operational safety?”

If the answer is no → it stays out.

⸻

5. Canonical mapping: v1 → v2 (what moves, what doesn’t)

5.1 Files that MUST move (already done or in progress)

v1 file	v2 home	Why
match_engine.py	batch/ranker.py + domain/*	Core scoring logic
company_scoring.py	domain/company.py	Deterministic signal
skills/*	domain/skills.py	Canonicalization
llm/distill_resume.py	llm/distill_resume.py	Embedding quality
llm/veto_relevance.py	batch/veto.py	Optional guard
storage/db.py	storage/store.py	Single spine
app.py, pages/*	app/	Read-only UI


⸻

5.2 Files that must NOT move (by design)

v1 file	Reason
config_loader.py	v2 config is static + frozen
config_lock.py	Replaced by immutable runs
run_daily.sh	Scheduler logic belongs in Python
process_and_ingest.py	CSV era artifact
_ingest_tmp/	Filesystem snapshot era
settings.lock.json	DB already stores fingerprints
cache/*	Hidden state, nondeterminism
workspace/*	Side-effect heavy


⸻

5.3 Files that may move later (conditionally)

v1 file	Condition
llm/plan_search.py	Only if recall is weak
utils/query_repair.py	Only if scraping recall drops
llm/explain_match.py	Only for UX
llm/classify_role.py	Only if heuristics fail


⸻

6. Scoring pipeline we are building (final form)

Stage order (important)

SCRAPE
  ↓
CANONICALIZE
  ↓
JOB EMBEDDING (structured)
  ↓
RESUME EMBEDDING (distilled)
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

What we just finished
	•	Structured job embeddings
	•	Resume distillation for embedding
	•	Embedding observability

These are Tier-0 correctness foundations.

⸻

7. Best-case end state (what “done” looks like)

Functional
	•	Top-10 results feel consistently “right”
	•	Wrong roles rarely leak
	•	Generic postings sink naturally
	•	Re-runs are stable

Operational
	•	One run = one DB transaction
	•	No temp files
	•	No unexplained behavior

Cognitive
	•	You can explain why a job ranked high
	•	Debugging happens via logs + SQL, not guesswork

⸻

8. Next TODO list (ranked by ROI)

🔴 Tier 0 – Do next (small, high impact)

1️⃣ Job description quality penalty

Add:
	•	min description length penalty
	•	recruiter-style boilerplate dampening

Why: fixes false positives cheaply.

⸻

2️⃣ Role-aware semantic weighting

Move role penalty into similarity stage.

Why: prevents late-stage distortion.

⸻

🟡 Tier 1 – After stabilization

3️⃣ Skill overlap bounded boost

Reintroduce as a secondary signal.

⸻

4️⃣ Fix dashboard “run has no results”

Pure wiring issue, medium ROI.

⸻

🟢 Tier 2 – Optional polish

5️⃣ Match explanations (top-N only)

6️⃣ Query repair (if recall drops)

7️⃣ LLM search expansion (opt-in)

⸻

9. How to evaluate changes (non-negotiable)

Every change must answer:
	1.	Did top-10 improve?
	2.	Did determinism degrade?
	3.	Did complexity increase?

If 2 or 3 is yes → revert.

⸻

10. Final guidance (important)

You are past architecture risk.

From now on:
	•	prefer 5-line scoring tweaks over new subsystems
	•	resist “v1 parity” instincts
	•	treat v2 as the final system

