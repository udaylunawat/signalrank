# Changelog

All notable changes to SignalRank are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

### Added

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

- Removed fixed role presets and profession-specific role synonym assumptions from onboarding and ranking.
- Target-role scoring now uses free-text role signatures and preserves adjacent roles in a broader-match lane.
- Skill overlap now compares explicitly parsed resume skills with job content instead of inferring the candidate's skills from job descriptions.
- Company scoring now uses AI reputation when available and retains deterministic behavior for unassessed employers.
- Onboarding questions are generated from the extracted profile without assuming software-engineering roles.
- Degraded resume drafts are reparsed when the same file is uploaded after OpenRouter recovers.
- The OpenRouter client now preflights authentication, discovers current free structured-output models, records the actual selected model, and routes fallbacks in a single request where possible.
- The jobs UI and job cards now expose broader matches, matched skills, company-reputation context, and clearer explanations.

### Fixed

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

- Backend test suite: 121 passing tests.
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
