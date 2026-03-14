# Ranking Quality Improvements v2 — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 ranking issues so the top results match Example's resume profile (AI Platform Engineer) instead of being dominated by customer-facing roles and non-ML jobs at tier_s companies.

**Architecture:** Config changes (blocklist, taxonomy, tiers) + 3 surgical code changes (seniority penalty, company semantic floor, title-weighted role classification). All changes are backwards-compatible — existing scoring behavior is preserved for jobs above the semantic floor.

**Tech Stack:** Python, DuckDB, pytest, uv

**Spec:** `docs/2026-03-11-ranking-quality-v2-design.md`

---

## Chunk 1: Config-Only Changes (Tasks 1-3)

### Task 1: Title Blocklist Expansion

**Files:**
- Modify: `job_ranker/config/overrides/example.yaml:212-218`

- [ ] **Step 1: Add blocklist entries**

In `job_ranker/config/overrides/example.yaml`, replace the `title_blocklist` section:

```yaml
title_blocklist:
  - trainee
  - manager
  - sales
  - trainer
  - junior
  # Over-senior / non-IC
  - director
  - head of
  - vice president
  - vp of
```

- [ ] **Step 2: Run tests to verify nothing breaks**

Run: `uv run pytest job_ranker/tests/test_scoring.py -v`
Expected: All tests PASS (config changes don't affect unit tests, but verify no import issues)

- [ ] **Step 3: Commit**

```bash
git add job_ranker/config/overrides/example.yaml
git commit -m "config: expand title blocklist with director/vp/head-of"
```

---

### Task 2: Forward Deployed Engineer Taxonomy

**Files:**
- Modify: `job_ranker/config/base.yaml:184-191`

- [ ] **Step 1: Add taxonomy keywords**

In `job_ranker/config/base.yaml`, add to the `customer_facing` keywords list:

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

- [ ] **Step 2: Run tests**

Run: `uv run pytest job_ranker/tests/test_scoring.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add job_ranker/config/base.yaml
git commit -m "config: add forward-deployed to customer_facing taxonomy"
```

---

### Task 3: Company Tier Promotions

**Files:**
- Modify: `job_ranker/config/overrides/example.yaml:56-129`

- [ ] **Step 1: Move companies from tier_a to tier_s**

In `job_ranker/config/overrides/example.yaml`, add these to the `tier_s` list (after existing entries):

```yaml
  tier_s:
    # ... existing entries ...
    - adobe
    - salesforce
    - palantir
    - netflix
    - stripe
```

- [ ] **Step 2: Remove moved companies from tier_a**

Remove `adobe`, `salesforce`, `palantir`, `netflix`, and `stripe` from the `tier_a` list in the same file.

- [ ] **Step 3: Run tests**

Run: `uv run pytest job_ranker/tests/test_scoring.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add job_ranker/config/overrides/example.yaml
git commit -m "config: promote adobe/salesforce/palantir/netflix/stripe to tier_s"
```

---

## Chunk 2: Over-Seniority Penalty (Task 4)

### Task 4: Over-Seniority Penalty in Scoring

**Files:**
- Modify: `job_ranker/domain/scoring.py:28-84`
- Modify: `job_ranker/config/base.yaml:36-44`
- Test: `job_ranker/tests/test_scoring.py`

- [ ] **Step 1: Write failing tests**

Add to `job_ranker/tests/test_scoring.py`:

```python
from job_ranker.domain.scoring import calculate_seniority_score

# Add this class after the existing TestWeightedScore class:

class TestSeniorityScoring:
    """Tests for calculate_seniority_score including over-seniority."""

    BASE_CFG = {
        "ranking": {
            "seniority_penalty": {
                "junior_multiplier": 0.4,
                "low_yoe_multiplier": 0.5,
                "over_senior_multiplier": 0.7,
                "title_keywords": {
                    "junior": ["intern", "junior", "entry"],
                    "over_senior": ["director", "vp ", "vice president", "head of", "chief"],
                },
            },
            "seniority_boosting_keywords": ["senior", "lead", "staff", "principal"],
        },
    }

    def test_director_gets_penalty(self):
        score = calculate_seniority_score(
            self.BASE_CFG, title="Director of Engineering", description="", user_yoe=7
        )
        assert score == pytest.approx(0.7)

    def test_vp_gets_penalty(self):
        score = calculate_seniority_score(
            self.BASE_CFG, title="VP of Engineering", description="", user_yoe=7
        )
        assert score == pytest.approx(0.7)

    def test_head_of_gets_penalty(self):
        score = calculate_seniority_score(
            self.BASE_CFG, title="Head of AI Platform", description="", user_yoe=7
        )
        assert score == pytest.approx(0.7)

    def test_senior_engineer_no_penalty(self):
        score = calculate_seniority_score(
            self.BASE_CFG, title="Senior Software Engineer", description="", user_yoe=7
        )
        assert score >= 1.0  # Gets a boost, not a penalty

    def test_principal_engineer_no_penalty(self):
        """Principal is senior-boosted, not over-senior penalized."""
        score = calculate_seniority_score(
            self.BASE_CFG, title="Principal Engineer", description="", user_yoe=7
        )
        assert score >= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest job_ranker/tests/test_scoring.py::TestSeniorityScoring -v`
Expected: FAIL — `test_director_gets_penalty` returns 1.0 instead of 0.7

- [ ] **Step 3: Add over_senior config to base.yaml**

In `job_ranker/config/base.yaml`, update the `seniority_penalty` section:

```yaml
  seniority_penalty:
    junior_multiplier: 0.4
    low_yoe_multiplier: 0.5
    over_senior_multiplier: 0.7
    title_keywords:
      junior:
        - intern
        - junior
        - entry
      over_senior:
        - director
        - "vp "
        - vice president
        - head of
        - chief
```

Note: `"vp "` has a trailing space to avoid matching "vp" inside words like "development".

- [ ] **Step 4: Implement over-seniority check**

In `job_ranker/domain/scoring.py`, in `calculate_seniority_score()`, add the over-senior check AFTER the junior check (after line 58) and BEFORE the senior boost (before line 63):

```python
    # --------------------
    # Over-senior penalties
    # --------------------
    over_senior_terms = scfg.get("title_keywords", {}).get("over_senior", [])
    if any(k in t for k in over_senior_terms):
        return scfg.get("over_senior_multiplier", 0.7)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest job_ranker/tests/test_scoring.py -v`
Expected: ALL PASS (both new and existing tests)

- [ ] **Step 6: Commit**

```bash
git add job_ranker/domain/scoring.py job_ranker/config/base.yaml job_ranker/tests/test_scoring.py
git commit -m "feat: add over-seniority penalty for director/vp/head-of titles"
```

---

## Chunk 3: Semantic Floor for Company Bonus (Task 5)

### Task 5: Semantic Floor for Company Score

**Files:**
- Modify: `job_ranker/domain/additive_scoring.py:140-182`
- Modify: `job_ranker/config/base.yaml:26-30`
- Test: `job_ranker/tests/test_scoring.py`

- [ ] **Step 1: Write failing tests**

Add to `job_ranker/tests/test_scoring.py`:

```python
from job_ranker.domain.additive_scoring import apply_company_semantic_floor


class TestCompanySemanticFloor:
    """company_score should be scaled down when semantic_score is below the floor."""

    def test_above_floor_unchanged(self):
        """semantic=0.70 is above floor=0.60 → company_score unchanged."""
        assert apply_company_semantic_floor(100.0, 0.70, 0.60) == pytest.approx(100.0)

    def test_at_floor_unchanged(self):
        """semantic=0.60 is exactly at floor → company_score unchanged."""
        assert apply_company_semantic_floor(100.0, 0.60, 0.60) == pytest.approx(100.0)

    def test_below_floor_scaled(self):
        """semantic=0.50, floor=0.60 → company_score scaled by 0.50/0.60."""
        result = apply_company_semantic_floor(100.0, 0.50, 0.60)
        assert result == pytest.approx(83.333, abs=0.1)

    def test_low_semantic_heavy_scaling(self):
        """semantic=0.40, floor=0.60 → company_score scaled by 0.40/0.60."""
        result = apply_company_semantic_floor(100.0, 0.40, 0.60)
        assert result == pytest.approx(66.667, abs=0.1)

    def test_tier_a_below_floor(self):
        """Non-tier_s company also gets scaled."""
        result = apply_company_semantic_floor(85.0, 0.50, 0.60)
        assert result == pytest.approx(85.0 * 0.50 / 0.60, abs=0.1)

    def test_zero_floor_no_scaling(self):
        """floor=0 disables the feature (avoid division by zero)."""
        assert apply_company_semantic_floor(100.0, 0.30, 0.0) == pytest.approx(100.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest job_ranker/tests/test_scoring.py::TestCompanySemanticFloor -v`
Expected: FAIL — `ImportError: cannot import name 'apply_company_semantic_floor'`

- [ ] **Step 3: Implement the function**

In `job_ranker/domain/additive_scoring.py`, add this function after `company_score_0_100()`:

```python
def apply_company_semantic_floor(
    company_score: float, semantic_score: float, floor: float
) -> float:
    """Scale down company_score when semantic_score is below the floor."""
    if floor <= 0:
        return company_score
    if semantic_score >= floor:
        return company_score
    return company_score * (semantic_score / floor)
```

- [ ] **Step 4: Integrate into apply_additive_scoring()**

In `job_ranker/batch/ranker.py`, in `apply_additive_scoring()`, add the import and apply after computing company_score (after line 157):

First, add the import at the top of ranker.py:

```python
from job_ranker.domain.additive_scoring import (
    apply_company_semantic_floor,  # ADD THIS
    company_score_0_100,
    # ... rest unchanged
)
```

Then in `apply_additive_scoring()`, after `df["company_score"] = ...` (line 157), add:

```python
    # Apply semantic floor to company score
    semantic_floor = cfg.get("ranking", {}).get("company_semantic_floor", 0.60)
    df["company_score"] = df.apply(
        lambda r: apply_company_semantic_floor(
            r["company_score"], r["semantic_score"], semantic_floor
        ),
        axis=1,
    )
```

- [ ] **Step 5: Add config default**

In `job_ranker/config/base.yaml`, add under the `ranking:` section (after `min_quality_multiplier`):

```yaml
  company_semantic_floor: 0.60
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest job_ranker/tests/test_scoring.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add job_ranker/domain/additive_scoring.py job_ranker/batch/ranker.py job_ranker/config/base.yaml job_ranker/tests/test_scoring.py
git commit -m "feat: add semantic floor for company score to prevent non-relevant jobs ranking high"
```

---

## Chunk 4: Title-Weighted Role Classification (Task 6)

### Task 6: Title-Weighted Role Classification

**Files:**
- Modify: `job_ranker/domain/roles.py:11-45`
- Modify: `job_ranker/batch/ranker.py:325-327`
- Test: `job_ranker/tests/test_scoring.py`

- [ ] **Step 1: Write failing tests**

Add to `job_ranker/tests/test_scoring.py`:

```python
from job_ranker.domain.roles import classify_functional_role


class TestTitleWeightedClassification:
    """Title keywords should count 3× more than description keywords in heuristic fallback."""

    BASE_CFG = {
        "functional_role_taxonomy": {
            "architecture_strategy": {
                "keywords": ["enterprise architect", "solution architect"],
            },
            "customer_facing": {
                "keywords": ["customer engineer", "sales engineer"],
            },
        },
        "functional_role_terms": {
            "ai": ["llm", "agent", "rag", "embedding", "inference"],
            "devops": ["kubernetes", "terraform", "ci/cd", "pipeline"],
            "security": ["siem", "soc", "threat"],
        },
        "functional_role_thresholds": {
            "security_min_terms": 2,
            "agentic_min_terms": 3,
            "mlops_ai_terms": 1,
            "mlops_devops_terms": 1,
            "platform_devops_min_terms": 2,
        },
    }

    def test_taxonomy_match_still_works(self):
        """Taxonomy match uses full text — should still catch 'customer engineer'."""
        result = classify_functional_role(
            "Customer Engineer", "Build AI solutions with LLM and RAG", self.BASE_CFG
        )
        assert result == "customer_facing"

    def test_ai_title_gets_boosted(self):
        """Title with AI terms should classify as agentic even with few description terms."""
        result = classify_functional_role(
            "LLM Agent Engineer",
            "Work on embedding systems",
            self.BASE_CFG,
        )
        # Title: llm(3) + agent(3) = 6, Desc: embedding(1) = 1, Total AI = 7 >= 3
        assert result == "agentic_systems"

    def test_generic_title_ai_description_not_agentic(self):
        """Generic title + AI description shouldn't easily reach agentic threshold."""
        result = classify_functional_role(
            "Software Engineer",
            "Work with llm and agent systems",
            self.BASE_CFG,
        )
        # Title: 0 AI terms, Desc: llm(1) + agent(1) = 2, Total AI = 2 < 3
        assert result != "agentic_systems"

    def test_mlops_classification(self):
        """Title with devops terms + description with AI → mlops."""
        result = classify_functional_role(
            "Platform Engineer - Kubernetes",
            "Deploy llm inference services",
            self.BASE_CFG,
        )
        # Title: kubernetes(3), Desc: llm(1)+inference(1)=2. AI=2>=1, DevOps=3>=1 → mlops
        assert result == "mlops_llmops"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest job_ranker/tests/test_scoring.py::TestTitleWeightedClassification -v`
Expected: FAIL — `TypeError: classify_functional_role() takes 2 positional arguments but 3 were given`

- [ ] **Step 3: Update classify_functional_role signature and implementation**

Replace `classify_functional_role` in `job_ranker/domain/roles.py`:

```python
def classify_functional_role(title: str, description: str, cfg: dict) -> str:
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    full_text = f"{title_lower} {desc_lower}"

    taxonomy = cfg.get("functional_role_taxonomy", {})
    thresholds = cfg.get("functional_role_thresholds", {})

    # Explicit taxonomy wins (checks full text)
    for role, block in taxonomy.items():
        for kw in block.get("keywords", []):
            if kw in full_text:
                return role

    terms = cfg.get("functional_role_terms", {})
    title_weight = 3

    ai_terms = terms.get("ai", [])
    devops_terms = terms.get("devops", [])
    security_terms = terms.get("security", [])

    ai = sum(k in title_lower for k in ai_terms) * title_weight + sum(k in desc_lower for k in ai_terms)
    devops = sum(k in title_lower for k in devops_terms) * title_weight + sum(k in desc_lower for k in devops_terms)
    sec = sum(k in title_lower for k in security_terms) * title_weight + sum(k in desc_lower for k in security_terms)

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

- [ ] **Step 4: Update call site in ranker.py**

In `job_ranker/batch/ranker.py`, replace lines 325-327:

```python
    # Before:
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

- [ ] **Step 5: Run all tests**

Run: `uv run pytest job_ranker/tests/test_scoring.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add job_ranker/domain/roles.py job_ranker/batch/ranker.py job_ranker/tests/test_scoring.py
git commit -m "feat: title-weighted role classification (3x title keyword weight)"
```

---

## Chunk 5: Integration Validation (Task 7)

### Task 7: Re-run Batch and Validate Results

**Files:**
- No code changes — validation only

- [ ] **Step 1: Run the batch**

Run: `uv run python -m job_ranker.batch.run`
Expected: Completes with `status=success`. This also validates that all code changes integrate cleanly.

- [ ] **Step 2: Pull top 10 results and verify**

```python
uv run python -c "
import duckdb, json
con = duckdb.connect('job_ranker/duckdb', read_only=True)
run = con.execute('SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1').fetchone()[0]
rows = con.execute(f\"\"\"
    SELECT final_score, payload FROM run_results
    WHERE run_id='{run}' ORDER BY final_score DESC LIMIT 10
\"\"\").fetchall()
for i, (score, payload) in enumerate(rows, 1):
    p = json.loads(payload)
    print(f'#{i} | {score:.1f} | {p.get(\"title\")} @ {p.get(\"company\")} | role={p.get(\"functional_role\")} | sem={p.get(\"semantic_score\",0):.3f} | rec={p.get(\"recency_score\",0):.0f}')
"
```

**Verify these acceptance criteria:**
- No duplicate jobs in top 10
- No Director/VP/Customer Engineer roles in top 20
- Recency scores are NOT all 50.0
- "AI Engineer @ Adobe" or similar ML-focused roles rank higher than generic SWE roles at tier_s companies
- "Field Solutions Architect @ Google" is capped at ≤75 (or absent if deduped)

- [ ] **Step 3: Commit validation results**

Save the top-10 output to a comment or log for future reference.

```bash
git add -A
git commit -m "validation: re-run batch with ranking quality v2 improvements"
```
