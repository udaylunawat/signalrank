# Phase 4 — Assessment

## Outcome

- Primary/broader ordering gate: **passed**.
- Pre-fix ordering violations: **60**.
- Post-fix ordering violations: **0**.
- Primary top-10 share: **48.6% → 85.7%**.
- Primary-first rate among primary-eligible candidates: **83.3% → 100.0%**.
- Automated title-family Precision@10 proxy: **41.4% → 60.0%**.

## Interpretation

The ordering A/B is causal for the lane fix because it replays the same candidate/job score frames. It does not establish absolute ranking quality: the title-family precision metric is an automated proxy, not a recruiter label.

## Next assessment gate

Label the top 20 post-fix jobs for one canonical resume in each category as relevant, adjacent, or irrelevant. Feed relevant labels to `scripts/evaluate_rankings.py` and require Precision@10, Recall@20, and NDCG@10/20 to remain stable or improve before changing score weights.

## Reproducibility

Frozen catalog SHA-256: `ec3e54942c57ca14cf0336e552ab1694aa1d8c36bc46f1a3d9174484786d5dbf`.
