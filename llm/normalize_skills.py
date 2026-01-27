# ================================
# FILE: llm/normalize_skills.py
# ================================
from typing import List
from fast_heuristics import extract_skills_fast


def normalize_skills_batch(
    texts: List[str],
    *,
    effective_settings: dict,
    logger=None,
):
    """
    Batch skill extraction using config-driven phrase matcher.
    """
    skills_cfg = effective_settings.get("skills", {})
    groups = skills_cfg.get("equivalence_groups", {})
    if not groups:
        return [[] for _ in texts]
    out = []
    for t in texts:
        skills = extract_skills_fast(
            t,
            equivalence_groups=groups,
        )
        out.append(skills)

    return out