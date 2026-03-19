"""
tests/test_mini_ranker.py — unit tests for mini_ranker.py scoring functions.
"""
import sys
from pathlib import Path

# mini_ranker.py is at project root — add it to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import mini_ranker as mr

# ── test setup: prime module-level state ─────────────────────────────────────

def setup_module():
    mr.CFG = mr.load_config.__func__(None) if hasattr(mr.load_config, "__func__") else {}
    # Use defaults so tests are self-contained
    import copy
    mr.CFG = copy.deepcopy(mr.DEFAULTS)
    mr.COMPANY_TIERS, mr.COMPANY_ALIASES, mr.TIER_SCORES = mr.build_tiers(mr.CFG)


# ── consulting_dampener ───────────────────────────────────────────────────────

def test_consulting_dampener_plain_engineer():
    assert mr.consulting_dampener("Software Engineer") == 1.0

def test_consulting_dampener_manager_no_ic():
    assert mr.consulting_dampener("Manager, Delivery") == 0.8

def test_consulting_dampener_assistant_manager():
    assert mr.consulting_dampener("Assistant Manager Operations") == 0.8

def test_consulting_dampener_senior_manager():
    assert mr.consulting_dampener("Senior Manager Program") == 0.8

def test_consulting_dampener_senior_manager_with_engineer():
    # Has IC signal → no dampen
    assert mr.consulting_dampener("Senior Manager Platform Engineer") == 1.0


# ── extract_max_yoe ───────────────────────────────────────────────────────────

def test_extract_max_yoe_basic():
    assert mr.extract_max_yoe("Requires 5+ years of experience") == 5

def test_extract_max_yoe_range():
    assert mr.extract_max_yoe("3-5 years of experience required") == 5

def test_extract_max_yoe_minimum():
    assert mr.extract_max_yoe("Minimum 4 years of relevant experience") == 4

def test_extract_max_yoe_at_least():
    assert mr.extract_max_yoe("At least 6 years of experience in ML") == 6

def test_extract_max_yoe_none():
    assert mr.extract_max_yoe("No experience requirements stated") is None

def test_extract_max_yoe_takes_max():
    assert mr.extract_max_yoe("Minimum 3 years, at least 7 years preferred") == 7


# ── company_score hidden gem bonus ────────────────────────────────────────────

def test_hidden_gem_bonus_applies():
    # Unknown company with high semantic — should get boosted to gem_bonus (60)
    score = mr.company_score("SomeUnknownStartup", semantic=0.75)
    assert score == 60.0

def test_hidden_gem_bonus_does_not_downgrade():
    # If a default company would score 40 and gem_bonus is 60, use 60
    # But if somehow already > 60, use the higher value (max behaviour)
    # Default tier scores at 40.0 — bonus should lift to 60
    score = mr.company_score("UnknownCo", semantic=0.80)
    assert score == 60.0

def test_hidden_gem_no_bonus_below_threshold():
    # Semantic below threshold (0.70) — no bonus applied
    score = mr.company_score("UnknownStartupXYZ", semantic=0.60)
    assert score == 40.0

def test_tier_s_company_not_affected_by_gem_bonus():
    # Tier-S company should not be capped at 60
    score = mr.company_score("Databricks", semantic=0.90)
    assert score == 100.0


# ── recency_score default ─────────────────────────────────────────────────────

def test_recency_score_none_returns_30():
    assert mr.recency_score(None) == 30.0

def test_recency_score_nan_returns_30():
    import numpy as np
    assert mr.recency_score(np.nan) == 30.0

def test_recency_score_fresh_job():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    assert mr.recency_score(today) == 100.0

def test_recency_score_old_job():
    assert mr.recency_score("2020-01-01") == 10.0
