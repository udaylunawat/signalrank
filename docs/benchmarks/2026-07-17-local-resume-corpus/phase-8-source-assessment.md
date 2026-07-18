# Phase 8 — Source retrieval assessment

Date: 2026-07-18

## First bounded replay: rejected

The first manifest-driven collector deduplicated verified roles and locations
globally, then rotated locations across roles. That allowed a role from one
profile to be fetched using another profile's location. The result had a high
primary-lane share but poor independently reviewed relevance:

| Measure | Frozen baseline | Global location rotation |
| --- | ---: | ---: |
| Judged precision@5 | 60.0% | 16.7% |
| Judged precision@10 | 45.0% | 18.3% |
| Graded NDCG@10 | 88.9% | 73.2% |
| Primary top-10 share | 88.3% | 96.7% |

The gate rejected the replay. A higher primary share was not treated as an
improvement because it was contradicted by the graded relevance labels.

## Corrected replay: improved, still rejected

The collector now produces exact verified `(target role, preferred location)`
pairs and deduplicates those pairs only. The corrected replay used 20 requests
in four bounded batches and improved relevance, but it did not reach the frozen
baseline:

| Measure | Global location rotation | Exact role-location pairs | Frozen baseline |
| --- | ---: | ---: | ---: |
| Judged precision@5 | 16.7% | 40.0% | 60.0% |
| Judged precision@10 | 18.3% | 26.7% | 45.0% |
| Graded NDCG@10 | 73.2% | 80.1% | 88.9% |
| Primary top-10 share | 96.7% | 76.7% | 88.3% |

The error labels were dominated by location/work-mode, seniority, and role
scope. The correction is retained because it removes cross-profile query
contamination; no ranker weight or lane rule was changed because the corrected
replay still failed every comparison gate.

## Next evidence needed

The private benchmark now persists query-to-listing provenance for fresh
collections. The next replay can report generic label error rates by source and
query outcome, identifying whether remaining failures are retrieval, location
normalisation, stale/ambiguous listing metadata, or ranking—without a
role-specific rule set.
