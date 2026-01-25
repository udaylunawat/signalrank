# llm/classify_functional_role.py
from fast_heuristics import classify_functional_role_fast

def classify_functional_roles_batch(texts, batch_size=64, logger=None):
    """
    Heuristic-only functional role classification.
    LLM removed permanently to avoid batch stalls.
    """

    roles = []

    for i, text in enumerate(texts):
        role = classify_functional_role_fast(text)
        roles.append(role)

        # progress log every 100 items
        if logger and (i + 1) % 100 == 0:
            logger.info(
                f"[RANK] Functional role classified: {i + 1}/{len(texts)}"
            )

    return roles



# # llm/classify_functional_role.py
# from fast_heuristics import classify_functional_role_fast
# from llm.client import llm_json

# PROMPT = """
# Classify functional role:
# - ai_ml_core
# - agentic_systems
# - mlops_llmops
# - platform_devops
# - sre
# - security
# - software_general

# Return JSON:
# { "role": "..." }

# TEXT:
# <<<TEXT>>>
# """

# def classify_functional_roles_batch(texts, batch_size=6, logger=None):
#     roles = []

#     for text in texts:
#         fast = classify_functional_role_fast(text)
#         if fast != "software_general":
#             roles.append(fast)
#             continue

#         # LLM fallback only when ambiguous
#         try:
#             data = llm_json(PROMPT.replace("<<<TEXT>>>", text), max_tokens=50)
#             roles.append(data.get("role", fast))
#         except Exception:
#             roles.append(fast)

#     return roles