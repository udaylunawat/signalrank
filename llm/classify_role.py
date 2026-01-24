from llm.client import llm_json

PROMPT = """
Classify job titles into:
- junior
- individual_contributor
- manager

Return JSON list:
{ "roles": [...] }

The number of roles MUST exactly match the number of titles.

TITLES:
<<<TITLES>>>
"""


def classify_roles_batch(titles, batch_size=10, logger=None):
    """
    Length-safe role classification.
    Guarantees len(output) == len(titles)
    """
    roles = []

    for i in range(0, len(titles), batch_size):
        batch = titles[i : i + batch_size]
        batch_len = len(batch)

        try:
            data = llm_json(
                PROMPT.replace("<<<TITLES>>>", "\n".join(batch))
            )

            batch_roles = data.get("roles", [])

            # --- HARD SAFETY GUARARD ---
            if not isinstance(batch_roles, list):
                raise ValueError("roles is not a list")

            if len(batch_roles) != batch_len:
                if logger:
                    logger.warning(
                        f"Role LLM length mismatch: expected {batch_len}, got {len(batch_roles)}. Falling back."
                    )
                batch_roles = ["individual_contributor"] * batch_len

        except Exception as e:
            if logger:
                logger.debug(f"Role LLM failed, fallback IC: {e}")
            batch_roles = ["individual_contributor"] * batch_len

        roles.extend(batch_roles)

    # --- FINAL ASSERTION ---
    if len(roles) != len(titles):
        if logger:
            logger.error(
                f"CRITICAL: role list length {len(roles)} != titles length {len(titles)}. Forcing fallback."
            )
        roles = ["individual_contributor"] * len(titles)

    return roles