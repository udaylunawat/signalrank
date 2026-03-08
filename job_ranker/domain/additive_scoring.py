# domain/additive_scoring.py
"""
Weighted additive scoring: 5 dimensions each scored 0-100.

final_score = skills × 0.40 + company × 0.20 + seniority × 0.15
            + location × 0.15 + recency × 0.10
"""

from __future__ import annotations

from datetime import datetime, timezone


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(value, hi))


def skills_score_0_100(
    semantic_score: float,
    skill_overlap: int,
    role_skill_score: float,
    functional_role_penalty: float,
    consulting_damp: float,
) -> float:
    base = semantic_score * 100

    # Skill overlap bonus (capped at +8)
    base += min(skill_overlap * 2, 8)

    # Role/skill modifier: clamped [-10, +10]
    role_mod = (role_skill_score - 1.0) * 25
    base += _clamp(role_mod, -10, 10)

    # Functional role modifier: clamped [-8, +10]
    func_mod = (functional_role_penalty - 1.0) * 50
    base += _clamp(func_mod, -8, 10)

    # Consulting dampener: if < 1.0, subtract 10
    if consulting_damp < 1.0:
        base -= 10

    return _clamp(base)


def company_score_0_100(tier: str) -> float:
    return {"preferred": 100.0, "deprioritized": 15.0}.get(tier, 50.0)


def seniority_score_0_100(multiplier: float) -> float:
    # Linear map [0.4, 1.15] -> [10, 100]
    score = ((multiplier - 0.4) / 0.75) * 90 + 10
    return _clamp(score)


def location_score_0_100(weight: float) -> float:
    return 100.0 if weight > 1.0 else 30.0


def recency_score_0_100(date_posted) -> float:
    if date_posted is None:
        return 50.0

    try:
        posted = datetime.fromisoformat(str(date_posted).replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - posted).days
    except Exception:
        return 50.0

    if age_days < 0:
        return 100.0

    # Piecewise linear: 0d->100, 7d->80, 14d->60, 30d->30, 60d->10
    breakpoints = [(0, 100), (7, 80), (14, 60), (30, 30), (60, 10)]
    for i in range(len(breakpoints) - 1):
        d0, s0 = breakpoints[i]
        d1, s1 = breakpoints[i + 1]
        if age_days <= d1:
            frac = (age_days - d0) / (d1 - d0)
            return s0 + frac * (s1 - s0)

    return 10.0


DEFAULT_WEIGHTS = {
    "skills_match": 0.40,
    "company_fit": 0.20,
    "seniority": 0.15,
    "location": 0.15,
    "recency": 0.10,
}


def compute_weighted_score(scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    return (
        scores["skills_match"] * w.get("skills_match", 0.40)
        + scores["company_fit"] * w.get("company_fit", 0.20)
        + scores["seniority"] * w.get("seniority", 0.15)
        + scores["location"] * w.get("location", 0.15)
        + scores["recency"] * w.get("recency", 0.10)
    )
