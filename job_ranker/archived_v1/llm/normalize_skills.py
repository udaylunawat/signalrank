# ================================
# FILE: llm/normalize_skills.py
# ================================
"""
Deterministic, config-driven skill extraction.

Rules:
- No heuristics
- No ML
- No external dependencies
- Only matches phrases defined in skills.equivalence_groups
"""

from typing import List


def _build_phrase_index(equivalence_groups: dict):
    """
    Build phrase → canonical mapping.
    """
    phrases = {}
    for group in equivalence_groups.values():
        canonical = group.get("canonical")
        variants = group.get("variants", [])
        if not canonical:
            continue
        canon = canonical.lower()
        phrases[canon] = canon
        for v in variants:
            if isinstance(v, str):
                phrases[v.lower()] = canon
    return phrases


def normalize_skills_batch(
    texts: List[str],
    *,
    effective_settings: dict,
    logger=None,
):
    """
    Extract skills by exact phrase matching against config.
    """

    skills_cfg = effective_settings.get("skills", {})
    groups = skills_cfg.get("equivalence_groups", {})

    if not groups:
        return [[] for _ in texts]

    phrase_map = _build_phrase_index(groups)

    out = []
    for text in texts:
        if not isinstance(text, str):
            out.append([])
            continue

        t = text.lower()
        found = set()

        for phrase, canonical in phrase_map.items():
            if phrase in t:
                found.add(canonical)

        out.append(sorted(found))

    return out
