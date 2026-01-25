# llm/classify_functional_role.py
from llm.client import llm_json

PROMPT = """
Classify the FUNCTIONAL ROLE of each job.

Choose exactly one:
- ai_ml_core
- agentic_systems
- mlops_llmops
- platform_devops
- sre
- security
- data_science
- software_general

Return JSON:
{ "roles": [...] }

The number of roles MUST exactly match the number of inputs.

JOBS:
<<<TEXT>>>
"""

def classify_functional_roles_batch(texts, batch_size=6, logger=None):
    roles = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        try:
            data = llm_json(
                PROMPT.replace("<<<TEXT>>>", "\n\n".join(batch)),
                max_tokens=400,
            )
            batch_roles = data.get("roles", [])

            if not isinstance(batch_roles, list) or len(batch_roles) != len(batch):
                raise ValueError("Length mismatch")

        except Exception as e:
            if logger:
                logger.warning(f"Functional role LLM failed, fallback software_general: {e}")
            batch_roles = ["software_general"] * len(batch)

        roles.extend(batch_roles)

    if len(roles) != len(texts):
        roles = ["software_general"] * len(texts)

    return roles