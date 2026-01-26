# llm/plan_search.py
from llm.client import llm_json
import re

PROMPT = """
Generate job search queries from this role intent.

Rules:
- One role per query
- No OR operators
- Suitable for job boards
- Senior IC focused
- Use standard industry titles only

Return JSON:
{ "queries": [...] }

ROLE:
<<<TEXT>>>
"""

# --------------------------------------------------
# CANONICAL NORMALIZATION
# --------------------------------------------------
TERM_NORMALIZATION = {
    r"\bmloops\b": "mlops",
    r"\bml ops\b": "mlops",
    r"\bmops\b": "mlops",
    r"\bai ops\b": "ai ops",
    r"\bgen ai\b": "genai",
    r"\bllm ops\b": "llmops",
}

# Terms that should NEVER appear alone
INVALID_TOKENS = {
    "mops",
    "ops engineer",
    "ai engineer ops",
}

# Allowed role anchors (must contain at least one)
VALID_ANCHORS = {
    "mlops",
    "llmops",
    "genai",
    "machine learning",
    "ai engineer",
    "platform engineer",
}

def _normalize_query(q: str) -> str:
    q = q.lower().strip()

    for pattern, repl in TERM_NORMALIZATION.items():
        q = re.sub(pattern, repl, q)

    q = re.sub(r"\s+", " ", q)
    return q


def _is_valid_query(q: str) -> bool:
    # reject obvious garbage
    if len(q) < 6:
        return False

    if q in INVALID_TOKENS:
        return False

    # must contain at least one valid anchor
    if not any(a in q for a in VALID_ANCHORS):
        return False

    # reject malformed ops variants
    if re.search(r"\bmops\b", q):
        return False

    return True

def is_google_style_query(q: str) -> bool:
    """
    Google Jobs requires literal UI-style queries.
    Heuristics:
    - No OR operators
    - No pipe |
    - Short, natural-language phrases
    """
    q = q.strip().lower()

    if " or " in q:
        return False

    if "|" in q:
        return False

    # Google-style queries tend to be short phrases
    if len(q.split()) < 3:
        return False

    return True

def plan_search_queries(text: str) -> list[str]:
    # If user already supplied a Google-style query, pass through
    if is_google_style_query(text):
        return [text]

    data = llm_json(PROMPT.replace("<<<TEXT>>>", text))
    raw = data.get("queries", [])

    if not isinstance(raw, list):
        return []

    normalized = []
    seen = set()

    for q in raw:
        if not isinstance(q, str):
            continue

        qn = _normalize_query(q)

        if not _is_valid_query(qn):
            continue

        if qn not in seen:
            seen.add(qn)
            normalized.append(qn)

    return normalized