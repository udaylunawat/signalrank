# Phase 5 — Graded relevance evaluation

Date: 2026-07-17

## Purpose

Before changing generic score weights again, the private fixture benchmark now
collects independent, graded judgements instead of a binary proxy inferred from
the primary lane. A label is one of: 0 (irrelevant), 1 (adjacent), 2 (good), or
3 (strong). Unreviewed jobs remain explicitly unreviewed; they are never
counted as negative examples.

Low-grade labels can use only these role-agnostic error tags:

- `role_scope`
- `skills_or_domain`
- `seniority`
- `location_or_work_mode`
- `employment_terms`
- `listing_quality`
- `other`

The tags describe a mismatch between a verified target profile and a listing,
without a prescribed job family, title list, career stage, or resume-derived
taxonomy.

## Measurements

`scripts/evaluate_rankings.py` groups results by opaque candidate ID before
calculating macro averages, so one large result set cannot dominate the
benchmark. Its output is aggregate-only and includes:

- label coverage and unreviewed counts;
- graded NDCG and judged precision at configured cutoffs;
- the distribution of relevance grades; and
- the generic error-tag counts.

The runner rejects duplicate labels, labels that do not belong to its ranking
snapshot, unknown tags, and error tags on an unreviewed or high-grade listing.
This keeps label quality separate from ranking signals and makes the next
calibration phase auditable.

Existing binary label queues have a one-time local migration path: `true`
becomes grade 2, `false` becomes grade 0, and `null` remains unreviewed. The
migration never adds error tags or changes the source queue.

## Gate for Phase 3

Do not modify score weights until each canonical candidate has reviewed the
same top-10 depth. Compare the frozen baseline and an experimental replay with
the same labels. A candidate family may not be traded off against another:
require non-regression in macro judged precision@5, judged precision@10, and
graded NDCG@10, alongside the existing primary-lane protection gate.
