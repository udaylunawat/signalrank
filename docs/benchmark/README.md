# SignalRank competitor benchmark — June backend hardening

Prepared 2026-11-17. This directory contains a **static code-level architecture audit** of the June 06 SignalRank feature branch against JobNavigator, ApplyPack, JobSync, CareerPulse, JobSpy and JobSentinel.

**Analyzed commit:** `97adf1b5930a02b70ed56ea1872ab75071b0dbee` on `feature/june-06-backend-hardening`. The branch later advanced independently to `6a1e171` with inbox/tracker work; that later implementation was not browser-tested as part of this research.

## Documents

1. [SignalRank baseline](01-signalrank-baseline.md)
2. [Competitor source review](02-competitor-review.md)
3. [Feature comparison matrix](03-feature-matrix.md)
4. [Benchmark protocol and result ledger](04-benchmark-results.md)
5. [Reuse versus replace decision](05-reuse-vs-replace.md)
6. [Prioritized development roadmap](06-roadmap.md)
7. [Offline POC 1 — ATS posting identity and synthetic comparison](poc/README.md)

## Evidence and limitations

Repository code, package manifests, selected test files and source structure were inspected. **No competitor application or the local SignalRank web UI was started in a browser, and no live jobs or actual applicant records were used.** Result cells remain `NOT RUN` pending independently verified runtime tests. Screenshots from existing READMEs are not substituted for real browser screenshots.

**Provisional recommendation:** Retain SignalRank and selectively adapt ATS-aware job identity, deterministic scoring explanations, source-health classification and simple daily-use interactions. Re-evaluate once live discovery, ranking relevance and browser UX benchmarks are available.

## Offline synthetic fixture

```sh
python3 docs/benchmark/fixtures/generate_jobset.py
python3 docs/benchmark/fixtures/evaluate_predictions.py --pred /path/to/predictions.jsonl
```

The fixture contains **150 fictional listings representing 120 separate requisitions**, including 30 deliberate cross-source aliases. It uses fictional profile data, `example.invalid` URLs and mock HTTP statuses; it never calls the network. Synthetic labels validate invariants, **not** real relevance, source freshness, application success or actual link availability. See document 04 for the separately labeled real-job benchmark protocol.

## Safety

Use isolated worktrees from `feature/june-06-backend-hardening` for POCs, with disposable databases and test credentials. Never change user data, use private resumes or accounts, send applications, switch branches, merge into `main`, or overwrite other threads' concurrent work for this benchmark.
