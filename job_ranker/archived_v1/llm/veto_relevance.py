# ================================
# FILE: llm/veto_relevance.py
# ================================
from typing import List

from llm.client import llm_json


# --------------------------------------------------
# PROMPT GENERATION
# --------------------------------------------------
def build_veto_prompt(*, role_intent: str) -> str:
    """
    Generate an LLM veto question from user profile intent.
    """

    intent = role_intent.lower()

    if "strategy" in intent or "innovation" in intent:
        question = (
            "Is this role primarily focused on strategy, innovation leadership, "
            "product direction, architecture decisions, or digital transformation — "
            "rather than hands-on day-to-day software development or ML implementation?"
        )

    elif "product" in intent:
        question = (
            "Is this role fundamentally a product, platform, or solution ownership role "
            "with technical depth, rather than a pure engineering execution role?"
        )

    elif "ai" in intent or "ml" in intent:
        question = (
            "Is this role fundamentally a hands-on AI, Machine Learning, "
            "MLOps, LLMOps, or Agentic AI engineering role?"
        )

    else:
        # Safe default
        question = (
            "Is this role fundamentally aligned with the resume summary provided?"
        )

    return f"""
You are validating job relevance.

Resume summary:
{{resume}}

Job description:
{{job}}

Question:
{question}

Answer ONLY with JSON:
{{ "relevant": true | false }}
"""


# --------------------------------------------------
# MAIN ENTRYPOINT
# --------------------------------------------------
def apply_llm_veto(
    *,
    resume_summary: str,
    job_descriptions: List[str],
    role_intent: str,
    max_tokens: int = 200,
    logger=None,
) -> List[bool]:
    """
    Conservative, schema-hardened LLM veto.

    - Never throws
    - Never vetoes on ambiguity
    - Only vetoes on explicit false
    """

    prompt = build_veto_prompt(role_intent=role_intent)
    results: List[bool] = []

    for idx, desc in enumerate(job_descriptions):
        try:
            raw = llm_json(
                prompt.format(
                    resume=resume_summary[:1500],
                    job=desc[:2000],
                ),
                max_tokens=max_tokens,
            )

            # ----------------------------
            # CASE 1: Proper dict response
            # ----------------------------
            if isinstance(raw, dict):
                val = raw.get("relevant")
                if isinstance(val, bool):
                    results.append(val)
                    continue

            # ----------------------------
            # CASE 2: Model returned string
            # ----------------------------
            if isinstance(raw, str):
                t = raw.strip().lower()
                if "false" in t:
                    results.append(False)
                    continue
                if "true" in t:
                    results.append(True)
                    continue

            # ----------------------------
            # CASE 3: Any ambiguity
            # ----------------------------
            if logger:
                logger.warning(
                    f"[LLM VETO] Ambiguous output on item {idx}, allowing job"
                )
            results.append(True)

        except Exception as e:
            if logger:
                logger.warning(f"[LLM VETO] Exception on item {idx}, allowing job: {e}")
            results.append(True)

    return results
