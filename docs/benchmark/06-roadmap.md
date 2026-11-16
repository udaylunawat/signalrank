# 06 — Prioritized implementation roadmap

**Prepared:** 2026-11-17. **Only target branch:** `feature/june-06-backend-hardening`. **Static evaluation baseline:** `97adf1b`; branch subsequently advanced to `6a1e171` with a separate inbox/tracker implementation. **Do not overwrite that work.**

**North-star outcome:** A candidate can review the ten highest-quality *new, non-duplicate and eligible* openings and save/apply/dismiss appropriately in approximately five minutes. This is a proposed target, not a measured achievement. Optimize decision quality, clarity and reliability—not quantity of features or UI chrome.

## Non-negotiable guardrails

- Use only an isolated worktree branched from the **current June hardening branch**, never `main`. Refresh the latest feature-branch tip before a POC; do not overwrite or reset the developer's active checkout.
- Never use private resumes, real credentials or production databases. All fixtures must be synthetic. Disable auto-email, external posting, apply or outreach.
- Do not run competitors against real personal accounts. Rate-limit permitted public ATS tests and distinguish blocked from dead sources.
- Benchmark before changing ranking weights or dedup defaults. Keep flags and rollback paths.
- Separate static evidence, synthetic tests and real-browser proof; never claim a screenshot if no real app was running.
- Preserve application history, saved/dismissed decisions and recruitment notes throughout identity migrations.
- Keep no more than four routine top-level app destinations (Matches, Tracker, Inbox if useful, Settings); simplify Overview if users cannot justify it.
- The contemporaneous `signalrank/docs/JUNE_06_ROADMAP.md` may define work by the other development thread; coordinate instead of overwriting it.

## Delivery waves and acceptance gates

### Wave 0 — Reproducibility and baseline (P0; prerequisite)

**Inputs:** `01-signalrank-baseline.md`, `04-benchmark-results.md`, synthetic fixtures.

1. Freeze SHA, test environment, schema revisions, sample data and model settings.
2. Run non-live backend unit tests, database/API tests, frontend typecheck and lint, plus disposable app startup.
3. Populate actual failure counts and CI commands. Take screenshots only from the running application.
4. Run synthetic identity/score invariants. Prepare 200–250 public job snapshots and independent 0–3 relevance labels for a *real* ranking evaluation.

**Acceptance:** Reproducible commands, tests and screenshots indexed by SHA; zero real data; all metric cells not yet tested remain `NOT RUN`; README vs architecture discrepancy resolved.

### Wave 1 — Identity and source provenance (P0)

1. Implement pure identity canonicalization for recognized ATS IDs; leave unknown URLs untouched except safe tracking-parameter cleanup.
2. Introduce `job_source_alias` / `posting_identity` relationships (or equivalent) through an additive backward-compatible migration.
3. Route incoming listings through exact ATS identity first, then non-destructive uncertain duplicate suggestions.
4. Replace final company/title-only **destructive** collapse in ranker with identity-aware grouping or display. Same company/title with distinct ATS requisitions must both survive.
5. Preserve original source URLs, best employer link, different regional eligibility and application history. Use migration shadow mode and feature flag before default switch.

**Acceptance:** Zero false merges in curated adversarial fixture; all known exact-ID aliases converge; data migration reversible, idempotent, with no deleted user state; pairwise duplicate precision >= 0.99 on independently reviewed gold pairs (proposed threshold; measure before production).

### Wave 2 — Trustworthy, explainable ranking (P0)

1. Define versioned `JobFitFacts` and deterministic `score_from_facts`, reusing June intent matching.
2. Keep embedding similarity; add explicit role-family/location/seniority/required-skill evidence and confidence bands.
3. Ensure hard exclusion cannot be canceled out by preferred-company/recency points. Distinguish unknown facts from negative facts.
4. Expose concise 'why matched' and 'watch-outs' strings; store evidence and source references without exposing user resume body.
5. Evaluate against baseline ranking with same frozen job set, no live sources. Shadow-score first; no silent score changes.

**Acceptance:** Deterministic re-score without model calls; no hard-incompatible job in top 10 on adversarial set; target P@10 improvement without >2% nDCG@10 regression on real labeled set (proposed gate); cost and failure telemetry retained.

### Wave 3 — Source resilience, recency, link health (P1)

1. Audit existing source retry/timeout logic; add missing source-health categories and per-source consecutive failure tracking.
2. Bounded retries and backoff; classify 403/429/CAPTCHA as `blocked/unknown`, not expired.
3. Track `first_seen`, `last_seen`, `posted_at`, `last_verified` separately with provenance.
4. Live-check a fixed set of public ATS feeds and board links; prefer actual employer URL, retain source aliases.
5. Add optional daily digest / 'new good matches' notification only after the match quality is adequate.

**Acceptance:** One failing source does not fail a full run; source-specific errors visible without logs; no falsely expired links in the controlled dead-link fixture; freshness and recovery measures reported.

### Wave 4 — Five-minute daily-use UX (P1)

1. Compare current June inbox/tracker/dashboard implementation against the actual five user tasks in `04-benchmark-results.md`.
2. Default to **new matches**, sorted by relevance and freshness. Surface 'Why', 'Concern', location/work mode, source date and employer link in the card.
3. One clear decision row: **Open, Save, Dismiss, Applied**; action completes without leaving the feed except when intentional.
4. Preserve filters, scroll state, reviewed status and inbox state. Explain 0 results truthfully ('nothing new' versus 'sources failed' versus 'all filtered').
5. Simplify navigation and settings before adding advanced analytics, a chatbot, new CRM-style screens or auto-apply.

**Acceptance:** Median review of 10 jobs <= 300 seconds using the actual browser and synthetic persona, <= 2 UI interactions for one decision, no loss of state, accessibility and keyboard paths checked. This is a *target*, not a reported result.

### Wave 5 — Quality engineering and optional expansion (P2)

1. Add adversarial source, ranking, identity and privacy tests to CI.
2. Measure cost per 100 useful postings and use bounded AI verification on uncertain/high-value results only.
3. Add individual ATS source integrations only if demonstrated *incremental* relevant India-focused yield.
4. Examine JobSync's backup/restore, interview timeline and AI usage details only where actual usage validates them.
5. Document data migration, rollback, opt-in cloud AI use, non-blocking health reporting and disaster recovery.

**Acceptance:** Benchmark gates preserved, costs visible, migrations and export tested, no new feature without a measured daily-use benefit.

## Concrete backlog (assign owners later)

| ID | Priority | Area | Work | Evidence source | Gate |
|---|---|---|---|---|---|
| SR-BENCH-01 | P0 | Baseline | Pin/reproduce June test and startup environment | June code | Suite and real screenshots |
| SR-BENCH-02 | P0 | Data | Curate 200–250 adjudicated relevant job snapshots | Shared gold protocol | Reproducible evaluation |
| SR-ID-01 | P0 | Identity | Canonical ATS requisition identity + URL aliases | JobNavigator | Exact-ID fixtures |
| SR-ID-02 | P0 | Identity | Remove company/title-only destructive matching | June ranker | Zero false merges fixture |
| SR-SCORE-01 | P0 | Matching | Job facts + hard-mismatch decision and reason codes | ApplyPack, June intent scoring | Fixed-input quality |
| SR-SCORE-02 | P0 | Matching | Shadow-score benchmark, no duplicate AI spend | June cache + ApplyPack | Determinism/cost |
| SR-SRC-01 | P1 | Discovery | Source health classification and retry metrics | CareerPulse, ApplyPack | Fault injection |
| SR-SRC-02 | P1 | Discovery | Link freshness and employer-link reliability | June availability, JobNavigator | Human-reviewed status |
| SR-UX-01 | P1 | UX | Matches-first feed, persistent filters, decisions | JobSync; June inbox | Timed browser tasks |
| SR-OPS-01 | P1 | Operations | Run funnel counts and model cost ledger | JobSync | Auditable by stage |
| SR-UX-02 | P2 | UX | Lean notification digest | JobNavigator, CareerPulse | Relevance + opt-in |
| SR-MAINT-01 | P2 | Maintenance | Lock source dependencies, privacy docs, backup tests | All | CI + recovery |

## Suggested POC contract

Work only in a **new disposable worktree from the June feature branch**. Each POC must have:
- A one-page hypothesis and baseline measurement.
- A minimal pure module or feature-flagged integration and its tests.
- Named synthetic fixture inputs and expected invariants.
- Before/after comparison on the **same** inputs, source SHA and runtime version.
- A single decision: `ADOPT`, `ITERATE`, or `REJECT` with numeric justification.
- No production migration, no sending resumes/alerts and no automatic merges.

## Definition of done for the broader benchmark

The six documents, synthetic fixture generator and ranking evaluator alone are **not** a finished competitive benchmark. The complete effort additionally requires:
- Independent live-app startup and verified browser screenshots.
- Independent real-labeled job ranking results.
- Controlled source coverage, freshness and link health measurements.
- Privacy/AI cost inspection.
- At least one isolated, runnable identity POC and one scoring POC.
- Documented final architecture choice supported by measured outcomes.

Until these are complete, the decision remains **provisional hybrid/retain**.
