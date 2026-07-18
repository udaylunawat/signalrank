# Phase 7 — Bounded verified-profile source benchmark

Date: 2026-07-17

## Collection rule

The local fixture runner can now create a fresh private catalog from exact
verified target-role and preferred-location pairs in the ignored manifest. It
does not mix one candidate's role with another candidate's location, use the
legacy fixed category matrix, a job-family catalogue, inferred resume roles,
or title-specific expansion in the benchmark script.

Collection is opt-in through `--refresh-catalog`. It retains the ingest
service's fixed six-query, two-attempt, 15-second request, and 90-second total
JobSpy safeguards per batch. If the profile-derived plan would exceed the
requested number of bounded query batches, the run fails instead of silently
excluding a role.

## Assessment flow

1. Create a new ignored fixture-run output directory with
   `--refresh-catalog --max-queries 6`.
2. Review every newly surfaced top-10 listing with the graded label schema.
3. Compare the new ranking and labels against the frozen baseline with
   `scripts/compare_ranking_evaluations.py`.
4. Accept a source or query change only when the generic Phase 6 gate passes.

The private report retains only source/status counts, catalog digest, and
ranking coverage. It does not write query terms, resume text, parsed fields, or
job samples into the Markdown assessment.
