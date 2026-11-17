# POC 1 — Conservative ATS posting identity

**Branch:** `feature/june-06-backend-hardening`. **Date:** 2026-11-17. **Status:** isolated proof of concept only; **no application code or database schema changed**.

This experiment is motivated by the June ranker's final company/title deduplication and the pre-embedding company/title/location selection. Both can suppress separate vacancies sharing a generic job title. URL-only deduplication has the opposite failure: the same opening reappears under several board URLs.

## What was implemented

- `posting_identity.py`: pure standard-library Python URL normalization and **high-confidence ATS identity** recognizers for Greenhouse, Lever, Ashby, Workday, Indeed and LinkedIn.
- Explicit, fixture-only identities for `example.invalid` generated URLs, so this offline benchmark requires **no network access**.
- `identity_for`: use a trusted canonical employer link only when `canonical_url_verified=True` was provided by a trusted adapter. Do not let arbitrary third-party query parameters invent a provider identity.
- Fallback: canonical comparison URL for unknown vendors; stable row identity for missing/invalid URLs. Never merge on company/title alone.
- `group_postings`: returns reversible *relationships*, keeping all member IDs, URLs and source names. It does not delete or update records.
- `evaluate_identity.py`: pairwise duplicate-precision/recall comparison against three approximate June key policies.
- `test_posting_identity.py` and `test_evaluate_identity.py`: adversarial cases plus the frozen synthetic fixture.

The code is research code under `docs/` and must not be imported into the production ingestion or ranking pipeline before an explicit implementation review.

## Reproduction

```sh
python3 docs/benchmark/fixtures/generate_jobset.py
python3 -m unittest discover -s docs/benchmark/poc -p 'test_*.py' -v
python3 docs/benchmark/poc/evaluate_identity.py
```

The shared fixture contains **150 synthetic listings representing 120 distinct requisitions**, with 30 deliberately duplicated board aliases, using fictional companies and `example.invalid` URLs. All results below are **only for that constructed dataset**.

## Results — synthetic fixture only

| Identity rule | Predicted opening groups | Correct duplicate pairs | False merged pairs | Missed duplicate pairs | Pairwise precision | Pairwise recall |
|---|---:|---:|---:|---:|---:|---:|
| URL-only (approximate June ingest) | 150 | 0 | 0 | 30 | n/a | 0% |
| Company + title (approximate June final matches) | 104 | 30 | 64 | 0 | 31.9% | 100% |
| Company + title + location (approximate June pre-embedding) | 112 | 30 | 32 | 0 | 48.4% | 100% |
| **ATS-aware identity (POC)** | **120** | **30** | **0** | **0** | **100%** | **100%** |

**Interpretation:** The synthetic fixture intentionally contains provider identifiers and same-title-different-requisition counterexamples. The POC groups all 30 intentionally aliased pairs without merging distinct requisitions **by construction**. This is a *correctness demonstration of the contract*, **not** a measurement of live job deduplication quality, source coverage or ranking accuracy. The three baselines approximate specific code-level key policies and do **not** execute the SignalRank production pipeline.

A 100% score on these specially constructed examples **must not be extrapolated** to actual Greenhouse/Lever/Workday listings, India-specific job boards, reposts, recruiter mirrors, or cases with insufficient canonical identity.

## Architecture implications

1. Retain the existing `jobs_raw` row IDs, application and recruiter history. Add an optional, **non-destructive** posting identity key and source URL alias relationship if POC is adopted.
2. Extract provider requisition IDs **before** pre-embedding and final match dedup. Avoid dropping rows solely because employer/title/location is the same.
3. When source identity is missing, do **not** group simply because titles are similar; expose a `possible_duplicate` relationship if textual evidence suggests a connection.
4. Require provenance when a board reports an employer canonical URL. Untrusted job-page text or AI output cannot assert equivalence.
5. Store the *original clickable URL* separately from a normalized comparison key. Preserve Workday path casing and identity-bearing board query parameters.
6. Add migration/rollback tests and compare benchmark pairwise precision and false merges before feature-flagging a production change.

## Known limitations and follow-up

- No HTTP redirect follow, company ATS API fetch, website metadata verification or actual browser testing.
- Does not recognize every possible ATS (e.g. Oracle, iCIMS, SmartRecruiters, Workable, SAP, Eightfold, Naukri). Unknown hosts use comparison-only URL equality.
- URL canonicalization and ATS reader rules must be tested against real URL corpora, including misleading or malicious URLs, multi-tenant and multilingual variants.
- The synthetic test corpus intentionally contains easy-to-parse fixture IDs. A production-grade evaluation needs independently adjudicated pairs and coverage by source, country and posting age.
- POC data structures are not normalized relational database schema. Do not run an automatic migration or hide duplicate rows based on this demonstration.
- Next independent POC: versioned, explainable ranking facts; then source-health state machine.

**Decision:** **ITERATE** — keep as a reference implementation, add real URL and false-merge gold labels, then design a reversible, feature-flagged integration. Do not ship as-is.
