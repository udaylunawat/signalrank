# SignalRank Website and Desktop End-to-End Test Plan

## Status

Validated planning document with the deterministic harness implemented in the
active checkout on 2026-08-01. Packaged WebView, upgrade, cross-OS, and live
provider cases remain release-lane work.

This document defines how to test the SignalRank website and packaged desktop
application end to end and how to record observations. Creating this plan does
not count as executing the journeys.

## Goal

Prove that a user can complete the full SignalRank product loop in both
deployment modes:

```text
account or local session
        |
        v
resume upload and extraction
        |
        v
preferences and onboarding completion
        |
        v
job discovery and ranking
        |
        v
explainable Matches
        |
        v
save, feedback, export, and application tracking
```

A test run is complete only when every named stage has browser or native-app
interaction evidence. Source inspection, API calls, unit tests, successful
builds, and service health checks support E2E testing but do not replace it.

## Current baseline observations

### Website

- The frontend has lint, development, and production-build commands.
- Playwright projects now cover SaaS Chromium, desktop-configured Chromium,
  mobile, and tablet viewports. The suite records stable case IDs and writes a
  sanitized observation log under `artifacts/e2e/<timestamp>-<commit>/`.
- The deterministic fixture backend covers auth, onboarding, runs, jobs,
  feedback, applications, desktop setup, and API-only resume tailoring without
  adding a production test endpoint.
- `.github/workflows/e2e.yml` runs migrations, the PostgreSQL backend contract
  lane, frontend lint/build, SaaS and desktop-web journeys, responsive checks,
  and the artifact scanner.
- The backend has broad pytest coverage for authentication, onboarding, jobs,
  runs, feedback, applications, discovery, ranking, and workers.
- Backend tests use real PostgreSQL and ASGI HTTP boundaries.
- The backend contract lane requires an isolated PostgreSQL instance and runs
  migrations before pytest; the local checkout currently has no reachable
  PostgreSQL service, so that lane must be run with the CI service or a local
  database.

### Desktop

- Desktop-mode backend tests use temporary SQLite databases and cover local
  identity, bootstrap authentication, provider-key fallback, SQLite settings,
  worker claims, and migration backup.
- `npm run smoke:sidecars` proves that built backend and web sidecars become
  healthy and then stop.
- `npm run smoke:packaged` proves that the packaged app launches its services,
  avoids Auth.js startup errors, exits, and leaves no sidecar processes.
- `.github/workflows/desktop-release.yml` builds release artifacts and runs
  packaged lifecycle smoke on macOS, Windows, and Linux.
- Neither smoke script interacts with the actual UI.
- `frontend/tests/e2e/desktop-web.spec.ts` now exercises the local session,
  provider setup, invalid-key recovery, resume upload, onboarding, and first
  ranked dashboard in a browser against a deterministic local backend.
- `desktop/src-tauri` now has unit coverage for secure external-link policy and
  sanitized CSV filenames. Packaged native UI, dialogs, OS keyring behavior,
  and upgrade recovery remain release-blocking gaps.
- The packaged smoke does not currently verify resume upload, extraction,
  ranking, Matches, Tracker, credential persistence, native links, native CSV
  save, or data preservation across upgrades.
- `signalrank/desktop/fixtures/smoke-resume.txt` exists but is not used by the
  current smoke scripts.

## Test principles

1. Use synthetic or explicitly consented resume fixtures. Never place a real
   resume, contact details, API key, access token, or local database in test
   artifacts.
2. Use a new account and isolated database or app-data directory for each run.
3. Keep deterministic CI and live external validation separate.
4. Use real PostgreSQL, SQLite, HTTP, sidecars, and application processes.
   Replace external providers with recorded local fixtures only in the
   deterministic lane.
5. Run opt-in live probes against real OpenRouter and job sources after the
   deterministic journey passes.
6. Do not change ranking weights or matching inputs to make an E2E test pass.
7. Redact request headers, credentials, resume text, and sensitive free text
   from logs and screenshots.
8. Record an explicit pass, fail, or blocked result for every case. Never infer
   browser or packaged-app success from static checks.

## Test lanes

### Lane A: deterministic CI

Use:

- isolated PostgreSQL for website tests;
- isolated SQLite app data for desktop tests;
- a consent-safe synthetic resume;
- recorded job-source responses;
- a local OpenRouter-compatible fixture service with representative success,
  authentication failure, rate limit, malformed response, and timeout cases;
- deterministic timestamps and seeded job records.

This lane is required on pull requests and must not require internet access,
provider quotas, or user credentials.

### Lane B: live release probe

Use:

- a dedicated test OpenRouter key;
- a public synthetic resume with no contact details;
- real enabled job sources;
- an isolated test account or desktop app-data directory;
- bounded queries, timeouts, and source limits.

Resume text may be sent to OpenRouter only after explicit authorization for
that fixture and destination. Capture provider/model identifiers and source
telemetry, but never the credential or full resume text.

## Environment matrix

| Mode | Data store | UI surface | Required coverage |
| --- | --- | --- | --- |
| SaaS development | Isolated PostgreSQL | Chromium | Every pull request |
| SaaS responsive | Isolated PostgreSQL | Chromium at 390x844, 768x1024, 1440x900 | Every pull request |
| SaaS cross-browser | Isolated PostgreSQL | Chromium, Firefox, WebKit | Release candidate |
| Desktop-configured web | Temporary SQLite | Browser against built sidecars | Every pull request |
| Packaged desktop | Temporary app-data directory | Actual Tauri WebView | Release candidate |
| Packaged upgrade | Previous-version app data | Actual installed application | Release candidate |
| Platform package | Fresh OS image | macOS, Windows, Linux | Release candidate |

Desktop-configured browser success does not prove packaged Tauri behavior.

## Phase 0: preflight and isolation

### Repository and build state

1. Record commit SHA, branch, operating system, architecture, and tool versions.
2. Record the dirty worktree without modifying or staging unrelated files.
3. Run `git diff --check`.
4. Verify ignored locations for screenshots, traces, downloads, temporary
   databases, and app data.

### Website services

1. Create or reset an isolated PostgreSQL test database.
2. Run `uv run alembic upgrade head`.
3. Confirm `uv run alembic current` matches the repository head.
4. Confirm backend and frontend secrets match without printing them.
5. Confirm the effective OpenRouter key source without printing the key.
6. Start backend and frontend on loopback addresses and random ports where
   supported.
7. Check backend health and the frontend login route.

### Desktop services

1. Create a new temporary `SIGNALRANK_APP_DATA_DIR`.
2. Confirm no production `.env`, local database, or credential-store entry is
   bundled into test artifacts.
3. Build and stage both sidecars.
4. Run `npm run check` and `npm run smoke:sidecars`.
5. Confirm processes stop cleanly before starting the UI journey.

## Phase 1: quality gates

Run these before browser testing:

```text
backend: uv run pytest -q
frontend: npm run lint
frontend: npm run build
desktop: npm run check
desktop: npm run smoke:sidecars
```

Implemented harness:

- `frontend/playwright.config.ts` defines SaaS, desktop-web, mobile, and tablet
  projects with retain-on-failure traces, screenshots, and videos.
- `frontend/tests/e2e/support/fixture-backend.mjs` provides deterministic
  provider/job responses and a reset hook for test isolation.
- `frontend/tests/e2e/support/observation-reporter.mjs` records every stable
  case ID with surface, viewport, fixture, result, evidence, severity, owner,
  and retest status; it also emits the complete requested stable-ID catalog so
  unregistered release cases are explicitly marked `Blocked`.
- `frontend/tests/e2e/support/case-catalog.mjs` defines the stable AUTH through
  SEC ranges from this plan.
- `frontend/tests/e2e/support/scan-artifacts.mjs` rejects credentials,
  authorization headers, fixture account data, and resume hashes in evidence.
- `frontend/tests/e2e/` covers the critical SaaS, desktop-web, accessibility,
  account-isolation, file-validation, discovery, matches, tracker, and settings
  journeys. Resume tailoring is API-only and covered by backend contract tests.

Run from `signalrank/frontend`:

```text
npm run lint
npm run build
npm run test:e2e:saas
npm run test:e2e:desktop-web
npm run test:e2e:responsive
npm run test:e2e:scan
```

The live lane is opt-in and must run separately from CI. From
`signalrank/backend`, provide a dedicated test key through the environment and
run `uv run python scripts/live_release_probe.py`; the probe emits only case
status, model, finish reason, HTTP status, and latency. Real-source discovery
probes should use the same isolated app-data/account boundary and bounded query
budgets before a release is approved.

## Phase 2: website E2E journey

### WEB-01 Authentication and routing

1. Open the website as a signed-out user.
2. Verify protected routes redirect to login with the intended destination.
3. Exercise invalid signup, valid signup, duplicate signup, invalid login, and
   valid login.
4. Verify session persistence after reload.
5. Verify sign-out and expired-session handling.
6. Use a second account to verify user isolation.

Evidence:

- screenshots of validation and successful routing;
- response status for auth failures;
- proof that account B cannot access account A's match detail.

### WEB-02 Resume onboarding

1. Upload valid TXT, PDF, and DOCX fixtures in separate cases.
2. Verify unsupported type, empty extraction, and file-over-10-MB errors.
3. Verify successful structured extraction and editable suggestions.
4. Verify degraded extraction preserves resume text and offers
   `Retry with OpenRouter`.
5. Recover the provider and retry without uploading the file again.
6. Verify prior onboarding answers survive retry and reload.
7. Complete onboarding with preferences.
8. Complete the resume-only path without optional preferences.
9. Replace the resume and verify the resulting profile state.

Evidence:

- upload and extracted-profile screenshots;
- sanitized parse status, confidence, source, and model;
- proof that raw resume text and contact details are absent from artifacts.

### WEB-03 Refresh and discovery

1. Start a refresh from the dashboard.
2. Verify queued, running, progress, source-coverage, and terminal states.
3. Verify a duplicate trigger coalesces or is rejected according to contract.
4. Verify results update automatically after completion.
5. Exercise partial source failure while retaining available matches.
6. Exercise total failure and a retry.
7. Verify stale/fresh boundaries and completion timestamps.

Live lane observations:

- queries issued;
- source-level jobs found and persisted;
- duration and failure summaries;
- total deduplicated jobs;
- no unbounded retry or runaway worker.

### WEB-04 Matches

1. Verify ranked counts and ordering against the seeded deterministic fixture.
2. Search by title, company, and location.
3. Exercise score, source, sort, and every implemented additive filter.
4. Reload and verify URL-backed filter restoration.
5. Change filters rapidly and verify stale responses do not overwrite the
   latest selection.
6. Expand `Why it fits` and verify score dimensions, matched signals,
   concerns, description, lane, and run timestamp.
7. Verify a job outside the current user's latest result returns 404.
8. Save a role to Tracker.
9. Submit every feedback reason and verify Undo.
10. Verify only HTTPS external links open.
11. Export CSV and validate filename, row count, columns, UTF-8 content, and
    spreadsheet-formula escaping.

### WEB-05 Tracker

1. Verify the initial empty state.
2. Save a role from Matches.
3. Update status, notes, applied date, next action, and interview date where
   supported.
4. Reload and verify persistence.
5. Delete and Undo.
6. Verify desktop table and mobile list/card layouts.
7. Verify failures do not optimistically leave incorrect state.

### WEB-06 Settings

1. Load profile values.
2. Add, edit, remove, and keyboard-submit array-backed values.
3. Verify duplicate normalization.
4. Save and reload.
5. Exercise a failed save and verify retry behavior.
6. Verify resume/provider status and replacement paths are understandable.

### WEB-07 Accessibility and responsive behavior

For 390x844, 768x1024, and 1440x900:

- complete the critical path with keyboard only;
- verify visible focus and logical focus order;
- verify dialogs/sheets trap focus and return it;
- run axe on login, onboarding, dashboard, Matches, detail, Tracker, and
  Settings;
- verify status is not conveyed by color alone;
- verify 200% zoom and reduced motion;
- capture approved deterministic visual snapshots.

## Phase 3: desktop-configured browser E2E

Run the same core journey against built frontend/backend sidecars with:

- `SIGNALRANK_MODE=desktop`;
- a temporary SQLite app-data directory;
- a per-launch bootstrap token and auth secret;
- the deterministic OpenRouter and job-source fixtures.

Add desktop-specific cases:

1. Local session starts without SaaS signup.
2. Desktop setup takes precedence over onboarding until provider setup is
   complete.
3. Provider-key validation succeeds and failure remains recoverable.
4. Credential-store failure uses the documented session-only fallback and
   never plaintext storage.
5. SQLite migrations and backup behavior are visible and safe.
6. State persists across sidecar restart.
7. Built sidecars do not require system Python, Node.js, PostgreSQL, or cloud
   SignalRank services.

## Phase 4: packaged Tauri E2E

Keep the existing packaged lifecycle smoke, then add actual native UI
interaction using platform-appropriate automation.

### DESK-01 Clean launch

1. Install or launch the packaged artifact with fresh app data.
2. Verify the real Tauri window appears.
3. Verify local sidecars become healthy.
4. Verify local-session bootstrap reaches desktop setup.
5. Confirm no unexpected external network call before the user invokes a
   provider/source feature.

### DESK-02 Full local journey

1. Configure a test provider key.
2. Upload the synthetic resume through the native WebView.
3. Complete preferences.
4. Run deterministic discovery and ranking.
5. Review match explanation.
6. Save a role, submit feedback, and update Tracker.
7. Relaunch and verify all local state persists.

### DESK-03 Native boundaries

1. Open an HTTPS job link and verify the operating-system browser receives it.
2. Reject `http`, `file`, `javascript`, malformed, and relative URLs.
3. Export CSV through the native save dialog.
4. Test save, cancel, sanitized filename, existing-file handling, and content.
5. Verify the renderer has no generic shell or filesystem access.

### DESK-04 Lifecycle and failures

1. Close normally and verify both sidecars stop.
2. Kill one sidecar and verify visible recovery/failure behavior.
3. Launch while the preferred ports are occupied.
4. Exercise credential-store unavailable and locked states.
5. Exercise missing/corrupt bundled resource behavior.
6. Confirm crash/error logs contain no key, token, or resume text.

## Phase 5: upgrade and platform matrix

For macOS, Windows, and Linux:

1. Install the previous supported version.
2. Complete onboarding and seed Matches/Tracker data.
3. Upgrade to the release candidate.
4. Verify schema migration, profile, jobs, feedback, applications, notes, and
   provider state.
5. Test invalid signature, interrupted download, unavailable manifest, and
   insufficient disk/network failure paths.
6. Verify rollback or recovery behavior.
7. Verify the application and child processes uninstall/exit cleanly.

Do not claim release readiness from local build checks alone.

## Observation log

Record one row per case:

| Field | Required value |
| --- | --- |
| Case ID | Stable ID such as `WEB-04.06` |
| Result | Pass, fail, or blocked |
| Surface | SaaS, desktop-configured web, packaged desktop |
| Environment | OS, architecture, browser/WebView, viewport |
| Build | Commit SHA and package version |
| Fixture | Synthetic resume and recorded/live source set |
| Expected | Objective observable result |
| Observed | Concise factual behavior |
| Evidence | Screenshot, trace, video, sanitized log, download, or DB assertion |
| Severity | P0, P1, P2, P3, or none |
| Reproduction | Minimal deterministic steps |
| Owner | Frontend, backend, desktop, source, provider, or infrastructure |
| Follow-up | Issue/fix reference and retest result |

### Severity

- **P0:** data loss, credential/resume exposure, account isolation failure, or
  unsafe native command.
- **P1:** critical journey cannot complete, packaged app cannot launch, or
  ranking results never become available.
- **P2:** major feature failure with a workaround, incorrect status, broken
  responsive layout, or inaccessible critical action.
- **P3:** localized visual, wording, or low-impact interaction defect.

## Evidence package

Store ignored artifacts under a unique run directory:

```text
artifacts/e2e/<timestamp>-<commit>/
├── environment.json
├── results.json
├── observations.md
├── screenshots/
├── traces/
├── videos/
├── downloads/
└── sanitized-logs/
```

Before delivery, scan the package for:

- API keys and bearer tokens;
- email addresses and account identifiers;
- resume/contact text;
- database connection strings;
- local filesystem user paths.

## Execution order

1. Add the deterministic seed layer and Playwright/axe/visual harness.
2. Run quality gates and the SaaS Chromium critical journey.
3. Expand to responsive, failure, security, Tracker, and Settings cases.
4. Run the shared journey against built desktop sidecars.
5. Extend packaged smoke into actual native UI E2E.
6. Run the opt-in live OpenRouter and job-source probe.
7. Run cross-browser SaaS and packaged macOS/Windows/Linux release gates.
8. Publish the observation log with explicit pass/fail/blocked status and
   retest every fix.

## Exit criteria

- The complete onboarding-to-Tracker journey passes in SaaS Chromium at all
  required viewports.
- SaaS release candidates pass Chromium, Firefox, and WebKit.
- The shared journey passes against built desktop sidecars with temporary
  SQLite data.
- The actual packaged Tauri UI completes the critical journey on every
  supported OS.
- Native links, downloads, credential handling, process lifecycle, migration,
  and upgrade preservation pass.
- At least one successful and one degraded/recovery provider flow pass.
- At least one successful, partial, and failed discovery flow pass.
- No P0 or P1 issue remains open.
- P2 issues have an approved disposition and retest record.
- Accessibility checks meet the project WCAG 2.2 AA requirements.
- Evidence contains no credentials, resume text, contact details, or committed
  local data.
- Final reporting distinguishes deterministic tests from live external probes.
