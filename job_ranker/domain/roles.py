"""
PORT FROM v1:
- llm/classify_functional_role.py
- core functional role logic
"""

# domain/roles.py
# domain/roles.py


def classify_functional_role(text: str, cfg: dict) -> str:
    t = (text or "").lower()

    taxonomy = cfg.get("functional_role_taxonomy", {})
    thresholds = cfg.get("functional_role_thresholds", {})

    # Explicit taxonomy wins
    for role, block in taxonomy.items():
        for kw in block.get("keywords", []):
            if kw in t:
                return role

    terms = cfg.get("functional_role_terms", {})

    ai_terms = terms.get("ai", [])
    devops_terms = terms.get("devops", [])
    security_terms = terms.get("security", [])

    ai = sum(k in t for k in ai_terms)
    devops = sum(k in t for k in devops_terms)
    sec = sum(k in t for k in security_terms)
    thresholds = cfg.get("functional_role_thresholds", {})

    if sec >= thresholds.get("security_min_terms"):
        return "security"
    if ai >= thresholds.get("agentic_min_terms"):
        return "agentic_systems"
    if ai >= thresholds.get("mlops_ai_terms") and devops >= thresholds.get(
        "mlops_devops_terms"
    ):
        return "mlops_llmops"
    if devops >= thresholds.get("platform_devops_min_terms"):
        return "platform_devops"

    return "software_general"
