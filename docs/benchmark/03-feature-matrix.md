# 03 — Evidence-backed feature matrix

**Review:** 2026-11-17. **SignalRank baseline:** June branch `97adf1b`, committed tree only. This matrix records *implementation evidence*, not real-world success. No browser tests, live jobs or AI calls were used.

**Legend:** `S` = source-code implementation identified; `D` = documentation-only claim; `P` = partial/limited design; `?` = not checked; `N` = not found in the reviewed scope. All `S` cells still require runtime validation.

| Area | SignalRank June | JobNavigator | ApplyPack | JobSync | CareerPulse |
|---|---|---|---|---|---|
| LinkedIn/Indeed discovery | S JobSpy | S JobSpy | P feed/ATS approach | N in ATS registry | S scraper modules |
| Greenhouse/Lever/Ashby discovery | S direct ATS | S | S | S three registries | P Greenhouse |
| Workday and other ATS | S Workday/direct ATS | S multi-ATS | S multi-ATS | N in registry | P some sources |
| Free remote-job APIs | S | S some aggregators | S | N in registry | S |
| Configurable search locations | S | S | S | S | S |
| Source retries, timeout, failure isolation | S source/worker modules | S | S | S board-specific | S |
| Source health reason taxonomy | P logs/telemetry; validate categories | S scraper health | S detailed taxonomy | S board error/status | S breaker/zero-run/timeout |
| URL normalization | S | S identity-aware | S | S | S simple canonical hash |
| ATS-level posting identity | P URL-based, not general posting-key parser | S dedicated canonical posting keys | P source IDs | P URL-based key | P URL+metadata |
| Cross-source near-duplicate evidence | P title/company/location dedup | S keyed/link/content | S cross-listing SimHash | P URL/meta | P fuzzy company/title |
| Preserve separate requisitions with same title | **Risk:** later display dedup may hide them | S designed guard | S cross-listing is annotation | P URL distinction | **Risk:** fuzzy merge |
| Semantic resume-to-JD embeddings | S | P LLM scoring focus | P fact-based classifier | P lexical pre-rank + LLM | P optional embedding; LLM matcher |
| Role-family / hard mismatch handling | S intent matching | S LLM scorer | S deterministic ceilings | S pre-rank and AI | D prompt cap |
| Deterministic fit score | S | P model-led | S arithmetic from facts | S pre-rank (not final match) | P prompt-led |
| Per-job explanation | S | S | S | S | S |
| Re-score without further model calls | P deterministic baseline/caches | P cached LLM | S stored facts | P lexical stage | ? |
| Multiple resumes/profile matching | P profile pipeline; inspect UX | S | S multiple searches | S resume choice | P |
| Saved/applied/interview tracker | S | S | S | S extensive | S |
| Interview timelines/tasks/contacts | S recruiter/tracker subset | S | P | S extensive | S |
| Resume/PDF tailoring | S | S | S | S | S |
| Scheduled/background discovery | S durable worker | S APScheduler | S worker/cron | S scheduled automations | S APScheduler |
| Durable claim/lock | S lease/runs | S scheduler context | S fetch locks | S DB unique active run | P breaker/stages |
| Explicit AI call/cost telemetry | P LLM cache/logs; verify token/cost fields | S logs | S AI ledger/spend | S token, time, feature | P provider configuration |
| Fully local AI option | S local embeddings; LLM optional | P provider dependent | P provider dependent | S Ollama | P provider dependent |
| Self-hosted data | S Postgres local deployment | S | S | S | S SQLite |
| Actual UX completion time | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Real browser screenshots verified here | NO | NO | NO | NO | NO |
| Real-world discovery coverage measured | NO | NO | NO | NO | NO |

## Important comparisons and boundaries

### Discovery coverage is not equivalent to useful coverage

A source adapter's existence does not prove source success, useful India coverage, fresh openings, or working external links. Source discovery must be benchmarked separately from the same-input ranking test. JobSync's observed **automated ATS registry contains only Greenhouse, Lever and Ashby**; its broader feature-rich tracker does not imply broader discovery.

### Dedup correctness is not just duplicate rate

Measure **false merges of different requisitions** as well as repeated exposure of the same posting. June SignalRank drops company/title-based matches after ranking; JobNavigator retains link/city/repost relationships; ApplyPack conservatively marks cross-listings without destructive merging.

### Score numbers are not directly comparable

SignalRank score, ApplyPack `fit_score`, JobSync pre-rank and CareerPulse LLM score are different scales and stages. On identical fixed inputs, compare **rank order and decisions** (P@10, nDCG@10, hard-mismatch false positives, calibration) rather than asserting a 90 in one app equals a 90 in another.

### Privacy needs runtime configuration evidence

All six products may use external AI or scraped job services. Local storage does not by itself mean resume text never leaves the machine. Measure outbound requests and provider settings in disposable test environments. Do not use private resumes or authentic user accounts.

## Specific code references

- SignalRank June: `signalrank/backend/batch/scrape_pipeline.py`, `batch/ranker.py`, `domain/intent_matching.py`, `batch/job_availability.py`, `batch/worker.py`.
- JobNavigator: [dedup](https://github.com/vesaias/JobNavigator/blob/main/backend/scraper/_shared/dedup.py), [posting links](https://github.com/vesaias/JobNavigator/blob/main/backend/scraper/_shared/posting_links.py), [scorer](https://github.com/vesaias/JobNavigator/blob/main/backend/analyzer/cv_scorer.py).
- ApplyPack: [filter](https://github.com/applypack/applypack/blob/main/src/filter.ts), [fit score](https://github.com/applypack/applypack/blob/main/src/fit-score.ts), [fingerprints](https://github.com/applypack/applypack/blob/main/src/fingerprint.ts), [health](https://github.com/applypack/applypack/blob/main/src/fetchers/source-health.ts).
- JobSync: [registry](https://github.com/Gsync/jobsync/blob/main/src/lib/scraper/ats/registry.ts), [pre-rank](https://github.com/Gsync/jobsync/blob/main/src/lib/scraper/ats/rank.ts), [pipeline](https://github.com/Gsync/jobsync/blob/main/src/lib/scraper/ats/pipeline.ts), [AI usage](https://github.com/Gsync/jobsync/blob/main/src/lib/aiUsage/tracker.ts).
- CareerPulse: [scraper base](https://github.com/tcpsyn/CareerPulse/blob/main/app/scrapers/base.py), [scheduler](https://github.com/tcpsyn/CareerPulse/blob/main/app/scheduler.py), [database/dedup](https://github.com/tcpsyn/CareerPulse/blob/main/app/database.py), [matcher](https://github.com/tcpsyn/CareerPulse/blob/main/app/matcher.py).
