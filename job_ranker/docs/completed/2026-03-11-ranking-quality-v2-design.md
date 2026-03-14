# Ranking Quality Improvements v2

**Date**: 2026-03-11
**Status**: Proposed
**Goal**: Fix 6 ranking issues identified by reviewing top-5 and random-sample results against Example's resume.

---

## Context

A manual review of the latest batch run (`9e5ca6ba`, 2026-03-10, 4533 results) revealed that the top results are dominated by customer-facing roles (Field Solutions Architect, Customer Engineer) and non-ML jobs at tier_s companies (Microsoft Teams backend). Meanwhile, excellent-fit jobs like "AI Engineer @ Adobe" rank at #41.

### Resume Profile

Senior Software Engineer / AI Platform Engineer, 7 YOE. Core: Python, GCP, Kubernetes, LangGraph, FastAPI, MLflow, Docker, Terraform, CI/CD, RAG, Vector DBs. Builds ML platforms, inference services, agentic orchestration, distributed systems.

### Problems Found

| # | Problem | Example | Root Cause |
|---|---------|---------|------------|
| 1 | Duplicate jobs in top 3 | Same Google FSA role 3× | **Already fixed** — title+company dedup in ranker.py, needs re-run |
| 2 | Recency all 50.0 | Every result | **Already fixed** — timezone bug in additive_scoring.py, needs re-run |
| 3 | Customer-facing roles ranked as engineering | "Outcome Customer Engineer" #32 | Taxonomy keywords added post-run, but title-weighted classification still needed |
| 4 | "Director" slips through blocklist | "Dir, Software Engrg Mgmt" #68 | Blocklist has "manager" but not "director" |
| 5 | Company score dominates over fit | MS Teams backend #34 beats Adobe AI Eng #41 | No semantic floor on company bonus |
| 6 | Seniority scoring flat | Director gets seniority=1.0 | No over-seniority penalty |
| 7 | Company tier misalignment | Adobe in tier_a despite being major AI platform company | Tier classification needs updating |

---

## Changes

### Change 1: Title Blocklist Expansion

**File**: `job_ranker/config/overrides/example.yaml`
**Type**: Config only
**Risk**: Low

Add hard-block titles that are clearly non-IC:

```yaml
title_blocklist:
  - trainee
  - manager
  - sales
  - trainer
  - junior
  # NEW
  - director
  - head of
  - vice president
  - vp of
```

**Rationale**: These are management/leadership roles, not IC engineering. Hard blocking (Approach A from hybrid strategy) is appropriate since there's no ambiguity — a "Director of Engineering" is never an IC role.

**Edge cases**: "Principal" is NOT blocked because "Principal Engineer" is a valid IC role (handled by soft penalty in Change 3 instead).

---

### Change 2: "Forward Deployed Engineer" to Taxonomy

**File**: `job_ranker/config/base.yaml`
**Type**: Config only
**Risk**: Low

Add under `customer_facing` keywords:

```yaml
customer_facing:
  keywords:
    - solutions engineer
    - pre-sales
    - sales engineer
    - customer engineer
    - field solutions
    # NEW
    - forward deployed engineer
    - forward deployed
```

**Effect**: These roles get capped at 60 (the `customer_facing` role-intent cap in base.yaml). They still appear in results but won't dominate the top 10. This is the soft-cap approach (Approach B from hybrid strategy).

---

### Change 3: Over-Seniority Penalty

**File**: `job_ranker/domain/scoring.py` — `calculate_seniority_score()`
**Type**: Code change
**Risk**: Medium

Currently the function only penalizes junior roles and boosts senior ones. A Director gets seniority=1.0 (neutral), identical to a mid-level engineer.

**Add** detection of over-senior titles and apply a penalty:

```python
# After junior check, before senior boost:
over_senior_terms = scfg.get("title_keywords", {}).get("over_senior", [])
if not over_senior_terms:
    over_senior_terms = ["director", "vp ", "vice president", "head of", "chief"]
if any(k in t for k in over_senior_terms):
    return scfg.get("over_senior_multiplier", 0.7)
```

**Config addition** in `base.yaml`:

```yaml
seniority_penalty:
  over_senior_multiplier: 0.7
  title_keywords:
    junior:
      - intern
      - junior
      - entry
    over_senior:
      - director
      - vp
      - vice president
      - head of
      - chief
```

**Effect**: seniority_score_0_100(0.7) = 46 (down from 82+ for neutral). Combined with the title blocklist, most Director roles get filtered; this catches edge cases that slip through.

---

### Change 4: Semantic Floor for Company Bonus

**File**: `job_ranker/domain/additive_scoring.py`
**Type**: Code change
**Risk**: Medium

The core ranking problem: a non-ML job at a tier_s company scores higher than a perfect-fit ML job at a tier_a company, because company_score=100 overwhelms the semantic difference.

**Add** a relevance scaling factor to `company_score_0_100()` or as a post-processing step in `apply_additive_scoring()`:

```python
# In apply_additive_scoring(), after computing company_score:
semantic_floor = cfg.get("ranking", {}).get("company_semantic_floor", 0.60)
df["company_score"] = df.apply(
    lambda r: r["company_score"] * min(1.0, r["semantic_score"] / semantic_floor),
    axis=1,
)
```

**Behavior**:

| semantic_score | company_score (tier_s) | After scaling |
|----------------|----------------------|---------------|
| 0.70 | 100 | 100 (unaffected, above floor) |
| 0.60 | 100 | 100 (at floor, unaffected) |
| 0.576 | 100 | 96 |
| 0.50 | 100 | 83 |
| 0.40 | 100 | 67 |

**Config addition** in `base.yaml`:

```yaml
ranking:
  company_semantic_floor: 0.60
```

**Rationale**: This is smooth (no discontinuities), configurable, and only affects jobs where the semantic fit is poor. A genuinely relevant job at a great company is unaffected.

---

### Change 5: Title-Weighted Role Classification

**File**: `job_ranker/domain/roles.py` — `classify_functional_role()`
**File**: `job_ranker/batch/ranker.py` — call site
**Type**: Code change
**Risk**: Medium

Currently `classify_functional_role()` receives `title + " " + description` as a single string. A "Customer Engineer" with an AI-heavy description gets classified as `agentic_systems` because 3+ AI terms in the description override the title signal.

**Change signature** to accept `title` and `description` separately:

```python
def classify_functional_role(title: str, description: str, cfg: dict) -> str:
    # 1. Taxonomy match (unchanged — checks full text)
    full_text = f"{title} {description}".lower()
    taxonomy = cfg.get("functional_role_taxonomy", {})
    for role, block in taxonomy.items():
        for kw in block.get("keywords", []):
            if kw in full_text:
                return role

    # 2. Heuristic fallback — title terms count 3×
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    terms = cfg.get("functional_role_terms", {})

    title_weight = 3

    ai_terms = terms.get("ai", [])
    devops_terms = terms.get("devops", [])
    security_terms = terms.get("security", [])

    ai = sum(k in title_lower for k in ai_terms) * title_weight + sum(k in desc_lower for k in ai_terms)
    devops = sum(k in title_lower for k in devops_terms) * title_weight + sum(k in desc_lower for k in devops_terms)
    sec = sum(k in title_lower for k in security_terms) * title_weight + sum(k in desc_lower for k in security_terms)

    # Thresholds remain unchanged
    thresholds = cfg.get("functional_role_thresholds", {})
    if sec >= thresholds.get("security_min_terms"):
        return "security"
    if ai >= thresholds.get("agentic_min_terms"):
        return "agentic_systems"
    if ai >= thresholds.get("mlops_ai_terms") and devops >= thresholds.get("mlops_devops_terms"):
        return "mlops_llmops"
    if devops >= thresholds.get("platform_devops_min_terms"):
        return "platform_devops"

    return "software_general"
```

**Call site change** in `ranker.py`:

```python
# Before (line 326-327):
df["functional_role"] = (
    df["title"].fillna("") + " " + df["description"].fillna("")
).apply(lambda t: classify_functional_role(t, cfg))

# After:
df["functional_role"] = df.apply(
    lambda r: classify_functional_role(
        r["title"] or "", r["description"] or "", cfg
    ),
    axis=1,
)
```

**Effect**: Title keywords get 3× weight in heuristic classification. Taxonomy matching is unaffected (still checks full text). This means a job titled "Customer Engineer" with AI terms in the description won't be mis-classified as `agentic_systems` — the title carries no AI signal, so the total AI count stays low.

---

### Change 6: Company Tier Promotions

**File**: `job_ranker/config/overrides/example.yaml`
**Type**: Config only
**Risk**: Low

Move from tier_a to tier_s:

- **Adobe** — Firefly, Sensei, major AI platform investment
- **Salesforce** — Einstein AI, large-scale ML platform
- **Palantir** — Core AI/ML infrastructure company
- **Netflix** — Elite ML engineering culture, recommendation systems
- **Stripe** — Growing AI/ML capabilities, top-tier engineering

```yaml
tier_s:
  # ... existing entries ...
  - adobe
  - salesforce
  - palantir
  - netflix
  - stripe
```

Remove these from tier_a list to avoid duplication.

---

## Summary of Changes

| Change | File(s) | Type | Approach |
|--------|---------|------|----------|
| 1. Title blocklist | example.yaml | Config | Hard block |
| 2. Forward Deployed taxonomy | base.yaml | Config | Soft cap (≤60) |
| 3. Over-seniority penalty | scoring.py, base.yaml | Code+Config | Soft penalty |
| 4. Semantic floor for company | additive_scoring.py, base.yaml | Code+Config | Smooth scaling |
| 5. Title-weighted classification | roles.py, ranker.py | Code | 3× title weight |
| 6. Company tier promotions | example.yaml | Config | Tier reassignment |

## Testing Strategy

1. **Unit tests** (`tests/test_scoring.py`):
   - Test over-seniority penalty returns 0.7 for "Director of Engineering"
   - Test company semantic floor scaling at various semantic_score values
   - Test title-weighted classification: "Customer Engineer" + AI description → NOT `agentic_systems`
   - Test blocklist catches "Director" and "Head of"

2. **Integration validation**:
   - Re-run batch: `uv run python -m job_ranker.batch.run`
   - Pull top-10 and compare against this analysis
   - Verify: Adobe AI Engineer should rank higher than MS Teams backend
   - Verify: No duplicates in top 10
   - Verify: Recency scores are no longer all 50.0
   - Verify: No Director/VP/Customer Engineer roles in top 20

## Expected Outcome

After these changes + a re-run:
- "AI Engineer @ Adobe" should be in the top 10-15 (up from #41)
- "Software Engineer @ ServiceNow (Moveworks)" should be in top 15 (up from #63)
- "Field Solutions Architect @ Google" capped at ≤75 (down from #1)
- "Dir, Software Engrg Mgmt" blocked entirely
- "Outcome Customer Engineer" capped at ≤60 (down from #32)
- MS Teams backend drops significantly due to semantic floor on company bonus
- Recency scores provide actual differentiation (recent jobs score higher)
