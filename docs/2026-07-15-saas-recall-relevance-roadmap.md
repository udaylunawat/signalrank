# SignalRank SaaS: Recall, Relevance, and Robustness Roadmap

## Product objective

SignalRank should reliably surface every high-value role available through its healthy sources, rank the best opportunities first, and tell the user when coverage is degraded.

“Never miss a job” is implemented as measurable service levels rather than an absolute promise:

- Recall@100 >= 95% on a maintained must-show evaluation set.
- Precision@20 >= 80% and nDCG@20 >= 0.85.
- At least four healthy discovery sources per daily cycle.
- A single-source outage reduces unique new-job yield by less than 20%.
- No source or query failure is reported as a fully fresh successful run.
- New high-value roles are discoverable within six hours at P95.
- Top-50 cross-source duplicate rate and dead-link rate remain below 2%.

## What the prior version had that the SaaS port missed

| Capability | Prior version | SaaS gap | Decision |
| --- | --- | --- | --- |
| Multi-source discovery | JobSpy/Indeed, Google via SerpAPI, Himalayas, Remotive, Jobicy, optional RapidAPI | JobSpy and Remotive only, with no per-source contract | Restore now |
| JobSpy resilience | Serialized Indeed, delay, retry, per-query isolation | Combined Indeed/LinkedIn calls with no source telemetry | Restore now |
| Raw discovery safety net | “All Discovered Jobs” view before ranking gates | Only ranked results are visible | Restore as “Broader matches” |
| Run observability | Run history and standalone source probes | Latest run only; no source counts or errors | Restore now |
| Freshness controls | Incremental scrape decisions and date windows | Historical rows remain eligible forever | Restore now |
| Semantic exploration | Resume similarity and overlap explanation | Score chips without an explanation | Restore in simplified form |
| Description enrichment | Public-page enrichment for incomplete LinkedIn jobs | No completeness repair | Add after source coverage |
| Rich tracker | Dates, notes, offers, recruiter contacts, analytics | Basic status columns | Add selectively later |
| Resume tailoring | Not central to discovery; SaaS backend already supports it | No frontend workflow | Add after discovery quality |

## Phase 0: Make refresh honest and dependable

Target: 1–2 engineering days.

### Backend

1. Add durable run execution:
   - Replace the process-local queue with DB leasing or a managed worker queue.
   - Recover stale `pending` and `running` runs after restart.
   - Coalesce duplicate refresh requests per user.
   - Add heartbeat, timeout, retry count, stage, and failure reason.
2. Add source-run telemetry:
   - Persist provider, query, location, attempted time, latency, raw count, normalized count, deduped count, error, and cache age.
   - Support `success`, `partial`, and `failed` terminal states.
   - A run is `partial` if a required provider fails and cached data is used.
3. Harden JobSpy:
   - Run Indeed and LinkedIn independently.
   - Serialize Indeed queries with a three-second delay and bounded retry/backoff.
   - Preserve results from successful queries when another query fails.
4. Fix the preference contract:
   - Use one typed schema shared by onboarding, profile settings, query planning, and ranking.
   - Resolve `multi_select` versus `multiselect`.
   - Pass preferred locations to discovery.
   - Map company preferences to the configuration read by `CompanyScorer`.
   - Remove any preference that has no tested product effect.

### Frontend

1. Poll or stream run progress until terminal state.
2. Show stages: planning queries, searching sources, deduplicating, ranking.
3. Disable or coalesce duplicate refresh clicks.
4. Reload metrics and results automatically on completion.
5. Distinguish fresh, partial, cached, stale, and failed results.
6. Move search, score filters, and sorting to the API so they operate across all pages.

### Acceptance criteria

- Restarting the backend during a refresh does not orphan the run.
- A failed Indeed search can produce a visible partial run from other sources.
- The UI states exactly which sources succeeded, failed, or used cached data.
- A page-two role is returned by search and participates in global sorting.
- Every onboarding answer has a contract test proving its downstream effect.

## Phase 1: Restore high-recall discovery

Target: 3–5 engineering days.

1. Add a deterministic query planner:
   - Generate 10–15 bounded variants from target roles, resume skills, role taxonomy, and adjacent titles.
   - Search preferred cities, India-wide, and remote/APAC lanes.
   - Track yield per query and retire persistently unproductive variants.
2. Restore independent provider adapters:
   - JobSpy Indeed and LinkedIn.
   - Remotive, Himalayas, and Jobicy.
   - Google Jobs through SerpAPI when configured.
   - Keep RapidAPI optional until its cost and reliability justify it.
3. Separate catalog refresh from user ranking:
   - Refresh a shared catalog incrementally on a schedule.
   - Rank the existing fresh catalog immediately for each user.
   - Use overlapping time windows to avoid boundary misses.
4. Preserve provenance and freshness:
   - Store canonical URL, content fingerprint, first seen, last seen, last verified, active state, and every provider sighting.
   - Canonically deduplicate across sources without losing alternative apply URLs.
5. Add a recall safety net:
   - Replace the all-token title hard gate with a soft role-fit feature.
   - Keep only explicit user exclusions as hard filters.
   - Add a “Broader matches” lane containing strong semantic near-misses and excluded items with reasons.

### Acceptance criteria

- Gold-set source recall is at least 95%.
- At least four sources return or explicitly report health each day.
- One provider outage does not remove more than 20% of unique new roles.
- Jobs stale for more than 30 days do not appear in the primary top 20.
- Users can inspect broader and excluded roles without silently weakening exclusions.

## Phase 2: Improve precision and user trust

Target: 5–7 engineering days.

1. Use two-stage ranking:
   - High-recall retrieval from query matches, semantic neighbors, and source quotas.
   - Deterministic reranking for role, resume-skill intersection, seniority, location, company, recency, and contract preference.
2. Correct scoring semantics:
   - Compute actual resume-to-job skill intersection rather than counting skills in the job description.
   - Restore useful deterministic role caps from the prior ranker.
   - Do not call scores percentages until calibrated on labeled examples.
3. Build a relevance evaluation set:
   - Start with 150–300 labeled roles, including must-show jobs and deliberate counterexamples.
   - Capture `relevant`, `not relevant`, `hide company`, `wrong location`, and `wrong seniority` feedback.
   - Track Recall@100, Precision@20, nDCG@20, and irrelevant-dismiss rate on every ranking change.
4. Explain every recommendation:
   - Show matched skills, role fit, location, freshness, and important concerns.
   - Make score dimensions understandable and actionable.
5. Add editable preferences:
   - Let users review parsed resume data and change roles, locations, compensation, exclusions, and company preferences.
   - Preview how a preference change affects results before applying it.

### Acceptance criteria

- Recall@100 >= 95%, Precision@20 >= 80%, and nDCG@20 >= 0.85.
- Irrelevant-dismiss rate is below 10% for the top 20.
- Every top result has a concise explanation and source/freshness provenance.
- Feedback changes later ranking without hiding jobs globally or irreversibly.

## Phase 3: Ensure users see new high-value jobs

Target: 3–5 engineering days.

1. Schedule catalog refreshes independently of browser sessions.
2. Add `new since last viewed`, `seen`, `saved`, `dismissed`, and `notified` state.
3. Start with an in-app new-match inbox and a deduplicated daily email digest.
4. Add optional instant alerts only for calibrated high-value matches.
5. Revalidate top apply links and demote expired jobs before notification.
6. Add anomaly alerts when a provider’s yield drops more than 50% from its seven-run median.

### Acceptance criteria

- P95 discovery-to-user visibility is under six hours.
- The same job is not notified twice after cross-source deduplication.
- Delivery failures retry and remain visible in a delivery log.
- Dead links are below 2% in notified and top-20 roles.

## Phase 4: Conversion features

Add only after discovery and ranking SLOs are stable:

1. Idempotent saved-job state and richer tracker cards with apply URL, score, source, and freshness.
2. Notes, next action, reminders, applied/interview dates, and offer compensation.
3. Frontend for the existing tailored-resume backend.
4. Recruiter discovery and contact workflow, with verified-contact quality gates.

## Explicitly defer

- Gmail job-alert ingestion: the prior implementation produced unreliable apply links.
- Per-job LLM veto: too expensive and risky as a hard relevance gate.
- AI config advisor: labeled feedback and evaluation provide higher-value learning.
- Large analytics dashboards: source health, freshness, and match explanations matter first.
- CSV/report artifacts: useful internally, not core SaaS UX.

## Required test layers

1. Provider contract tests with recorded representative payloads.
2. Live source probes outside the normal unit suite.
3. Worker restart, lease expiry, retry, partial failure, and idempotency tests.
4. Query-planner and preference-contract tests.
5. Canonical and fuzzy cross-source deduplication tests.
6. Ranking regression tests against the labeled relevance set.
7. Browser tests for refresh progress, partial failure, new-match state, filters, save/dismiss, and expired sessions.
