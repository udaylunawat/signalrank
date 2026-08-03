# Primary-lane benchmark

This folder records the phased, repeatable evaluation of SignalRank's primary-lane ordering against the previous score-only ordering.

The benchmark uses 70 PII-free resumes across seven role families. The query matrix is test-only and does not create a product role catalog. It collects a live catalog once, freezes it in an isolated local database, then applies both ordering policies to the same candidate/job scores.

| Phase | Artifact | Purpose |
| --- | --- | --- |
| 1 | `phase-1-query-matrix.md` | Search terms, locations, and scope |
| 2 | `phase-2-catalog-collection.md` | Source telemetry and frozen-catalog assessment |
| 3 | `phase-3-ranking-ab.md` | Pre-fix versus post-fix lane metrics |
| 4 | `phase-4-assessment.md` | Outcome, limitations, and follow-up actions |

The runner is `signalrank/backend/scripts/run_primary_lane_benchmark.py`. It keeps raw jobs, embeddings, and resumes in a disposable scratch directory; only the Markdown assessments are written here.
