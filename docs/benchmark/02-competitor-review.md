# 02 — Competitor code review (static)

**Review date:** 2026-11-17. **Baseline:** SignalRank `feature/june-06-backend-hardening` at `97adf1b`. **All competitor observations:** GitHub README, repository tree, source and test manifests; **no application was run or browser-tested**. Pin all hashes again at execution time if repositories advance. Source features are not real-world availability claims.

## Comparable repositories and pinned observations

| Repository | Reviewed HEAD | Declared license | Test files identified* | Latest committed date observed |
| --- | --- | --- | ---: | --- |
| [JobNavigator](https://github.com/vesaias/JobNavigator) | `232956b4962870f90178758321e46cd5f953c6d0` | MIT | 271 | 2026-11-16 |
| [ApplyPack](https://github.com/applypack/applypack) | `b40a9bc3c32e32463344e05678b467d3b7333f2e` | MIT | 359 | 2026-11-16 |
| [JobSync](https://github.com/Gsync/jobsync) | `4be4faa0a3132358157f0446388a1b6db255e10c` | MIT | 347 | 2026-11-14 |
| [CareerPulse](https://github.com/tcpsyn/CareerPulse) | `629aa992f3e3c3d05575686f350a7173e8b5e108` | MIT in `LICENSE` file (GitHub auto-detection ambiguous) | 71 | 2026-04-15 |
| [JobSpy](https://github.com/speedyapply/JobSpy) | `68b88d6909a2342ad75fbb945c4204a3a7ed6665` | MIT | Not counted | 2026-10-27 |
| [JobSentinel](https://github.com/cboyd0319/JobSentinel) | `98ee94b64e22670a568464f1042dfed991773eb1` | MIT | Not validated in this audit | 2026-11-13 |

*Test-file count = filenames matching `test_*.py`, `*.test.ts[x]` or `*.spec.ts[x]` in the Git tree, not passed test counts. JobSync additionally has `tests/e2e` and `evals`; ApplyPack has many `src/*.test.ts` files. License compatibility is preliminary; inspect vendored/third-party dependencies before copying code.

## 1. JobNavigator — strongest verified job-identity design

**Stack:** FastAPI/SQLAlchemy/Python/Postgres, frontend, background APScheduler, JobSpy 1.4.1, Playwright, optional LLM services.

**Sources / architecture:** `backend/scraper/ats/` includes Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Oracle HCM, Google, Meta and other adapters. `backend/scraper/sources/` integrates JobSpy and aggregator sources. Orchestration is under `backend/scraper/orchestrator.py`.

**Dedup evidence:**
- `backend/scraper/_shared/dedup.py`: protects identity-bearing query keys (Indeed `jk`, LinkedIn `currentJobId` in relevant paths), folds URL variants for hashing, preserves clickable source URL separately.
- `backend/scraper/_shared/postings.py`: derives ATS-specific `posting_key` from Greenhouse/Lever/Ashby/Workday and other URL shapes.
- `backend/scraper/_shared/posting_links.py`: links duplicates with `duplicate_of` and `copy_kind` (link, city, repost) while preserving user actions; heuristic text matching requires evidence.
- `backend/scraper/_shared/same_role.py`: conservative long-description equivalence check and boilerplate template guard.

**Matching and automation:** `backend/analyzer/cv_scorer.py` sends resume/job text to an LLM with dynamic resume selection, caching and concurrency gating. `backend/scheduler.py` manages per-account/installation tasks with defensive configuration and a scheduler-disabled switch.

**Reuse potential:** High for *algorithms and tests* around posting identity, metadata preservation, source aliases, and role comparison. Medium to high engineering cost for importing its tightly coupled SQLAlchemy event listeners, account context and database model.

**Caution:** More subsystems and accounts increase maintenance. Live scraper success and actual ranking quality not established.

## 2. ApplyPack — strongest fact-based scoring and source-health reference

**Stack:** TypeScript/Node, Hono, Prisma, embedded/self-hosted PostgreSQL, background worker and dashboard as separate processes (`ARCHITECTURE.md`).

**Discovery:** `src/fetchers/` contains Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Rippling, Recruitee, Teamtailor and aggregator adapters; source selection, partial-refresh and monitoring are explicit.

**Matching:**
- `src/filter.ts`: pure deterministic per-search role/keyword/location gate, bounded keyword tokenization and explicit rejection reasons.
- `src/classifier-prefilter.ts`: short optional AI relevance gate before full classification, deliberately fail-open on uncertain/error cases. Its stated 30–40% savings is a code comment, not independently measured here.
- `src/classifier.ts`: model outputs *structured facts* per active profile; schema validated before persistence; model-call results recorded.
- `src/fit-score.ts`: deterministic arithmetic from extracted facts, explicit ceilings for no-stack/role/seniority/excluded conditions, stored facts support rescore without repeat model calls.
- `src/fingerprint.ts`: 64-bit SimHash of long job descriptions; links near-identical cross-listings but avoids assuming same-company descriptions are equivalent.
- `src/fetchers/source-health.ts`: classifies ok, empty, not-modified, missing source, authentication, rate limit, server, network, bad payload and more.

**Reuse potential:** Highest for the *design pattern* of evidence facts -> deterministic verdict, per-stage funnel counters, and source-health states. Direct TypeScript code copying into a Python backend is unattractive; a clean Python implementation with own tests is preferable.

**Caution:** Many fetcher adapters and features increase scope. Cloud AI cost, actual accuracy, and uptime remain unverified.

## 3. JobSync — strongest tracker/UX and cost-aware pre-rank reference

**Stack:** Next.js 16, React 19, Prisma/PostgreSQL, Vitest, Playwright E2E, optional Ollama/cloud AI. Self-hosted Docker is the documented primary deployment.

**Discovery — narrower, targeted ATS registry:** `src/lib/scraper/ats/registry.ts` explicitly wires **Greenhouse, Lever and Ashby** for automated discovery. README documents large built-in company directories; this is different from unrestricted open-web discovery.

**Pipeline:**
- `src/lib/scraper/utils.ts`: canonical URL for storage and dedup, metadata fallback if URL missing.
- `src/lib/jobs/jobDedupe.ts`: per-user saved-job dedup key map, normal URL fast path, canonical fallback.
- `src/lib/scraper/ats/rank.ts`: deterministic IDF-weighted title/skill term scoring with lexical boundaries, optional strict-location filtering; explicit component breakdown.
- `src/lib/scraper/ats/pipeline.ts`: location gate -> relevance floor -> score threshold -> cap -> top K for LLM; remainder optionally saved un-analyzed.
- `src/lib/scraper/automation-run/atsRun.ts`: actual staged automation flow, board-failure reporting, funnel counters, state handling and AI matches.
- `src/lib/scraper/runner.ts`: atomic database constraint prevents concurrent runs of the same automation; cancellation propagates and is checked in DB.
- `src/lib/aiUsage/tracker.ts`: records feature/provider/model, tokens, time and failure state per AI call.

**UX:** Application tracker, interviews, interview timeline, contacts, tasks, resume editor and docked AI assistant. Good reference for task-detail screens, backup/restore, cost visibility, and explicit manual confirmation of imported job postings. The breadth could undermine SignalRank's five-minute shortlist objective if adopted wholesale.

**Limitations:** Only three ATS providers in the observed automated registry; a cheap lexical pre-rank can miss relevant postings with synonyms; not a drop-in replacement for SignalRank semantic ranking. The README's privacy positioning requires qualification: optional cloud-model use sends selected user data to configured providers.

**Reuse potential:** High for explicit funnel instrumentation, bounded top-K analysis, atomic run claims, cancellation, cost telemetry and tracker interactions. **Medium** for actual code because of the Next.js/Prisma architecture.

## 4. CareerPulse — strong isolated-failure scraping patterns, weaker identity semantics

**Stack:** Python >=3.12, FastAPI, aiosqlite/SQLite WAL, optional `sqlite-vec`, httpx, APScheduler, Anthropic/OpenAI clients; `app/scrapers/` has many source modules.

**Discovery/operations:**
- `app/scrapers/base.py`: per-domain rate limits; retry on 429 and 5xx, bounded exponential delay, HTTP validation, salary sanity bounds and rotating browser-like user agents.
- `app/scheduler.py`: per-source 120-second timeout, failure circuit breaker, progress heartbeats, warning on consecutive empty runs, stage-separated scrape/enrichment/location/digest cycles.
- `app/database.py`: SQLite jobs, job sources, scores, application status, search config, enrichment and history.

**Ranking:** `app/matcher.py` uses an LLM prompt to judge role (30%), core skills (30%), seniority (20%) and logistics (20%) and requests a cap of 50 on wrong-role matches. `batch_score` calls `score_job` sequentially; the numerical cap is in the prompt rather than a verified post-processing code gate. This is less reproducible than arithmetic over extracted facts.

**Dedup risk:** `app/database.py:find_cross_source_dupes` compares normalized company plus title-token overlap >=0.7, then `app/scheduler.py` dismisses the newly inserted row and merges the source. Distinct openings with similar titles may be collapsed; add a precise ATS identity/description check before copying this design. Also note per-row database lookups in the scrape cycle could be costly at scale; performance not measured.

**Maintenance:** Last observed commit 2026-04-15, older than the main peers. This is a maintenance signal, *not* proof of defects.

**Reuse potential:** Medium for bounded source timeouts, circuit breakers, freshness telemetry and uncertain-location fail-open handling; **low for full replacement** because its matching and dedup algorithms do not obviously improve on the June SignalRank branch.

## 5. JobSpy and JobSentinel — secondary modules only

- **JobSpy:** `pyproject.toml` declares version 1.4.1 and MIT license; built-in boards include LinkedIn, Indeed, Glassdoor, Naukri etc. June SignalRank already depends on `python-jobspy>=1.1.0` and uses `batch/sources/jobspy_source.py`. Evaluate source health, lockfile, local scrape failure behavior and Indian coverage; do not duplicate the integration.
- **JobSentinel:** MIT-licensed Rust/Tauri desktop project with Rust crates for scrapers, scheduler, scoring, persistence and notifications. Useful patterns for desktop startup and isolation, but translating Rust modules to the existing Python backend is high effort. Read `crates/jobsentinel-application/src/scoring/` and `scheduler/` selectively if needed.

## Preliminary conclusions

1. **Do not replace June SignalRank yet.** It already has semantic matching, intent gates, direct ATS discovery, durability and availability logic.
2. **First candidate POC:** posting identity (JobNavigator) plus optional evidence-based cross-listing (ApplyPack).
3. **Second POC:** extracted requirements and deterministic fit ceilings (ApplyPack), while keeping local semantic matching (SignalRank).
4. **Third POC:** instrumented source health + run funnel (JobSync + CareerPulse + ApplyPack).
5. **UX study:** JobSync's tracker interactions, not its entire CRM platform.

**Evidence level:** Code presence and design verified; correctness, ranking superiority, uptime, actual screenshots and real data benchmarks NOT VERIFIED.
