# Phase 6 — Generic calibration gate

Date: 2026-07-17

## Rule

No score, prompt, or retrieval change becomes a ranking improvement merely
because its aggregate score moves upward. It must replay the same private
candidate set and pass the comparison gate in
`scripts/compare_ranking_evaluations.py`.

The gate compares macro averages across opaque candidates, not a pooled job
list. It requires complete human review through rank 10 in both runs and
rejects a candidate when any of these decline:

- judged precision@5;
- judged precision@10;
- graded NDCG@10; or
- primary-lane share in the top 10.

The comparison output contains only aggregate metrics, deltas, and gate
statuses. It has no resume text, job text, candidate names, or role taxonomy.

## Current status

The initial two-stage scorer experiment was rejected by this policy: it
lowered the frozen baseline precision@10. The committed additive scorer remains
the baseline. Future calibration must first identify a consistent generic
failure pattern in independently-labelled data; weights will not be adjusted
by intuition alone.
