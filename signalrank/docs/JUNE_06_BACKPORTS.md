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

## Next work on this branch

1. Establish isolated PostgreSQL + pgvector and run database-backed tests, API smoke tests, and end-to-end refresh tests using disposable data.
2. Audit resume-generation entry points and expose generation explicitly in the June UI if save-only should be enforced across all paths.
3. Add a durable review inbox (new/reviewed/dismissed/snoozed) with user-scoped database state and daily follow-up actions.
4. Add next action and due date to the existing full-featured tracker without discarding notes, priority, interviews, offer data or recruiter management.
5. Compare later OpenRouter/score-fallback and bounded-memory changes against June implementations, port only test-supported differences.
6. Resolve dependency vulnerabilities; do not apply blind major-version upgrades.
