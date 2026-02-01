# domain/scoring.py
import math
import re
from datetime import datetime, timezone

# domain/scoring.py


def recency_weight(cfg, date_posted):
    ranking = cfg.get("ranking", {})

    if not ranking.get("enable_recency_decay", False):
        return 1.0

    if not date_posted:
        return 1.0

    try:
        posted = datetime.fromisoformat(str(date_posted).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - posted).days
        half_life = ranking.get("recency_half_life_days", 21)
        return math.exp(-age / half_life)
    except Exception:
        return 1.0


def seniority_penalty(cfg, title: str, description: str) -> float:
    ranking = cfg.get("ranking", {})
    penalty_cfg = ranking.get("seniority_penalty", {})

    title_cfg = penalty_cfg.get("title_keywords", {})
    junior_terms = title_cfg.get("junior", [])

    t = (title or "").lower()
    d = (description or "").lower()

    for k in junior_terms:
        if k in t:
            return penalty_cfg.get("junior_multiplier", 0.4)

    if any(x in d for x in ["0-2 years", "1-2 years", "2-3 years"]):
        return penalty_cfg.get("low_yoe_multiplier", 0.5)

    return 1.0


def location_weight(location: str, cfg: dict) -> float:
    loc_cfg = cfg.get("location_scoring", {})
    preferred = loc_cfg.get("preferred_locations", [])
    boost = float(loc_cfg.get("preferred_weight", 1.0))

    if not location or not preferred:
        return 1.0

    loc = location.lower()
    for p in preferred:
        if isinstance(p, str) and p.lower() in loc:
            return boost

    return 1.0


def extract_required_yoe(text: str) -> int | None:
    """
    Extract maximum years-of-experience required by a job.

    Returns:
      - highest YOE mentioned (int)
      - None if no requirement detected

    Conservative by design.
    """
    if not isinstance(text, str):
        return None

    t = text.lower()

    patterns = [
        r"(\d+)\s*\+?\s*years",
        r"(\d+)\s*-\s*(\d+)\s*years",
        r"minimum\s+(\d+)\s*years",
        r"at\s+least\s+(\d+)\s*years",
    ]

    found = []

    for p in patterns:
        for m in re.findall(p, t):
            if isinstance(m, tuple):
                nums = [int(x) for x in m if x.isdigit()]
                found.extend(nums)
            elif str(m).isdigit():
                found.append(int(m))

    if not found:
        return None

    return max(found)
