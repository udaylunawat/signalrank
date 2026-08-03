# domain/scoring.py
import re
from dataclasses import dataclass

# domain/scoring.py


@dataclass(frozen=True)
class ExperienceRequirement:
    minimum_years: int
    maximum_years: int | None


def calculate_seniority_score(
    cfg: dict,
    *,
    title: str,
    description: str,
    user_yoe: int | None = None,
) -> float:
    """
    Returns a bounded seniority multiplier in [0.4, 1.15].

    Philosophy:
    - Junior roles are penalized
    - Senior-aligned roles get a mild boost
    - Never dominates semantic intent
    """

    ranking = cfg.get("ranking", {})
    scfg = ranking.get("seniority_penalty", {})

    t = (title or "").lower()
    d = (description or "").lower()

    # --------------------
    # Junior hard penalties
    # --------------------
    junior_terms = scfg.get("title_keywords", {}).get("junior", [])
    if any(k in t for k in junior_terms):
        return scfg.get("junior_multiplier", 0.4)

    if any(x in d for x in ["0-2 years", "1-2 years", "2-3 years"]):
        return scfg.get("low_yoe_multiplier", 0.5)

    # --------------------
    # Over-senior penalties
    # --------------------
    over_senior_terms = scfg.get("title_keywords", {}).get("over_senior", [])
    if any(k in t for k in over_senior_terms):
        return scfg.get("over_senior_multiplier", 0.7)

    # --------------------
    # Senior / lead boosts
    # --------------------
    senior_terms = ranking.get(
        "seniority_boosting_keywords",
        ["senior", "lead", "staff", "principal"],
    )

    boost = 1.0
    if any(k in t for k in senior_terms):
        boost *= 1.08

    # --------------------
    # YOE alignment (soft)
    # --------------------
    if user_yoe is not None:
        req = extract_required_yoe_range(d)
        if req is not None:
            if user_yoe + 1 < req.minimum_years:
                return min(boost * 0.55, 0.65)
            if req.maximum_years is None or user_yoe <= req.maximum_years + 1:
                boost *= 1.05
            elif user_yoe >= req.maximum_years + 5:
                boost *= 0.9

    return min(boost, 1.15)


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


def extract_required_yoe_range(text: str) -> ExperienceRequirement | None:
    if not isinstance(text, str):
        return None

    t = text.lower()
    matches: list[ExperienceRequirement] = []
    patterns = (
        re.compile(
            r"\b(?P<minimum>\d{1,2})\s*(?:-|–|to)\s*(?P<maximum>\d{1,2})"
            r"\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+|professional\s+)?experience\b"
        ),
        re.compile(
            r"\b(?:minimum(?:\s+of)?|at\s+least)\s+(?P<minimum>\d{1,2})"
            r"\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+|professional\s+)?experience\b"
        ),
        re.compile(
            r"\b(?P<minimum>\d{1,2})\s*\+\s*(?:years?|yrs?)\s+"
            r"(?:of\s+)?(?:relevant\s+|professional\s+)?experience\b"
        ),
        re.compile(
            r"\b(?P<minimum>\d{1,2})\s*(?:years?|yrs?)\s+"
            r"(?:of\s+)?(?:relevant\s+|professional\s+)?experience\b"
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(t):
            context = t[max(0, match.start() - 80) : match.end() + 40]
            if re.search(r"\b(?:company|organization|business)\s+(?:has|with|over)\b", context):
                continue
            minimum = int(match.group("minimum"))
            maximum_value = match.groupdict().get("maximum")
            maximum = int(maximum_value) if maximum_value else None
            matches.append(ExperienceRequirement(minimum, maximum))
    if not matches:
        return None
    return max(
        matches,
        key=lambda item: (
            item.minimum_years,
            item.maximum_years or item.minimum_years,
        ),
    )


def extract_required_yoe(text: str) -> int | None:
    requirement = extract_required_yoe_range(text)
    if requirement is None:
        return None
    return requirement.maximum_years or requirement.minimum_years
