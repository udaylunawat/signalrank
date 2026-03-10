import math
import re
from datetime import datetime, timezone

from config_loader import settings

cfg = settings


# --------------------------------------------------
# SENIORITY PENALTY
# --------------------------------------------------
def seniority_penalty(title, description, cfg) -> float:
    t = (title or "").lower()
    d = (description or "").lower()

    for k in cfg.ranking.seniority_penalty.title_keywords.junior:
        if k in t:
            return cfg.ranking.seniority_penalty.junior_multiplier

    if any(
        x in d
        for x in [
            "0-2 years",
            "1-2 years",
            "2-3 years",
            "2–3 years",
            "3 years experience",
        ]
    ):
        return cfg.ranking.seniority_penalty.low_yoe_multiplier

    return 1.0


# --------------------------------------------------
# FUNCTIONAL ROLE CLASSIFICATION (CONFIG DRIVEN)
# --------------------------------------------------
def classify_functional_role_fast(text: str) -> str:
    t = text.lower() if isinstance(text, str) else ""

    taxonomy = cfg.functional_role_taxonomy
    thresholds = cfg.functional_role_thresholds

    # 1. Explicit taxonomy blocks (ordered)
    items = taxonomy.items() if isinstance(taxonomy, dict) else vars(taxonomy).items()
    for role, block in items:
        for kw in block.keywords:
            if kw in t:
                return role

    # 2. Term-count based inference
    ai_terms = set(cfg.functional_role_terms.ai)
    devops_terms = set(cfg.functional_role_terms.devops)
    security_terms = set(cfg.functional_role_terms.security)

    ai = sum(1 for k in ai_terms if k in t)
    devops = sum(1 for k in devops_terms if k in t)
    sec = sum(1 for k in security_terms if k in t)

    if sec >= thresholds.security_min_terms:
        return "security"

    if ai >= thresholds.agentic_min_terms:
        return "agentic_systems"

    if ai >= thresholds.mlops_ai_terms and devops >= thresholds.mlops_devops_terms:
        return "mlops_llmops"

    if devops >= thresholds.platform_devops_min_terms:
        return "platform_devops"

    return "software_general"


# --------------------------------------------------
# UTILITIES
# --------------------------------------------------
def extract_max_yoe(cfg, text: str) -> int | None:
    matches = re.findall(r"(\d+)\s*\+?\s*years", text.lower())
    if not matches:
        return None
    return min(max(map(int, matches)), cfg.ranking.max_yoe_cap)


def recency_weight(cfg, date_posted: str | None) -> float:
    if not cfg.ranking.enable_recency_decay or not date_posted:
        return 1.0
    try:
        posted = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - posted).days
        return math.exp(-age_days / cfg.ranking.recency_half_life_days)
    except Exception:
        return 1.0
