# SignalRank June 6 — Development Plan

**Branch:** `feature/june-06-backend-hardening`
**Foundation:** June 6, 2026 commit `fa2d42767186d81b511b50c81494212b60ceea27`
**Last verified implementation before this documentation commit:** `6a1e17122ab6f843483ade51da2f43567cecfab4`
**Plan updated:** 2026-11-17
**Status:** Active development; **not production-validated**.

## Product direction

Build SignalRank into a reliable **five-minute daily job-search workspace**, retaining the June version's terminal-inspired visual appearance and deeper application tracker. The user should quickly find relevant jobs, decide what to do next, and manage follow-through without re-reviewing rejected postings.

**Preserve:** recruiter contacts, priority, notes, interviews, offers and compensation, resume editor, role/company/location tuning, application history and user data. Avoid replacing the June app with the simplified July tracker. The core save action must not silently trigger paid AI, resume generation or enrichment.

## What is already implemented

| Area | Current state | Evidence |
|---|---|---|
| Search matches title, company **and location** | Implemented | June backport tests |
| Tracking a job saves without implicit enrichment | Implemented | June backport tests |
| Clearable notes, priority, interview/offer fields | Implemented | June backport tests |
| User-scoped review inbox | Implemented | `/inbox`, `/api/inbox`, SQLite API tests |
| Dismissal and snooze remain after reload | Implemented | SQLite API tests; no browser E2E yet |
| Snoozed roles resurface on selected date | Implemented | SQLite API tests |
| Tracker next action + due date | Implemented | Tracker UI and SQLite API tests |
| Dashboard follow-up and interview counters | Implemented | Frontend build, source and API tests |
| Atomic tailored-resume update | Implemented | SQLite upsert test |
| PostgreSQL migration for new review and tracker fields | Generated, **not run against PostgreSQL** | Alembic offline SQL passes |

The selected backend suite has **126 passing tests**; frontend production build and lint passed. These checks are not a substitute for full PostgreSQL integration, live ingestion, or browser task tests. See [backend hardening/validation notes](JUNE_06_BACKPORTS.md).

## Delivery priorities

### P0 — Prove the running app and safe database upgrade

- [ ] Provision **disposable PostgreSQL with pgvector**; take no actions against personal/production data. Apply all Alembic migrations through `7d0e20261117`.
- [ ] Test upgrade from a disposable copy of the June schema with saved tracker rows, recruiter data and generated resumes; verify rollback/recovery plan and backups.
- [ ] Run database-backed API tests, migrations, worker claim/recovery tests and app startup smoke checks.
- [ ] Start the **actual** Next.js/FastAPI app with disposable login and job fixtures. Capture real browser screenshots for `/dashboard`, `/inbox`, `/jobs`, `/tracker`, settings and mobile layouts. No mock screenshots.
- [ ] Verify save, dismiss, restore, snooze/resurface, page refresh, per-user isolation, follow-up scheduling and explicit resume generation through a real browser.

**Exit criteria:** all above workflows pass on PostgreSQL and in a browser, with reproducible logs and screenshots attached to a dated validation report. Do not deploy migrations before this.

### P1 — Complete the daily inbox

- [x] Model **first seen since last visit** distinctly from **unreviewed** using a per-user visit cursor and preserved first-match timestamps. **Pending:** PostgreSQL migration and real-browser verification.
- [ ] Distinguish reviewed-but-undecided from deliberately dismissed; preserve decisions across reranks and new sources.
- [ ] Add an end-of-session “reviewed today's batch” state and a clear next task.
- [ ] Support quick dismiss reasons, undo, snooze presets, due-date resurfacing and keyboard shortcuts where accessible.
- [ ] Show follow-ups due / today's review / upcoming interviews ahead of scan diagnostics, with reliable counts even if the user has no active scan.

**Exit criteria:** 10 jobs can be triaged without reappearing after reload; user can finish a daily batch, resume tomorrow, and recover a dismissed role. Measure actual completion time; five minutes is a goal, **not an observed result**.

### P1 — Make the tracker an actionable follow-up tool

- [x] Next action and due date stored per application.
- [x] Due actions surfaced on the tracker and dashboard.
- [ ] Add a dedicated **Needs Attention** list with completed/snoozed follow-up actions and optional reminder delivery.
- [ ] Add date/time and time zone handling for interviews, plus calendar export/links if explicitly requested.
- [ ] Preserve the June tracker fields and recruiter contacts; validate updates and clearing in the running browser.
- [ ] Rework narrow-screen tracker into readable grouped lists, avoiding a horizontal Kanban-only workflow.

**Exit criteria:** a follow-up can be scheduled, found when due, completed/rescheduled and viewed on mobile without horizontal scrolling.

### P2 — Improve Matches usability without changing the product's character

- [ ] Offer dense table and readable card/list mode; keep sorting, pagination and important signals.
- [ ] Move diagnostics behind a secondary details section; keep run failure visibility.
- [ ] Introduce explicit **remote / hybrid / onsite / unknown** and **FTE / contract / unknown** filters grounded in the job data.
- [ ] Unify score thresholds and labels across cards, dashboard, filters and inbox; distinguish `0–1` internal fractions from `0–100` display points.
- [ ] Persist search/filter/sort choices in shareable URLs; add saved searches only after core navigation works.
- [ ] Verify accessible focus, keyboard behavior, responsive layout, contrast, errors and empty states.

### P2 — Improve discovery, identity and ranking using measured evidence

- [ ] Execute the [benchmark protocol](../../docs/benchmark/04-benchmark-results.md) with immutable app/competitor revisions.
- [ ] Use the [synthetic identity/relevance fixtures](../../docs/benchmark/fixtures/generate_jobset.py) for regression **contracts**, not real-world accuracy claims; then collect a separately labeled 200–250-job human-reviewed real set.
- [ ] Investigate ranker behavior that may merge distinct requisitions with the same employer/title; use ATS posting IDs and conservative equivalence checks. **Never discard application history** when grouping aliases.
- [ ] Measure source success, freshness, broken employer links, duplicate precision/recall and false merges; retain source-specific failure and partial-success states.
- [ ] Compare JobNavigator's posting identity, ApplyPack's structured scoring, JobSync's usage accounting and CareerPulse's source fault isolation. Port *small tested ideas* rather than wholesale competitor services.
- [ ] Profile memory, DB queries, embedding cache, ranker costs and bounded batches before adopting later August changes; current June architecture is not schema-compatible with those commits.

**Exit criteria:** before/after benchmark rows include dataset, commit, config, exact test, source and failure evidence. Publish no invented P@10, nDCG, cost or freshness numbers.

### P3 — Reliability, privacy, operating cost and maintenance

- [ ] Audit implicit resume-generation entry points (boot scan, ingestion, manual actions) for surprising costs.
- [ ] Instrument per-source yields/errors and per-provider request/token/cache use; make optional LLM spending explicit.
- [ ] Review dependencies for security fixes using compatible updates and regression tests, not blanket major-version changes.
- [ ] Exercise lease expiry, duplicate triggers, model 429/500, partial ingestion and worker restart against disposable data.
- [ ] Audit data sent to external LLMs, job sources and hosted services; document explicit consent/retention and local-vs-cloud boundaries.

## Repeatable validation commands

From the repository root, for **isolated** development with dependencies installed:

```bash
cd signalrank/backend
uv sync --python 3.12 --group dev --frozen
uv run --python 3.12 pytest -q \
  tests/test_inbox_sqlite_api.py \
  tests/test_desktop_inbox_upgrade.py \
  tests/test_resume_upsert_sqlite.py \
  tests/test_june_backend_backports_unit.py \
  tests/test_scoring.py tests/test_query_builder.py \
  tests/test_intent_matching.py tests/test_profile_rules.py \
  tests/test_desktop_mode.py
uv run --python 3.12 alembic heads

cd ../frontend
npm ci
npm run lint
npm run build
```

Offline migration SQL generation succeeded, but **running the migration against PostgreSQL and live browser testing remain unverified**. Real browser screenshots must come from an actual running instance with disposable accounts; never use a rendered mock or untested URL as evidence.

## Decisions and constraints

- Stay on `feature/june-06-backend-hardening` until the runtime and UX gates pass. Keep `main` unchanged; merge only through deliberate review.
- Avoid contacting real job sites, paying for AI calls, sending email or uploading real resumes during automated tests unless deliberately authorized.
- Do not commit `.env`, credentials, identifiable resumes, user employment records or generated personal benchmark exports.
- Every data migration must be additive, user-scoped, reversible where feasible, and backed up before deployment.
- Treat source-only competitor findings as **hypotheses** until runtime evidence exists.

## Supporting documents

- [June backend changes, implementation and validation](JUNE_06_BACKPORTS.md)
- [Canonical product spec](spec.md) (contains older vocabulary; needs reconciliation with current inbox routes)
- [Research and benchmark index](../../docs/README.md)
- [Pinned June source baseline](../../docs/benchmark/01-signalrank-baseline.md)
- [Competitor architecture review](../../docs/benchmark/02-competitor-review.md)
- [Feature comparison](../../docs/benchmark/03-feature-matrix.md)
- [Benchmark methodology and results ledger](../../docs/benchmark/04-benchmark-results.md)
- [Provisional reuse vs. replace architecture decision](../../docs/benchmark/05-reuse-vs-replace.md)
- [Benchmark-led engineering backlog](../../docs/benchmark/06-roadmap.md)
