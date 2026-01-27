# ================================
# FILE: fast_heuristics.py
# ================================
import re
from typing import Iterable, List, Dict, Set


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------
def _normalize_text(text: str) -> str:
    """
    Deterministic text normalization for phrase matching.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\+\-\. ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# --------------------------------------------------
# SKILL PHRASE MATCHER (CONFIG-DRIVEN)
# --------------------------------------------------
def extract_skills_fast(
    text: str,
    *,
    equivalence_groups: Dict,
) -> List[str]:
    """
    Deterministic skill phrase extractor.

    Properties:
    - Phrase-based (not token-based)
    - Config-driven (skills.equivalence_groups)
    - LLM-free
    - High precision
    - Stable across runs

    Returns:
    - List of matched raw skill variants (lowercase)
    """

    if not text or not equivalence_groups:
        return []

    norm_text = _normalize_text(text)

    matched: Set[str] = set()

    for group in equivalence_groups.values():
        variants = group.get("variants", [])
        for v in variants:
            if not isinstance(v, str):
                continue

            phrase = v.strip().lower()
            if not phrase:
                continue

            # Word-boundary safe phrase match
            pattern = r"\b" + re.escape(phrase) + r"\b"
            if re.search(pattern, norm_text):
                matched.add(phrase)

    return sorted(matched)


# --------------------------------------------------
# FUNCTIONAL ROLE HEURISTICS (UNCHANGED)
# --------------------------------------------------
AI_TERMS = {
    "llm", "agent", "agents", "rag", "embedding",
    "prompt", "inference", "evaluation", "orchestration",
    "langchain", "langgraph", "vector",
}

DEVOPS_TERMS = {
    "kubernetes", "terraform", "ci/cd", "pipeline",
    "monitoring", "grafana", "prometheus",
    "sre", "availability", "mttr",
}

SECURITY_TERMS = {
    "threat", "siem", "soc", "incident",
    "attack", "mitre", "edr", "forensics",
}

def classify_functional_role_fast(text: str) -> str:
    t = text.lower() if isinstance(text, str) else ""

    ai = sum(1 for k in AI_TERMS if k in t)
    devops = sum(1 for k in DEVOPS_TERMS if k in t)
    sec = sum(1 for k in SECURITY_TERMS if k in t)

    if sec >= 2:
        return "security"
    if ai >= 3:
        return "agentic_systems"
    if ai >= 1 and devops >= 1:
        return "mlops_llmops"
    if devops >= 2:
        return "platform_devops"
    return "software_general"