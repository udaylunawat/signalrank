"""
PORT FROM v1:
- skills/canonicalizer.py
- llm/normalize_skills.py
"""

# domain/skills.py
from __future__ import annotations

from typing import Dict, Iterable, Set


def _build_variant_lookup(groups: dict) -> Dict[str, str]:
    lookup: Dict[str, str] = {}

    for group in groups.values():
        canonical = group.get("canonical")
        variants = group.get("variants", [])
        if not canonical:
            continue

        canon = canonical.lower().strip()
        lookup[canon] = canon

        for v in variants:
            if isinstance(v, str):
                lookup[v.lower().strip()] = canon

    return lookup


class SkillCanonicalizer:
    """
    Deterministic skill canonicalization.

    RULES:
    - config-driven only
    - no ML
    - canonicalize → dedupe (order matters)
    """

    def __init__(self, cfg: dict):
        skills_cfg = cfg.get("skills", {})
        groups = skills_cfg.get("equivalence_groups", {})
        self.lookup = _build_variant_lookup(groups)

    def canonicalize(self, raw: Iterable[str]) -> Set[str]:
        out: Set[str] = set()

        for s in raw or []:
            if not isinstance(s, str):
                continue
            key = s.lower().strip()
            out.add(self.lookup.get(key, key))

        return out

    def canonicalize_and_join(self, raw: Iterable[str]) -> str:
        return " ".join(sorted(self.canonicalize(raw)))
