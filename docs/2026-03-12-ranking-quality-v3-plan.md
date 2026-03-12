# Ranking Quality v3 — Incremental Improvements

**Date**: 2026-03-12
**Status**: Complete (A, B, C, D all done)
**Prerequisite**: Ranking Quality v2 (completed, see `docs/completed/`)

## Improvements (ROI-ordered)

### A) QA/Test Title Blocklist — DONE
**Effort**: Config-only | **Impact**: Removes false positives from top 20

Added to `example.yaml` title_blocklist:
- `automation engineer`
- `qa engineer`
- `test engineer`
- `quality engineer`
- `sdet`

**Motivation**: "Automation Engineer @ Adobe" (#17) was essentially a QA/test role for agentic systems, ranking high due to tier_s + recency despite low semantic (0.555).

---

### B) Raise Semantic Floor to 0.65 — DONE
**Effort**: Config-only | **Impact**: Pushes non-ML tier_s jobs lower

Changed `company_semantic_floor` from `0.60` to `0.65` in `base.yaml`.

**Effect**: Jobs with semantic < 0.65 at tier_s companies get more aggressive company_score scaling. At semantic=0.56 (MS Teams backend), company_score drops from 100 to 86 (was 93 at floor=0.60).

---

### C) Hidden Gem Bonus — DONE
**Effort**: Code change (~20 min) | **Impact**: Surfaces great-fit jobs from unknown companies

**Problem**: Jobs like "AI Engineer @ Codersbay" (sem=0.777) and "AgenticOps Platform Engineer @ BridgeAi" (sem=0.735) are excellent fits but rank at #34-35 because company_score=40 (unknown default).

**Proposed approach**: If company tier is unknown (default) AND semantic_score > 0.70, bump company_score from 40 to 60. This is a targeted bonus that doesn't affect known companies.

**Implementation**:
- Add `apply_hidden_gem_bonus()` in `domain/additive_scoring.py`
- Integrate in `batch/ranker.py` after company_score computation
- Config: `ranking.hidden_gem_semantic_threshold: 0.70`, `ranking.hidden_gem_company_bonus: 60`
- Tests: verify bonus applies only when tier=default AND semantic > threshold

---

### D) Contract/Part-time Detection — DONE
**Effort**: Code change (~30 min) | **Impact**: Low frequency (~5% of results)

**Problem**: "Data Scientist @ VWorker" (#87) is 3 hours/day part-time. No signal currently to detect or penalize atypical employment types.

**Proposed approach**: Scan title and first 200 chars of description for contract signals (`contract`, `part-time`, `freelance`, `hours per day`, `hrs/day`). If detected, apply a mild penalty (e.g., 0.9 multiplier on final_score) or tag for dashboard filtering.

---

## Validation Plan

After implementing C and D:
1. Re-run batch: `uv run python -m job_ranker.batch.run`
2. Pull top 20 and verify:
   - No QA/test/automation roles
   - High-semantic unknown company jobs rank closer to top 20
   - Contract/part-time jobs flagged or penalized
3. Compare top 5 against resume for relevance
