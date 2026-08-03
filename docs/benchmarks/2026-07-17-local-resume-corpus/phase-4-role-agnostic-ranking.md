# Phase 4 — Role-agnostic ranking signals

Date: 2026-07-17

## Change under test

The ranking pipeline now separates three kinds of evidence:

- Confirmed profile intent: free-text target roles, user-provided aliases,
  locations, and experience live in `config_overrides.profile_intent` and the
  existing profile fields.
- Parser output: resume extraction may suggest career evidence for onboarding,
  but it no longer writes inferred roles into the active target-role profile.
- Job evidence: a candidate-independent, cached `JobEnrichment` record stores
  generic job aliases, seniority, explicit skills, workplace, and title versus
  responsibility coherence. It is populated once per job, never once per
  candidate.

Only an `assessed`, high-confidence contradiction can demote a job from the
primary lane. Unavailable, stale, or invalid enrichment remains neutral and is
shown in the result explanation.

The enrichment prompt is role-agnostic. It receives one job at a time and is
explicitly prohibited from using a resume, candidate preference, company tier,
or a pre-defined role catalogue.

## Validation

- Focused backend suite: 37 passed.
- Private fixture-runner suite: 5 passed.
- Alembic SQL-only migration validation reached `da3e9f1b7c24` and produced the
  `job_enrichments` table with a UUID foreign key to `jobs_raw`.
- Frozen local corpus: 8 PDFs, 6 canonical candidates, copied catalog only,
  deterministic parser only, and no external LLM call.

## Frozen replay result

| Measure | Before | After | Interpretation |
| --- | ---: | ---: | --- |
| Primary jobs in top 10 | 53 / 60 | 53 / 60 | Primary-lane protection did not regress. |
| Primary top-10 share | 88.3% | 88.3% | Stable. |
| Top-10 job identity overlap | — | 60 / 60 | The same labelled jobs remained in view. |
| Precision at 5 | 60.0% | 63.3% | Small ordering improvement only. |
| Precision at 10 | 45.0% | 45.0% | Unchanged. |
| NDCG at 10 | 88.9% | 89.0% | Effectively unchanged. |

The minor P@5 movement must not be attributed to job enrichment: the frozen
replay intentionally contained no live job assessments, so all new listing
quality signals were neutral. This run establishes compatibility and protects
the existing labelled baseline; it does not measure prompt quality.

## Next controlled benchmark

1. Build a separate, ignored copy of the frozen catalog and enrich a bounded,
   fixed job set with the generic rubric once. Persist the assessment snapshot
   and model/prompt version with it.
2. Replay exactly the same six confirmed profiles against the neutral and
   enriched catalog copies, reusing the existing labels whenever job identity
   is unchanged and independently labelling only new top-10 jobs.
3. Gate rollout on primary top-10 share, P@5, P@10, NDCG@10, and a manual
   count of false-primary examples. Report the per-candidate deltas and do not
   ship a prompt change that improves one role family by degrading another.
