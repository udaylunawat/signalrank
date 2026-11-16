# 05 — Reuse vs. replace: architecture decision record

**Date:** 2026-11-17. **Working branch:** `feature/june-06-backend-hardening`. **Analyzed baseline:** `97adf1b` (committed tree). A later June inbox/tracker commit (`6a1e171`) landed independently while the audit was in progress; it has not been runtime-tested as part of this evaluation.

**Decision status: PROVISIONAL.** No competitor was successfully run in a disposable browser or measured on a shared real labeled dataset. This is a code-backed engineering recommendation, not a claim of proven product superiority.

## Recommendation

**Prefer a selective hybrid: retain SignalRank's Python/FastAPI, Postgres/pgvector, local embeddings, user-facing matching, and June workflow; selectively reimplement small proven ideas.** Neither JobSync, CareerPulse, JobNavigator nor ApplyPack currently demonstrates enough *verified* superiority to justify replacing SignalRank's codebase and migrating its user data.

### Architecture alternatives

| Choice | Benefits | Costs / failure modes | Current verdict |
| --- | --- | --- | --- |
| **A. Retain and tune** | Minimal migration and integration risk; existing semantic+intent scoring, sources, tracker | Existing identity shortcuts persist; missing some operational explanations | Better than replacement; insufficient alone |
| **B. Hybrid reuse** | Targeted correctness and UX improvements without adding another backend | Need contracts, tests and migrations; some cross-language ports | **Recommended for gated experiments** |
| **C. Fork JobNavigator** | Rich ATS identity handling and aggressive discovery; Python stack | New app/data model, account/auth, workflows, migrations and product semantics | Not justified before a quantified head-to-head |
| **D. Fork ApplyPack** | Strong fact-scoring and source-health systems | TypeScript rewrite/migration from Python, new DB and UI, cost of large feature surface | Reject for now |
| **E. Fork JobSync** | Mature application tracker, self-hosting, rich test suite, AI usage telemetry | Next.js/Prisma architecture; three ATS providers in current automation registry; full CRM scope | Useful inspiration; not a matching/drop-in replacement |
| **F. Fork CareerPulse** | Python implementation, scraper isolation, SQLite footprint | Weak identity heuristic, prompt-calculated fit, lower observed maintenance cadence | Not justified |
| **G. Adopt JobSentinel subsystem wholesale** | Rust reliability-focused runtime | Rust/Tauri integration, maintenance and dual-system complexity | Not justified; study patterns only |

## Ranked code-reuse candidates

### P0 — Evidence-based canonical posting identity

**Reference:** JobNavigator `backend/scraper/_shared/postings.py`, `posting_links.py`, `same_role.py`; ApplyPack `src/fingerprint.ts`.

**Why:** June SignalRank `batch/scraper.py` dedupes by URL within phases; `scrape_pipeline.py` upserts by URL and uses a company/title/location candidate key; `ranker.py` drops company/title matches after scoring. Different URLs may refer to one opening, while distinct requisitions with the same title may be suppressed.

**Port:** Write an isolated pure-Python `posting_identity.py` with `canonical_posting_key(url, source_metadata)`, `possible_cross_listing(a,b)` and `equivalence_evidence`; store one-to-many URL/source aliases and group identity separately. Prefer explicit ATS IDs first; for unresolved links, use conservative content similarity *as a non-destructive suggestion*. Never drop existing `job_raw` rows or application history during migration. Do not blindly copy a large foreign SQLAlchemy subsystem.

**Proof tests:** Greenhouse token embed/direct link; Indeed `jk`; LinkedIn ID forms; same company+title distinct requisitions; location variants; boilerplate; relative vs full URLs. No false auto-grouping for different requisition keys. Correct copy-kind and provenance. **Complexity:** Medium/high (schema plus ranking and UX). **Expected benefit:** High if benchmark confirms false merges/repeats.

### P0 — Deterministic evidence extraction and score provenance

**Reference:** ApplyPack `src/classifier.ts`, `src/fit-score.ts`; compare with SignalRank `domain/intent_matching.py`, `domain/score_synthesis.py`.

**Why:** SignalRank *already* has deterministic/additive scoring and role-family caps, so an entirely new scorer is unnecessary. We should instead make requirements and model judgments inspectable, stable and versioned, and ensure hard incompatibilities cannot be canceled out by company/prestige scores.

**Port:** Define `JobFitFacts` (role family, seniority, required and preferred skills, work location eligibility, compensation status, unknown fields, evidence excerpts, classifier version) and `score_from_facts` deterministic policy. Preserve the current embedding stage. When facts are unavailable, use the deterministic current baseline with `unknown` flags; do not hallucinate missing requirements or filter unknowns as negatives. Add human-readable reason codes and score-version migration.

**Proof tests:** 20+ domain-crossing synthetic cases, hard location incompatibility, missing required skills, company-bonus cannot override hard exclusion, unknown facts remain neutral, re-score yields same result, no duplicate model charges. **Complexity:** Medium. **Expected benefit:** High for trust, explainability and reproducibility.

### P1 — Source-health state machine

**References:** ApplyPack `src/fetchers/source-health.ts`, CareerPulse `app/scrapers/base.py`, `app/scheduler.py`.

**Port:** In Python, classify source results as `ok/empty/not_modified/rate_limited/auth/blocked/not_found/timeout/network/server/bad_payload/unknown`; track last attempt, last good result, successive failure count, next retry and circuit-breaker state. Already-existing source logging should be retained. Mark CAPTCHA/403/429 as unknown/blocked, never as proof of posting expiry. Bounded retries must respect provider limits and robots/terms.

**Proof tests:** 429 Retry-After, 5xx, invalid JSON, empty successful board, 304, one hung source, failing source must not block others, recovery after cooldown, truthful UI status. **Complexity:** Low/medium. **Expected benefit:** High.

### P1 — Bounded expensive analysis and funnel metrics

**Reference:** JobSync `src/lib/scraper/ats/pipeline.ts`, `rank.ts`, `automation-run/atsRun.ts`, `aiUsage/tracker.ts`.

**Port:** Preserve SignalRank's embeddings and pre-embedding selector; add explicit counters per stage (`raw -> fresh -> identity-grouped -> hard-compatible -> embedded -> ranked -> verified -> shown`). Run optional LLM verification only for high-value or uncertain candidates. Keep per-call token, provider, model, cache hit, cost-estimate and error metadata; never store plaintext resume prompts in ordinary logs.

**Proof tests:** Same fixed-input relevance at lower AI spend, top-K/queue cutoff respects budget, no degradation of recall at 20, cancelled runs stop downstream work, counter sums are consistent. **Complexity:** Medium. **Expected benefit:** Medium/high.

### P1 — Simple tracker and daily review interactions

**Reference:** JobSync tracker, job detail, inbox and backup UI. **Do not** port task management, generic chat agent, question bank or full CRM unless daily-use evidence supports them.

**Port:** From the June branch's existing tracker and new inbox work, measure one-tap decisions, saved filters, explanation readability and restoring the previous scroll position. Prefer reusing current Next.js routes and components over bringing in a second application shell.

**Proof tests:** Review 10 relevant jobs in <= 5 minutes median, at most 2 interactions per decision, no hidden application history, all decisions persist on reload. **Complexity:** Low/medium once app startup exists.

### P2 — Source coverage extension

**References:** JobNavigator source adapters, JobSpy, ApplyPack fetchers.

**Port only after source-yield benchmark:** June already has JobSpy, Google Jobs, free APIs, and multiple direct ATS adapters. Measure live unique relevant openings per source for India before adding one more network dependency. Favor primary ATS feeds, clear source attribution, retries and link freshness.

**Complexity:** Varies by provider. **Expected benefit:** Unknown until live measured.

## Legal, security, maintenance constraints

- June SignalRank `LICENSE`: MIT in its committed tree. JobNavigator, ApplyPack, JobSync, JobSpy and JobSentinel report MIT; CareerPulse has a license file but GitHub automatic recognition was inconclusive at inspection time. Before reuse, inspect exact license *at pinned commit*, notices, bundled dependencies and attribution obligations.
- Source reuse should be accompanied by focused tests and preserved copyright/attribution, not vague 'inspiration' claims where literal code was copied.
- Untrusted job descriptions and external URLs must never control prompts, SQL, filesystem paths or tool execution. Cache prompt versions and handle malformed model replies.
- Browser automation, scraped boards, email integrations and job-apply actions carry account, TOS and data privacy risks. No real user account or resume in benchmarks.
- Local storage isn't sufficient to claim full privacy if OpenRouter or another cloud model receives resume text. Document outbound destinations and opt-in.
- Maintenance risk depends on reproducible pinned dependencies and tests, not GitHub star count. Lock JobSpy to a reproducible compatible release and do not blindly upgrade.
- Do not add framework complexity before quantifying the improvement on the common benchmark.

## Decision gates for a future replacement

A fork/replacement should be considered **only** if it meets *all* the following:
1. Actual competitor running app and top user tasks browser-verified, on disposable data.
2. Higher P@10 or nDCG@10 against independently labeled real fixed-input jobs without unacceptable false hard matches.
3. Better unique relevant India-focused discovery yield and link health under comparable source access.
4. End-to-end migration of jobs, resumes/profile, statuses, history and user decisions works without data loss.
5. Measurably lower total engineering/maintenance effort after adaptation than incremental SignalRank improvement.
6. Acceptable privacy, cost, licenses, accessibility and reliable day-to-day startup.

**Status:** No option presently meets these evidence gates. Retain + small, reversible hybrid experiments.
