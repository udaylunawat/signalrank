# ================================
# FILE: skills/canonicalizer.py
# ================================
from typing import Iterable, Dict, Set


# --------------------------------------------------
# INTERNAL CACHE (fingerprint → variant_map)
# --------------------------------------------------
_VARIANT_MAP_CACHE: Dict[str, Dict[str, str]] = {}


# --------------------------------------------------
# INTERNAL: build variant lookup
# --------------------------------------------------
def _build_variant_lookup(equivalence_groups: dict) -> Dict[str, str]:
    """
    Build mapping: variant -> canonical
    Deterministic, lowercase-only.
    """
    lookup: Dict[str, str] = {}

    for _, group in equivalence_groups.items():
        canonical = group.get("canonical")
        variants = group.get("variants", [])

        if not canonical:
            continue

        canon = canonical.strip().lower()

        # canonical maps to itself
        lookup[canon] = canon

        for v in variants:
            if not isinstance(v, str):
                continue
            lookup[v.strip().lower()] = canon

    return lookup


# --------------------------------------------------
# PUBLIC API
# --------------------------------------------------
def canonicalize_skills(
    raw_skills: Iterable[str],
    *,
    effective_settings: dict,
    cfg_fingerprint: str,
) -> Set[str]:
    """
    Canonicalize raw skills using config-driven equivalence groups.

    - Deterministic
    - Config-driven
    - Cached per config fingerprint
    - Safe for resume + job usage
    """

    if not raw_skills:
        return set()

    skills_cfg = effective_settings.get("skills", {})
    groups = skills_cfg.get("equivalence_groups", {})

    if not groups:
        return {
            s.strip().lower()
            for s in raw_skills
            if isinstance(s, str)
        }

    # --------------------------------------------------
    # Get or build cached variant map
    # --------------------------------------------------
    variant_map = _VARIANT_MAP_CACHE.get(cfg_fingerprint)
    if variant_map is None:
        variant_map = _build_variant_lookup(groups)
        _VARIANT_MAP_CACHE[cfg_fingerprint] = variant_map

    canon: Set[str] = set()

    for s in raw_skills:
        if not isinstance(s, str):
            continue
        key = s.strip().lower()
        canon.add(variant_map.get(key, key))

    return canon

def canonicalize_and_dedupe(
    raw_skills,
    *,
    effective_settings: dict,
    cfg_fingerprint: str,
):
    """
    Canonicalize first, then dedupe.
    This is the ONLY correct order.
    """
    canon = canonicalize_skills(
        raw_skills,
        effective_settings=effective_settings,
        cfg_fingerprint=cfg_fingerprint,
    )
    return sorted(canon)

# --------------------------------------------------
# SHARED CANONICAL TEXT BUILDER (FAISS + RANKING)
# --------------------------------------------------
def build_canonical_texts(
    texts: list[str],
    *,
    effective_settings: dict,
    cfg_fingerprint: str,
):
    """
    Single source of truth for:
    - skill extraction
    - canonicalization
    - embedding text

    Used by:
    - build_faiss_corpus.py
    - match_engine.py
    - rank_corpus.py
    """
    from llm.normalize_skills import normalize_skills_batch

    raw_skills = normalize_skills_batch(
        texts,
        effective_settings=effective_settings,
    )

    canonical_texts = []
    canonical_skill_sets = []

    for skills in raw_skills:
        canon = canonicalize_and_dedupe(
            skills,
            effective_settings=effective_settings,
            cfg_fingerprint=cfg_fingerprint,
        )
        canonical_skill_sets.append(canon)
        canonical_texts.append(" ".join(canon))

    return canonical_texts, canonical_skill_sets