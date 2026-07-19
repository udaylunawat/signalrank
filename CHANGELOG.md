# Changelog

All notable changes to SignalRank are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

### Desktop reliability and performance

- Fixed macOS startup failures caused by hardened signing of an ad-hoc PyInstaller sidecar whose extracted Python runtime had a different signing identity.
- Real Apple-signed builds now sign PyInstaller contents with the same identity; ad-hoc builds no longer enable hardened Library Validation.
- Sidecar exits now fail immediately, persist startup diagnostics, and show Retry and Open Log actions instead of leaving a permanent loading screen.
- Added startup phases, bounded frontend and proxy requests, missing-session recovery, post-start service failure notices, and stricter packaged smoke tests.
- Desktop restarts now discard only SignalRank session cookies before creating a fresh local session, preventing stale JWT errors without clearing cached application assets.
- Desktop dashboard navigation no longer passes through the hosted Auth.js middleware gate, preventing a silent redirect back to local setup when middleware and server session state differ.
- Local Auth.js sessions now start reliably, and a locked or prompting macOS Keychain can no longer block the backend event loop or leave setup stuck on **Open dashboard**.
- Backend and web sidecars now exit if the native shell crashes or is force-terminated, preventing orphaned services and idle memory leaks.
- Moved the local embedding model out of the one-file backend archive, deferred Keychain and heavy ranking imports, and reduced idle desktop worker polling.

### Added

- Added a shared application kit to Matches and Tracker for generating, editing, copying, and opening recruiter outreach plus generating and saving tailored PDF resumes.
- Added a lightweight cross-platform PDF renderer with classic, modern, and minimal layouts; desktop resume generation no longer depends on an unbundled Typst executable.
- Resume- and role-agnostic onboarding for PDF, DOCX, and TXT resumes.
- Structured resume parse status, confidence, source model, parser version, and recoverable error metadata.
- Deterministic resume extraction fallback for skills, experience, and recent titles.
- Editable free-text roles, locations, company preferences, and exclusions across onboarding and settings.
- AI-driven company reputation assessment through dynamically discovered OpenRouter free models.
- A role-independent company rubric with persisted score, tier, confidence, rationale, model, fingerprint, and expiry metadata.
- `all`, `top_reputed`, and explicitly selected AI company-tier filter modes.
- Match explanations containing role lane, matched resume skills, score dimensions, reputation context, and concerns.
- Company-reputation enrichment in the durable refresh worker.
- Regression coverage for company assessment, enrichment, role-agnostic ranking, resume parsing, and OpenRouter recovery behavior.

### Changed

- Deferred the PDF renderer until first use, capped the desktop Next.js heap, enabled its persistent compile cache, and disabled telemetry to reduce idle memory and improve repeat startup.
- OpenRouter clients now adopt a replaced desktop key without requiring an app restart.
- Removed fixed role presets and profession-specific role synonym assumptions from onboarding and ranking.
- Target-role scoring now uses free-text role signatures and preserves adjacent roles in a broader-match lane.
- Skill overlap now compares explicitly parsed resume skills with job content instead of inferring the candidate's skills from job descriptions.
- Company scoring now uses AI reputation when available and retains deterministic behavior for unassessed employers.
- Onboarding questions are generated from the extracted profile without assuming software-engineering roles.
- Degraded resume drafts are reparsed when the same file is uploaded after OpenRouter recovers.
- The OpenRouter client now preflights authentication, discovers current free structured-output models, records the actual selected model, and routes fallbacks in a single request where possible.
- The jobs UI and job cards now expose broader matches, matched skills, company-reputation context, and clearer explanations.

### Fixed

- Allowed the packaged loopback renderer to invoke only the validated native link-opening and save-dialog commands, fixing dead job links and desktop downloads without exposing a generic shell or opener permission.
- Tailored-resume and outreach failures now return actionable errors instead of blank content, false success, or an uncaught missing-renderer response.
- Prevented stale degraded resume results from remaining cached after credentials or provider availability improve.
- Prevented reasoning tokens from consuming the output budget for strict structured extraction.
- Added recovery for free-router `404` responses, empty completions, and HTTP `200` responses without choices.
- Preserved ranking when company enrichment is unavailable instead of failing the entire refresh run.
- Removed role-specific exclusions and labels that incorrectly suppressed valid resumes and professions.
- Kept explicitly preferred companies eligible when the **Top reputed** filter is active.

### Removed

- Removed the legacy DuckDB/Streamlit Job Ranker packages, duplicated archives, cached embeddings, benchmark artifacts, obsolete root scripts, and unused starter assets from `main`.
- Removed stale role-specific helper modules that were no longer part of the SaaS ranking path.
- Moved historical source material out of the production tree; it remains recoverable from `backup/main-2026-07-15`.

### Validation

- Backend test suite: 141 passing tests.
- Frontend lint and production build pass.
- End-to-end resume onboarding verified with a non-platform-engineering QA resume.
- Live OpenRouter structured extraction verified with currently available free models.
- Browser flow verified from onboarding through extracted profile, preferences, ranking, and matches.

## [0.1.0] - 2026-06-06

### Added

- Initial SignalRank desktop and web release.
- Resume ingestion, OpenRouter validation, job discovery, profile-driven ranking, and desktop packaging.

The original `v0.1.0` release remains available by tag. The pre-promotion `main` tip is also preserved on the dated backup branch created during the SaaS promotion.

## Legacy batch engine - 2026-03-10

Before the SaaS application, SignalRank operated as a DuckDB and Streamlit batch engine. That implementation introduced multi-source JobSpy discovery, deterministic scoring, immutable runs, recruiter tools, and the operational lessons retained in the current architecture. Its source remains available on the dated backup branch rather than in the active tree.
