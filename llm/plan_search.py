# ================================
# FILE: llm/plan_search.py
# ================================
from llm.client import llm_json
import re
from types import SimpleNamespace


# --------------------------------------------------
# CONFIG NORMALIZATION
# --------------------------------------------------
def _to_namespace(obj):
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_namespace(x) for x in obj]
    return obj


# --------------------------------------------------
# HELPERS (PURE MECHANICS)
# --------------------------------------------------
def _normalize_query(q: str, normalization: dict[str, str]) -> str:
    q = q.lower().strip()
    for src, dst in normalization.items():
        q = re.sub(rf"\b{re.escape(src)}\b", dst, q)
    q = re.sub(r"\s+", " ", q)
    return q


def _is_valid_query(
    q: str,
    *,
    anchors: set[str],
    invalid_tokens: set[str],
    min_length: int,
) -> bool:
    if len(q) < min_length:
        return False

    if q in invalid_tokens:
        return False

    if anchors and not any(a in q for a in anchors):
        return False

    return True


def is_google_style_query(q: str) -> bool:
    q = q.strip().lower()
    if " or " in q or "|" in q:
        return False
    if len(q.split()) < 3:
        return False
    return True


# --------------------------------------------------
# MAIN (CONFIG-DRIVEN)
# --------------------------------------------------
def plan_search_queries(
    text: str,
    *,
    effective_settings,
) -> list[str]:
    """
    Fully config-driven query planner.
    Zero domain assumptions in code.
    """

    cfg = _to_namespace(effective_settings)

    search_cfg = getattr(cfg, "search", None)
    if search_cfg is None:
        return []

    prompt = getattr(search_cfg, "prompt", None)
    if not prompt:
        return []

    anchors = {
        a.lower()
        for a in getattr(search_cfg, "anchors", [])
        if isinstance(a, str)
    }

    invalid_tokens = {
        t.lower()
        for t in getattr(search_cfg, "invalid_tokens", [])
        if isinstance(t, str)
    }

    raw_norm = getattr(search_cfg, "normalization", None)

    if raw_norm is None:
        normalization = {}
    elif isinstance(raw_norm, dict):
        normalization = {
            k.lower(): v.lower()
            for k, v in raw_norm.items()
        }
    else:
        # SimpleNamespace
        normalization = {
            k.lower(): str(v).lower()
            for k, v in vars(raw_norm).items()
        }

    min_length = getattr(search_cfg, "min_query_length", 6)

    # ----------------------------------------------
    # Pass-through for literal queries
    # ----------------------------------------------
    if is_google_style_query(text):
        return [text.strip().lower()]

    # ----------------------------------------------
    # LLM expansion
    # ----------------------------------------------
    data = llm_json(prompt.replace("<<<TEXT>>>", text))
    raw = data.get("queries", [])

    if not isinstance(raw, list):
        return []

    seen = set()
    out = []

    for q in raw:
        if not isinstance(q, str):
            continue

        qn = _normalize_query(q, normalization)

        if not _is_valid_query(
            qn,
            anchors=anchors,
            invalid_tokens=invalid_tokens,
            min_length=min_length,
        ):
            continue

        if qn not in seen:
            seen.add(qn)
            out.append(qn)

    return out