# SignalRank — Documentation and Research

This index is for **`feature/june-06-backend-hardening`**; the public `main` branch remains separate.

## Where to start

| Document | Purpose |
|---|---|
| [June 6 development roadmap](../signalrank/docs/JUNE_06_ROADMAP.md) | Prioritized P0–P3 plan, acceptance criteria and remaining verification |
| [Backend fixes and test evidence](../signalrank/docs/JUNE_06_BACKPORTS.md) | Implemented changes, test results and limitations |
| [Product specification](../signalrank/docs/spec.md) | Canonical boundaries; some vocabulary predates the new inbox |
| [June source baseline](benchmark/01-signalrank-baseline.md) | Historical committed code snapshot at `97adf1b` |
| [Competitor code review](benchmark/02-competitor-review.md) | JobNavigator, ApplyPack, JobSync, CareerPulse, JobSpy, JobSentinel |
| [Evidence-based feature matrix](benchmark/03-feature-matrix.md) | Source-coded comparisons, not measured rankings |
| [Benchmark protocol and results ledger](benchmark/04-benchmark-results.md) | Reproducible methodology; real results are **NOT RUN** |
| [Reuse versus replace decision](benchmark/05-reuse-vs-replace.md) | Provisional architecture decision and candidate proof-of-concepts |
| [Benchmark-led implementation roadmap](benchmark/06-roadmap.md) | Engineering waves, backlogs and acceptance gates |

## Offline benchmark fixtures

- [Synthetic job-set generator](benchmark/fixtures/generate_jobset.py) makes a deterministic fictional candidate profile and 150 synthetic postings, with reference labels.
- [Predictions evaluator](benchmark/fixtures/evaluate_predictions.py) computes contract-test precision@10 and nDCG@10 on synthetic labels. These are **not** estimates of real-world matching performance.

Generate the fixtures locally (the outputs are intentionally not checked in):

```bash
python3 docs/benchmark/fixtures/generate_jobset.py
python3 docs/benchmark/fixtures/evaluate_predictions.py --pred /path/to/synthetic-predictions.jsonl
```

The evaluator requires a separately generated predictions file.

## Provenance and important limits

- Benchmark research was pinned to June branch commit **`97adf1b`** before the inbox/tracker improvements committed as **`6a1e171`**. Do not mistake this older audit for a description of the current working tree.
- Competitor conclusions are **source-only**. No live competitor application runs, comparable scoring benchmark, real browser screenshots, source freshness testing or measured AI cost results are claimed.
- Run PostgreSQL/pgvector migrations and browser workflows on disposable test data before production deployment. Do not commit secrets, resumes or user job records.
