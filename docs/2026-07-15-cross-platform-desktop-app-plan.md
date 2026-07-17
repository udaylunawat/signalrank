# SignalRank Local-First Desktop App Plan

## Product decision

SignalRank Desktop is a self-contained, local-first application for Windows,
macOS, and Linux.

It does not use SignalRank-hosted infrastructure:

- no hosted SignalRank API;
- no hosted PostgreSQL database;
- no hosted worker or scheduler;
- no account or data synchronization with the web app;
- no SignalRank telemetry in the first release.

The installed app runs scraping, ranking, persistence, and the UI on the user's
machine. Network access is limited to user-initiated or scheduled job-source
scraping, OpenRouter requests, update checks, and opening external job links.

## Desktop v1 capabilities

- Local profile and resume onboarding.
- User-supplied OpenRouter key with live validation.
- Local scraping through JobSpy and supported public job APIs.
- Local deterministic ranking and local embedding inference.
- Local job catalog, runs, preferences, match results, and application tracker.
- Resume upload, ranked-job browsing, CSV export, and external apply links.
- Signed application updates for Windows, macOS, and Linux.

The desktop app remains useful when OpenRouter is unavailable: deterministic
resume parsing and ranking continue with a visible degraded-status message.
Scraping and OpenRouter inherently require internet access; previously stored
jobs, profiles, matches, and tracker data remain available offline.

## Architecture

Restore and adapt the Tauri 2 desktop implementation preserved in the `v0.1.0`
tag.

```text
Tauri 2 native shell
    |
    +-- Next.js standalone sidecar on 127.0.0.1:<random-port>
    |
    +-- PyInstaller FastAPI sidecar on 127.0.0.1:<random-port>
            |
            +-- local SQLite database
            +-- local scraper and ranking worker
            +-- bundled local embedding model
            +-- OpenRouter using the user's API key
```

Packaged users do not install Python, Node.js, Rust, PostgreSQL, or model
tooling. Every runtime dependency is included in the installer.

### Why Tauri 2

1. The repository already shipped a functioning Tauri 2 desktop shell at
   `v0.1.0`, including sidecar lifecycle management, build scripts, icons, and
   packaged smoke tests.
2. The current Next.js frontend uses NextAuth and server-side routes, so bundling
   its standalone server avoids a static-export rewrite.
3. The existing FastAPI, scraper, and ranking code can be packaged with
   PyInstaller and run locally instead of being rewritten in Rust or TypeScript.
4. Tauri exposes native capabilities through an explicit allowlist and has a
   smaller shell than Electron.

Electron remains a fallback only if platform WebView defects become a sustained
product issue. A separate native UI would duplicate the product and is out of
scope.

## Reuse from `v0.1.0`

Restore selected files from the tagged desktop release, then port them to the
current backend and frontend contracts:

- `signalrank/desktop/src-tauri/` shell, icons, and window configuration;
- Node/Next.js standalone build and sidecar staging scripts;
- PyInstaller backend build script;
- random loopback-port allocation and readiness checks;
- complete child-process-tree shutdown;
- desktop setup page and desktop-mode routing patterns;
- packaged smoke-test harness;
- `.github/workflows/desktop-release.yml` as the release CI baseline;
- desktop SQLite compatibility and Python similarity fallbacks as design
  references.

Do not cherry-pick the old desktop commits wholesale. The active SaaS promotion
changed the schema, API routes, ranking behavior, frontend, and onboarding
contracts. Each restored desktop component must be reconciled with the current
code.

## Local data and runtime behavior

### Local database

Use SQLite in the operating system's application-data directory:

| Platform | Data location |
| --- | --- |
| macOS | `~/Library/Application Support/app.signalrank.desktop/` |
| Windows | `%APPDATA%\\app.signalrank.desktop\\` |
| Linux | `$XDG_DATA_HOME/app.signalrank.desktop/` or `~/.local/share/app.signalrank.desktop/` |

The directory contains the SQLite database, application logs, cached job-source
responses, and local model/cache metadata. Resumes and generated artifacts are
stored there by default or exported to a user-selected location.

Requirements:

- Enable SQLite WAL mode and a busy timeout.
- Keep one application-managed writer queue.
- Use versioned desktop schema migrations; `create_all` alone is not sufficient
  after the first public release.
- Run an automatic database backup before every schema migration.
- Provide a user action to open the data folder and another to export a portable
  backup.
- Never store OpenRouter or scraper API keys in SQLite.

### PostgreSQL and pgvector portability

The current SaaS models and migrations assume PostgreSQL and pgvector. Desktop
mode must provide explicit portable behavior:

- store embeddings as a SQLite-compatible binary or JSON representation;
- run cosine similarity in local Python/NumPy for the bounded candidate set;
- replace PostgreSQL-only expressions with tested SQLite equivalents;
- preserve the same deterministic ranking features and explanations;
- keep desktop schema adaptations outside pure `domain/` scoring code.

The old `v0.1.0` SQLite tests and Python ANN fallback are the starting point, but
they must be updated for the current schema and ranking pipeline.

### Local embedding model

Bundle the supported local embedding model with the application so ranking does
not depend on a model download after installation. The model is loaded by the
local backend and cached in process.

Phase 0 must measure installer size, cold-start time, memory, and ranking
latency on each target. If the current sentence-transformers stack makes the
package unacceptably large, evaluate an ONNX build of the same model before
changing ranking semantics.

### OpenRouter

- The user supplies their own OpenRouter key during local setup.
- Validate the key and preflight currently available free structured-output
  models before enabling LLM features.
- Store the key in the operating system credential store through Python
  `keyring` or an equivalent Tauri-backed secure store.
- If secure persistence is unavailable, keep the key for the current session
  only; never fall back to a plaintext config file.
- Send OpenRouter requests directly from the local FastAPI process.
- Show which model was used, whether the response was degraded, and whether the
  deterministic fallback ran.
- Never log the key, authorization headers, or full resume prompt payloads.

OpenRouter receives only the inputs required for the chosen feature. The setup
flow must disclose that resume text sent for LLM parsing leaves the device.

### Scraping and local worker

- Run JobSpy and public-source adapters inside the packaged Python backend.
- Preserve serialized Indeed execution, bounded delay, retry/backoff, and
  per-source telemetry.
- Use free sources without credentials and expose optional scraper API keys only
  for adapters that require them.
- Store scraper credentials in the same secure store policy as OpenRouter.
- Run the durable worker in the local backend process for v1.
- Resume or fail stale runs cleanly after a crash or forced shutdown.
- Show source counts, errors, cache age, and partial-run state in the UI.
- Stop active scraping on app exit after a bounded graceful-shutdown window.

Scheduled scans run only while SignalRank Desktop is open in v1. Background tray
execution and launch-at-login are deferred until lifecycle behavior is stable.

### Local identity and authentication

Desktop mode has one local profile and no signup/login screen.

- Create the local user and profile idempotently on first launch.
- Generate a unique per-install authentication secret; never use the old
  hard-coded desktop secret.
- Require a high-entropy bootstrap token shared only between the Tauri shell and
  its two sidecars before issuing a local application session.
- Bind both services only to `127.0.0.1` on random ports.
- Reject non-local origins and unexpected host headers.
- Keep the browser session local to the installed app.

This local session protects the app from unrelated processes and websites on the
same machine; it is not a SignalRank cloud account.

## Native security boundary

The renderer receives only narrowly scoped native behavior:

- open validated `https://` job URLs in the system browser;
- choose resume files through a native open dialog;
- save exports and backups through a native save dialog;
- show the local data or log directory;
- report version and update state;
- install a signed update after confirmation.

No generic shell execution, unrestricted filesystem access, arbitrary URL
navigation, or raw IPC bridge is exposed. Tauri capabilities must list every
allowed command, URL, and filesystem scope explicitly.

## Delivery plan

### Phase 0: Restore and prove the local runtime

Target: 2-3 engineering days.

1. Restore the minimal Tauri shell, build scripts, icons, and smoke fixtures from
   `v0.1.0`.
2. Restore `SIGNALRANK_MODE=desktop` configuration without changing web/SaaS
   defaults.
3. Package the current Next.js standalone server as a Node sidecar.
4. Package the current FastAPI app as a PyInstaller sidecar.
5. Launch both on random loopback ports and implement readiness/error screens.
6. Create a current-schema SQLite database in an isolated app-data directory.
7. Prove local profile creation, clean shutdown, and process cleanup on the
   development OS.

Exit criteria:

- A packaged development build starts without system Node, Python, Rust,
  PostgreSQL, or Docker.
- It opens the local setup flow backed by a local SQLite file.
- No child process remains after app exit.
- No request reaches a SignalRank-hosted service.

### Phase 1: Port persistence and ranking to SQLite

Target: 4-6 engineering days.

1. Inventory every PostgreSQL-only model type, query, migration, lock, and
   pgvector operation used by current workflows.
2. Add portable desktop storage types and SQLite query paths.
3. Port current schema creation and versioned migrations.
4. Restore Python/NumPy embedding similarity for local candidate retrieval.
5. Bundle and load the local embedding model.
6. Port durable run claiming, retry, freshness, source telemetry, and ranking to
   a single local writer model.
7. Add database backup, restore, corruption, and migration-failure handling.

Exit criteria:

- Current backend tests pass in PostgreSQL mode.
- A desktop-specific SQLite suite covers all tables and core workflows.
- The same frozen job/profile fixture produces equivalent ranking order and
  explanations in PostgreSQL and SQLite within documented numeric tolerance.
- Restarting during a run does not corrupt the database or orphan it silently.

### Phase 2: Local setup, OpenRouter, and scraping

Target: 3-5 engineering days.

1. Restore the desktop setup API and update it for the current profile schema.
2. Add secure OpenRouter-key save, validation, free-model preflight, replacement,
   and removal.
3. Add optional secure scraper-key management.
4. Port resume upload and deterministic/LLM parsing to the local profile.
5. Run a real local scrape through each free source and JobSpy.
6. Persist source telemetry and expose fresh, partial, cached, and failed states.
7. Trigger local ranking immediately after successful ingestion.

Exit criteria:

- A fresh install can accept a resume, validate an OpenRouter key, scrape real
  jobs, rank them locally, and display explanations.
- Removing or invalidating the OpenRouter key visibly activates deterministic
  fallback without blocking scraping or ranking.
- API keys survive restart only when a secure credential store is available.
- Secrets never appear in the SQLite database, logs, crash output, or UI state.

### Phase 3: Complete desktop product parity

Target: 3-5 engineering days.

1. Skip web signup/login and establish the protected local session.
2. Port onboarding, settings, dashboard, jobs, filters, refresh progress, and
   tracker to desktop mode.
3. Open apply links in the system browser without navigating the app window.
4. Save CSV and backup exports through native dialogs.
5. Add offline, source-unavailable, OpenRouter-unavailable, startup-failure, and
   database-recovery states.
6. Add single-instance behavior and bounded graceful shutdown.

Exit criteria:

- Every workflow in the desktop v1 capability list passes in a packaged build.
- Stored jobs, matches, settings, and applications remain usable offline.
- External links cannot navigate the Tauri WebView.
- Closing the app stops local workers and sidecars without data loss.

### Phase 4: Cross-platform packaging and release

Target: 4-6 engineering days plus signing-certificate provisioning.

Build on each target operating system because PyInstaller, Node, native Python
dependencies, embedding runtimes, and installers are platform-specific.

| Platform | Initial artifacts | Release requirements |
| --- | --- | --- |
| macOS arm64 and x64 | Signed and notarized DMG | Developer ID, hardened runtime, notarization, stapling |
| Windows x64 | Per-user NSIS installer | Authenticode signing, WebView2 handling, clean-machine test |
| Linux x64 | AppImage and `.deb` | WebKitGTK compatibility, desktop entry, icons, distro smoke tests |

Each release job must:

1. install pinned Node, Rust, Python, `uv`, and platform build dependencies;
2. run backend, frontend, and Rust checks;
3. build the platform-native Python and Node sidecars;
4. verify the embedding model and required resource files are present;
5. build and sign the installer plus updater artifacts;
6. install and run the packaged smoke suite with isolated app data;
7. upload artifacts, checksums, and an SBOM only after smoke tests pass.

Use Tauri's signed updater with protected stable and prerelease channels. Roll
out to internal users, then beta, then stable. Published versions are immutable;
a broken release is replaced only by a higher version.

Exit criteria:

- Clean Windows, macOS, and Linux machines can install, launch, scrape, rank,
  restart, update, back up, and uninstall without developer tools.
- macOS opens without a Gatekeeper override and Windows identifies the
  publisher.
- Update artifacts fail closed when their signature is invalid.
- User data survives application upgrades and is removed only through an
  explicit user choice during uninstall or in-app reset.

### Phase 5: Desktop-native enhancements

Add only after local runtime and release reliability are stable:

1. native notifications for completed scans and new high-value matches;
2. optional tray execution for scans while the main window is closed;
3. opt-in launch at login and scheduled local scans;
4. deep links such as `signalrank://jobs/<id>`;
5. encrypted portable backup and restore.

Each background capability requires an explicit user control, a resource budget,
and cross-platform lifecycle tests.

## Verification strategy

### Every pull request

- existing PostgreSQL backend tests;
- desktop SQLite backend tests;
- frontend ESLint and production build;
- `cargo fmt --check`, `cargo clippy`, and Rust unit tests;
- local-auth, URL-allowlist, secure-storage, migration, and process-lifecycle
  tests;
- a desktop build check that verifies both sidecars and all bundled resources.

### Packaged smoke suite on every supported OS

Run with a new temporary app-data directory:

1. launch both sidecars and wait for health;
2. complete the local session handshake;
3. save and reload a test OpenRouter key through a fake local validation server
   in the non-live suite;
4. upload a small fixture resume;
5. ingest a recorded job-source fixture and rank it locally;
6. load jobs, tracker, and settings;
7. save a CSV and database backup to a temporary directory;
8. restart and verify persisted local state;
9. close and verify that no child process remains;
10. upgrade from the previous release and verify schema migration plus data
    retention.

Keep live OpenRouter and source probes in a separate opt-in release gate because
they depend on credentials, quotas, and current provider availability.

## Guardrails

- `domain/` ranking code remains pure and shared across deployment modes.
- Desktop data never syncs to SignalRank infrastructure.
- SignalRank servers never receive the resume, job catalog, profile, tracker, or
  API keys.
- OpenRouter and job sources receive only the traffic necessary for the feature
  the user invokes.
- Desktop releases never contain `.env` files, credentials, real resumes, test
  user data, or access tokens.
- Secure-store failure never falls back to plaintext secret persistence.
- Platform support requires signed artifacts and clean-machine smoke coverage,
  not only a successful compilation.

## Main risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Python, Node, and the embedding model make installers large | Use PyInstaller collection allowlists, Next.js standalone output, resource audits, and an ONNX embedding runtime evaluation after measuring the baseline |
| PostgreSQL behavior diverges from SQLite | Maintain shared domain fixtures, dialect-specific storage tests, and cross-database ranking parity tests |
| Scrapers behave differently across packaged OS builds | Run recorded contract tests everywhere and separate live source probes per OS before release |
| Another local process calls the loopback API | Random ports, a per-launch bootstrap token, local-origin checks, short-lived local sessions, and no unauthenticated desktop session endpoint |
| API keys leak through fallback files or logs | OS secure store only, session-only fallback, redaction tests, and no secret-bearing command arguments |
| Model or native Python dependencies fail on a clean machine | Bundle all runtime resources and run install-to-rank smoke tests on clean OS images |
| App exits during a scrape or migration | Graceful cancellation, WAL, bounded worker shutdown, migration backups, and startup recovery |
| Old desktop code conflicts with the promoted SaaS tree | Restore component-by-component and validate against current API, schema, ranking, and UI contracts |

## Definition of done for desktop v1

- Signed installers are available for macOS arm64/x64, Windows x64, and Linux
  x64.
- The installed application needs no SignalRank cloud service or developer
  runtime.
- Profile, resumes, jobs, runs, rankings, preferences, and tracker state are
  stored only in the local app-data directory.
- A user can configure OpenRouter, scrape real job sources, and rank results on
  the local machine.
- Deterministic fallback keeps core local workflows available without
  OpenRouter.
- Install, first run, scrape, rank, restart, backup, upgrade, and uninstall pass
  on clean machines for every supported platform.
- No high-severity finding remains in the local API, native IPC, secure storage,
  updater, or external-navigation threat model.
