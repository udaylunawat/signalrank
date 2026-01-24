from llm.client import llm_json

PROMPT = """
Classify job titles into:
- junior
- individual_contributor
- manager

Return JSON list:
{ "roles": [...] }

TITLES:
<<<TITLES>>>
"""


def classify_roles_batch(titles, batch_size=10, logger=None):
    roles = []

    for i in range(0, len(titles), batch_size):
        batch = titles[i : i + batch_size]
        try:
            data = llm_json(
                PROMPT.replace("<<<TITLES>>>", "\n".join(batch))
            )
            roles.extend(data.get("roles", ["individual_contributor"] * len(batch)))
        except Exception as e:
            if logger:
                logger.debug(f"Role LLM failed, fallback IC: {e}")
            roles.extend(["individual_contributor"] * len(batch))

    return roles