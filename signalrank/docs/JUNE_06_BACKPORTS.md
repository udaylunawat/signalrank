# June 6 SignalRank: backend hardening baseline

## Branch and scope

- Branch: `feature/june-06-backend-hardening`
- Historical base: `fa2d42767186d81b511b50c81494212b60ceea27` (2026-06-06)
- Goal: retain the June 6 frontend, tracker, recruiter management and scoring workflow while adapting narrowly compatible fixes found in the later SaaS application. This is **not** a wholesale cherry-pick of July's redesigned backend.
- Worktree: `/workspace/projects/signalrank-june-06-backend-hardening`; existing `main` and local user data were not changed.

## Initial backports

1. **Location-aware job search.** Both single-run and multi-run Matches queries now use the same search clause for title, company and location, rather than title and company alone. No API contract change.
2. **Save-only tracking.** `POST /api/applications` persists the application without immediately enqueuing resume generation or starting recruiter discovery. This removes unexpected paid/network/background work on simple saves and preserves existing explicit recruiter and resume capabilities.
3. **Clearable tracker fields.** `PATCH /api/applications/{id}` distinguishes omitted fields from explicit JSON `null` for notes, priority, location group, interview date and offer compensation. A malformed interview date produces HTTP 422 rather than an internal server error.

These are **adaptations** of later workflow improvements, not literal merged commits. July changed architecture and data contracts substantially.

## Validation

- Python 3.12 is used explicitly for the local isolated development environment; repository `.python-version` (3.11) is unchanged.
- Backend dependencies: `uv sync --python 3.12 --group dev --frozen` — passed.
- Backend unit tests:
  `uv run --python 3.12 pytest -q tests/test_june_backend_backports_unit.py tests/test_scoring.py tests/test_query_builder.py tests/test_intent_matching.py tests/test_profile_rules.py`
  — **109 passed**.
- Database-backed tests `tests/test_applications_api.py` and `tests/test_jobs_api.py` are included and contain four additional regression cases, but they **cannot be executed** in the WebCodex runner without PostgreSQL and the pgvector extension. No database server was listening at `localhost:5432` during validation.
- Additional isolated tests: `tests/test_desktop_mode.py` — **10 passed**; `tests/test_resume_worker.py -k "not creates_tailored_resume"` — **5 passed, 1 deselected**.
- **124** distinct backend tests passed in these isolated suites; the full backend suite was not run.
- The PDF-generation test could not complete because the optional `typst` executable is not installed in this runner.
- Frontend: `npm ci --no-audit --no-fund`, `npm run build`, and `npm run lint` — passed.
- FastAPI import smoke check — **82 routes** registered successfully.
- Python syntax compilation, essential Ruff rules, and `git diff --check` — passed.

## Important existing behavior and limitations

- June already persists runs and has lease/heartbeat/worker-recovery machinery; the later SaaS durable-runs implementation does not map cleanly to this historical schema. Compare behavior before backporting anything from `d1aec39`.
- The optional `RUN_BOOT_SCAN` worker and the ingest pipeline still have their own generation-queue logic. The normal application-save API no longer enqueues generation; these separate background paths are not changed by this patch.
- Existing generated resumes, recruiter records and saved application data are not deleted.
- The June UI and frontend dependencies are retained. No attempt was made to replace it with the July overview/matches/tracker redesign.

For prioritized active work and acceptance criteria, see [JUNE_06_ROADMAP.md](JUNE_06_ROADMAP.md).

## Original next-work list (partly delivered in November 2026)

1. Establish isolated PostgreSQL + pgvector and run database-backed tests, API smoke tests, and end-to-end refresh tests using disposable data.
2. Audit resume-generation entry points and expose generation explicitly in the June UI if save-only should be enforced across all paths.
3. Add a durable review inbox (new/reviewed/dismissed/snoozed) with user-scoped database state and daily follow-up actions.
4. Add next action and due date to the existing full-featured tracker without discarding notes, priority, interviews, offer data or recruiter management.
5. Compare later OpenRouter/score-fallback and bounded-memory changes against June implementations, port only test-supported differences.
6. Resolve dependency vulnerabilities; do not apply blind major-version upgrades.


## November 17: durable daily workflow (next development phase)

The June 6 appearance and existing tracker features remain intact. This phase adds:

- A new `/inbox` screen and navigation entry, with score threshold, persisted user-specific review states (new, reviewed/undecided, dismissed, snoozed, resurfaced/due, saved), bulk review for the current page, and individual restore/snooze actions.
- Review decisions are stored in `job_review_states`, unique per user and job, rather than transient browser state. Dismissed and future-snoozed items are excluded from both existing Matches queries; expired snoozes resurface automatically. The Matches cached result is bypassed for users with review records.
- The daily inbox summary provides follow-ups due and interviews scheduled for the coming seven days. The dashboard now links prominently to the inbox, ahead of operational scan diagnostics.
- Existing tracker cards now include a next-action description and date; overdue tasks appear in a needs-attention strip. Priority, notes, interviews, compensation and recruiter management remain available.
- New Alembic revision `7d0e20261117` adds the review table and application scheduling fields for PostgreSQL. The desktop SQLite compatibility startup path adds missing columns and index without dropping existing application rows.
- Adapted later commit `b2719eb`: resume drafts use a dialect-aware atomic UPSERT keyed on user/job. A newly generated PDF replaces outdated stored PDF bytes; certifications persist in the structured content. Concurrent writes do not race at SELECT-then-INSERT.

### Tests and operating constraints

`uv run --python 3.12 pytest -q tests/test_inbox_sqlite_api.py tests/test_desktop_inbox_upgrade.py tests/test_resume_upsert_sqlite.py` runs API-level regression tests against *disposable* SQLite databases. It verifies user-scoped review isolation, persistent dismissal in Matches, snooze resurfacing, bulk review, tracked follow-ups, safe migration of an existing desktop application row, and idempotent tailored-resume regeneration.

Run the existing targeted scoring, intent, desktop and previous backport unit suites as well, plus `npm run build` and `npm run lint` for the June frontend. Full targeted phase gate: **126 backend tests passed**, frontend build and ESLint passed, essential Ruff rules passed. Offline Alembic SQL generation through new head passed (614 lines; includes review state table and follow-up columns). PostgreSQL/pgvector migrations and the full DB-backed integration suite remain unverified in the WebCodex environment because no PostgreSQL instance or container runtime is installed. Real browser interaction and screenshots remain unverified because browser control was denied and a local browser binary is not installed.

### Deferred work and known boundaries

- **No real push notifications or background reminders yet.** Overdue tasks are visible when the user opens the dashboard, inbox or tracker.
- **"New" means not yet reviewed**, rather than strict first-seen-since-last-visit, until a durable last-visit cursor is implemented. The user can choose a 65+ score threshold or all scored jobs.
- The user-owned jobs review query uses existing latest JobResult per user; this preserves rerank compatibility, but no parallel event history of review actions is recorded.
- Later ranking-memory and durable-run commit `1487a73` / `d1aec39` use significantly different schema (e.g. active jobs/enrichment or SaaS ingestion), so those changes were *reviewed but not cherry-picked*. Detailed benchmarking is required before modifying June ranking.
- A full PostgreSQL integration pass, browser E2E on desktop/mobile, and production migration smoke test should precede deployment. Never apply migrations against a user's existing production database without a backup.


## November 17: first-match timestamps and visit window

- The new `job_results.first_seen_at` records a user's first match with a posting and is intentionally **not reset by subsequent reranks**. SQLite desktop startup safely backfills this field on existing rows. PostgreSQL Alembic revision `8e0e20261117` backfills legacy rows from the latest known run date (or the job ingestion date); an exact historical first-seen time cannot be reconstructed from previously overwritten results.
- The `user_inbox_visits` table stores an authenticated user's last and previous review visits. `POST /api/inbox/visit` atomically advances the window with an idempotent page-visit ID. The frontend distinguishes **New since last visit** from the existing **Unreviewed** backlog. New arrivals during the current visit appear in the next visit window.
- The new `since_visit` inbox bucket includes only unreviewed postings first matched after the previous visit and by the current visit. Saved, reviewed, dismissed and snoozed jobs remain excluded from it as intended; the backlog remains separately accessible.
- Disposable SQLite regression coverage verifies duplicate visit IDs, visit rotation, new jobs appearing, cross-user isolation, reviewed/dismissed exclusions, rerank preserving first-seen timestamps, and additive desktop upgrades.
- Validation for this update: **130 targeted backend tests passed**, frontend production build and lint passed, changed-file Ruff rules passed, and Alembic `upgrade head --sql` generated 642 lines including the new revision. **PostgreSQL migration execution and browser E2E were not run**; this branch is not approved for production deployment on this evidence alone.
