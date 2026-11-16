# 04 — Benchmark protocol and results ledger

**Base revision:** SignalRank June `97adf1b`. **State:** Static benchmark specification and synthetic fixture preparation only. **No comparative runtime measurements have been performed.**

## Scoreboard — intentionally blank

| Test | SignalRank June | JobNavigator | ApplyPack | JobSync | CareerPulse |
|---|---|---|---|---|---|
| Fixed-input P@10 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Fixed-input nDCG@10 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| False-positive hard mismatch @10 | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Duplicate recall/false merge | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Live-source coverage | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| 7-/14-/30-day freshness | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Dead employer links | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| AI cost / 100 accepted jobs | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| 5-minute UX workflow | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Resilience under source/model errors | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

Never populate this table from README statements, Github stars, simulated scores or screenshots of mocked apps.

## A. Fixed-input ranking benchmark (systems comparable on identical inputs)

1. Generate the offline **synthetic** job set using `fixtures/generate_jobset.py`: `python3 docs/benchmark/fixtures/generate_jobset.py`. It writes `jobs-public.jsonl`, `gold.jsonl`, and `profile.json` to `docs/benchmark/fixtures/`. Records use `example.invalid`, and no network request should be made.
2. The generated fixture is **not a real relevance accuracy benchmark**. It is an adversarial contract test for missing descriptions, same-title distinct requisitions, cross-source aliases, remote/location mismatch, expired listings and role-name collisions. Treat the labels as assertions for those synthetic scenarios.
3. For a *real* accuracy estimate, curate **200–250 real publicly accessible jobs** sampled with a reproducible date/region/source policy, freeze title, description, location, employer link and source metadata under permitted use, remove any personal data, and have two independent reviewers grade each for a public synthetic candidate profile. Adjudicate disagreements. Record sampling strata, annotation guide, reviewer agreement and random seed.
4. Freeze each system's code revision, candidate profile, allowed AI provider/model, inference temperature where applicable, prompt versions, and ranking parameters. Feed the **same** posting snapshots. Disable live sourcing and external links for this test.
5. Metrics: precision@10 (relevance >= 2 and eligible/active), nDCG@10 with graded relevance 0–3, false hard-mismatch@10, recall@20, score-versus-judgment calibration, and rank stability across at least three runs when model stochasticity is involved.
6. Some systems do not expose comparable offline ranking interfaces. Implement an adapter that accepts JSONL jobs and produces `{"job_id":"...","score":...,"rank":...}` results. Record missing capability as NOT COMPARABLE, not zero.

## B. Deduplication benchmark (must penalize false merges)

Use identities from known ATS requisitions, plus hand-reviewed equivalence decisions; include:
- Same posting via board, ATS and short-link URLs.
- Indeed `jk`, LinkedIn `currentJobId` and ATS query parameters that are posting identifiers.
- Same company and *exact same title* but **different** requisition IDs and descriptions.
- One role advertised for several cities, separate region restrictions, reposted/expired/reopened jobs.
- Common boilerplate with different duties, skills or experience requirements.

Report pairwise duplicate precision/recall/F1 and **false merges per 100 genuinely distinct jobs**. Keep URLs, source attribution and user application status even when listings are grouped. The desired objective is high precision on auto-grouping; send uncertain matches to a non-destructive possible-duplicate label.

## C. Live discovery benchmark (separate from fixed-input ranking)

At a scheduled date and target locations, collect a controlled sample from each source using a disposable account if needed, rate limits and robots/TOS compliance. Log query and source config, raw count, successful fetches, fresh unique openings, primary employer links, retriable errors and source latency. Compare across the same query set and geography; do not infer failure from a single blocked scraper run.

Compare **discovery yield per source**, freshness and verified primary job URLs. Never confuse a source-independent ranking win with a live-source coverage win.

## D. Freshness and link health

- Freshness uses `date_posted` where source-verifiable, else label posted date unknown. Keep `first_seen`, `last_seen`, `last_verified` separate.
- Link checking should prefer an ATS API or employer-page semantics. HTTP 200 may display an expired listing; HTTP 403/429 and CAPTCHA do not prove expiry. Record `available`, `expired`, `unknown`, `blocked` with evidence, HTTP code and timestamp.
- False-expiration rate matters more than optimistic dead-link pruning; do not erase jobs or application history.
- Offline synthetic `simulated_link_status` is only an assertion for a mocked HTTP harness, never a real network status.

## E. UX task completion (actual apps only)

With isolated real applications, capture *real browser* screenshots and click/event logs for:
1. New user creates profile and configures role/location.
2. User reviews top 10 new matches; records save/dismiss/apply decisions and sees explanations.
3. User opens an employer posting, then returns and preserves the decision.
4. User finds a previously saved application, updates interview status, and adds a note.
5. User diagnoses a failed scan without reading server logs.

Record median and p90 task seconds over three attempts, clicks, mistakes, dead ends and subjective confidence. Five-minute target is a product hypothesis, not a measured result. Screenshot index must identify project, immutable commit, URL, fixture user, exact task and capture time. **No mock screenshot substitutions.**

## F. Reliability and cost

- Deterministically inject 429/500/timeouts/malformed JSON, duplicate source rows, bad posted dates, missing description, optional AI model failures, worker restarts and duplicate concurrent run triggers.
- Count recovered vs lost jobs, partial run status visibility, retries and database invariants. Use disposable DB only.
- Record token input/output, provider price **as of the run date**, cache hit rate, wall time and total cost per 100 distinct scored postings. Do not assume a free tier is guaranteed.
- Verify external network boundaries with synthetic resumes and no real credentials.

## Benchmark artifact conventions

`fixtures/generate_jobset.py` builds deterministic offline assertions with a fixed date and seed. `fixtures/evaluate_predictions.py` accepts JSONL predictions and gold labels; add external system adapters only in isolated environments. Retain separate artifacts for **synthetic**, **real labeled fixed input**, **live source**, **UX**, and **fault-injection** results, each with commit hashes and parameter logs.

**Pending:** Actual benchmark runs, hand-labeled real set, source connectivity, browser screenshots and POCs require the separate development-environment workflow. No score has been invented.
