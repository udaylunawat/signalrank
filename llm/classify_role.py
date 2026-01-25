# llm/classify_role.py
import hashlib
import json
from pathlib import Path
from typing import List

from llm.client import llm_json

# --------------------------------------------------
# CACHE
# --------------------------------------------------
CACHE_DIR = Path("cache/role_classification")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_TTL = 7 * 24 * 3600  # 7 days


# --------------------------------------------------
# FAST HEURISTICS
# --------------------------------------------------
def _fast_role(title: str) -> str | None:
    t = title.lower()

    if any(k in t for k in ["intern", "junior", "graduate", "entry"]):
        return "junior"

    if any(k in t for k in [
        "manager", "lead", "head", "director", "principal manager"
    ]):
        return "manager"

    if any(k in t for k in [
        "engineer", "developer", "scientist", "architect", "researcher"
    ]):
        return "individual_contributor"

    return None


def _cache_key(title: str) -> Path:
    h = hashlib.md5(title.strip().lower().encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


# --------------------------------------------------
# LLM PROMPT
# --------------------------------------------------
PROMPT = """
You are classifying job titles.

For EACH item below, return exactly one role:
- junior
- individual_contributor
- manager

Rules:
- Preserve ordering
- Do NOT add or remove items
- Use the provided index

Return JSON exactly:
{
  "roles": {
    "0": "...",
    "1": "...",
    "2": "..."
  }
}

ITEMS:
<<<ITEMS>>>
"""


# --------------------------------------------------
# MAIN ENTRY
# --------------------------------------------------
def classify_roles_batch(
    titles: List[str],
    batch_size: int = 10,
    logger=None,
) -> List[str]:
    """
    Fast, cached, deterministic role classification.
    Guarantees len(output) == len(titles).
    """

    roles: List[str] = [None] * len(titles)
    llm_needed = []
    llm_indices = []

    # ---------- pass 1: heuristics + cache ----------
    for i, title in enumerate(titles):
        if not isinstance(title, str) or not title.strip():
            roles[i] = "individual_contributor"
            continue

        # heuristic
        fast = _fast_role(title)
        if fast:
            roles[i] = fast
            continue

        # cache
        cache_path = _cache_key(title)
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                roles[i] = data.get("role", "individual_contributor")
                continue
            except Exception:
                pass

        llm_needed.append(title)
        llm_indices.append(i)

    # ---------- pass 2: LLM only for unknowns ----------
    for i in range(0, len(llm_needed), batch_size):
        batch = llm_needed[i : i + batch_size]
        batch_idxs = llm_indices[i : i + batch_size]

        items = "\n".join(
            f"{j}: {t}" for j, t in enumerate(batch)
        )

        try:
            data = llm_json(PROMPT.replace("<<<ITEMS>>>", items))
            raw = data.get("roles", {})

            for j, original_idx in enumerate(batch_idxs):
                role = raw.get(str(j), "individual_contributor")
                roles[original_idx] = role

                # write cache
                _cache_key(titles[original_idx]).write_text(
                    json.dumps({"role": role})
                )

        except Exception as e:
            if logger:
                logger.warning(f"Role LLM failed, fallback IC: {e}")
            for original_idx in batch_idxs:
                roles[original_idx] = "individual_contributor"

    # ---------- final safety ----------
    for i, r in enumerate(roles):
        if r not in {"junior", "manager", "individual_contributor"}:
            roles[i] = "individual_contributor"

    return roles