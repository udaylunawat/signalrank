# 01 — SignalRank baseline: June 06 backend-hardening

**Status:** Static source audit only. **Baseline revision:** `97adf1b5930a02b70ed56ea1872ab75071b0dbee` on `feature/june-06-backend-hardening`. **Reviewed:** 2026-11-17.

## Provenance and safety

This document uses the **committed HEAD tree**, read via `git show HEAD:<path>`, not the working files. Other development work was already present in the worktree (modified API, dashboard and tracker paths; new inbox files). Do **not** reset, merge, checkout, stage or modify those in-progress files for benchmarking. The separate SignalRank `main` workspace is out of scope. Historical April test claims and later `main` implementations are **not** assertions about this baseline.

No actual services, external job searches, user accounts, browsers, or scoring benchmarks were run by this audit.

## Verified source architecture

- `signalrank/frontend/package.json`: Next.js 16.2.1, React 19.2.4, TypeScript, Tailwind; `dev`, `typecheck`, `lint:ci`, `build`, `check` scripts.
- `signalrank/backend/pyproject.toml`: Python >=3.11, FastAPI, SQLAlchemy asyncio, PostgreSQL/asyncpg, pgvector, Alembic, optional aiosqlite, ONNX Runtime, tokenizers, `python-jobspy>=1.1.0`, httpx, pdf/docx and resume tools. The dependency declaration is a lower bound; check the lockfile before making runtime version claims.
- `signalrank/backend/batch/sources/`: adapters for JobSpy, free APIs, Google Jobs, RapidAPI, direct ATS, Workday, LinkedIn pages, Amazon and company portals. Presence of an adapter does not prove current live availability.
- `batch/scraper.py` (408 lines): query planning/incremental cache, source orchestration, within-phase URL de-duplication.
- `batch/scrape_pipeline.py` (615 lines): source ingestion, database upserts keyed on `job_url`, pre-embedding candidate selection using title/skill/cluster/location/description signals, and company+title+location candidate reduction.
- `batch/worker.py` (1,036 lines): durable run claiming, leases, worker modes and run-state transitions; confirm concurrency properties by tests.
- `batch/ranker.py` (1,969 lines): embedding-based matching, semantic gates, deterministic additive score, optional agentic matching/verifier, intent shadow matching and final result selection.
- `domain/intent_matching.py`: explicit profile/job facts, confidence checks, role-family negatives, confidence caps, and score bands.
- `domain/score_synthesis.py`: maps optional model verdict and verification adjustments onto a deterministic baseline using a bounded multiplier.
- `batch/job_availability.py`: detects HTTP 404/410, page-expiration signals, and archives confirmed expired jobs.
- `api/models.py`: users, profiles, raw jobs, runs, results, applications, preference memory, feedback, recruiters, embeddings and caches.
- `LICENSE`: MIT license in **this June branch** (do not infer the license from a different branch).
- **72 tracked backend test files** were identified by filename. This is *not* 72 passing tests. No tests were executed here.

## Significant source-verified issues/hypotheses

1. **False merging of distinct openings.** `batch/ranker.py` finalization (lines ~1927–1953) drops duplicate company+title records, then a fuzzy normalized-title+company key. Two separate requisitions with the same title can disappear from the matches list. This is a structural risk, not a confirmed real-world failure.
2. **Cross-board repeated openings.** `scrape_pipeline.py` upserts by URL and the scraper has URL-level de-duplication. Distinct ATS and aggregator URLs can remain separate catalog records unless downstream identity evidence connects them.
3. **Pre-embedding reduction can collapse roles.** `select_fresh_jobs_for_embedding` keys candidates by company/title/location, without requiring the same ATS requisition. This risks pruning valid distinct openings before scoring.
4. **Complexity.** Ranker and workers contain substantial policy and orchestration code. Separate deterministic facts/score synthesis, source orchestration and persistence before introducing new feature types.
5. **Already-existing protections.** Avoid reimplementing matching gates, retrying, availability checks, caching or failure fallback merely because competitors advertise them. Test this branch's implementations first.
6. **Documentation drift.** `signalrank/README.md` describes an in-memory queue; code contains lease-claimed durable worker logic. Treat implementation as authoritative, validate the architecture diagram and revise documentation as a separate task.
7. **Privacy/deployment review.** `docker-compose.local.yml` describes a local worker syncing top-ranked results to Railway. Confirm exact configured network/data flow before describing this deployment as fully local; never access real credentials or resumes during benchmark.

## Baseline performance and UX

| Metric | State |
|---|---|
| Job relevance P@10 / nDCG@10 | NOT RUN |
| Duplicate precision / recall | NOT RUN |
| Active/dead link rate | NOT RUN |
| Source freshness / incremental fetch yield | NOT RUN |
| Browser task times / real screenshots | NOT RUN |
| Backend unit, API and end-to-end tests | NOT RUN in this audit |
| Previous April 69-unit-test result | Historical claim; not transferable to June HEAD |
| Current working tree | **Dirty due to concurrent work**; do not reset |

## Recommended first baseline verification (separate environment thread)

Use isolated dependencies/database and a clean worktree at the pinned commit **without** disturbing the active June workspace. Run backend marked unit tests, API/database tests, lint/typecheck/build, disposable-seed browser flows, and a source-failure dry run. Record executable versions, commit hashes, actual failing tests, screenshots and run logs separately from this static report.
