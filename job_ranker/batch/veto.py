"""
PORT FROM v1:
- llm/veto_relevance.py
"""

# batch/veto.py
from job_ranker.llm.client import llm_json


def cfg_section(cfg, name, default=None):
    if default is None:
        default = {}
    return cfg.get(name, default)


def apply_llm_veto(
    *,
    resume_summary: str,
    job_descriptions: list[str],
    role_intent: str,
    cfg: dict,
    logger=None,
):
    veto_cfg = cfg_section(cfg, "ranking", {}).get("llm_veto", {})
    if not veto_cfg.get("enabled", False):
        return [True] * len(job_descriptions)

    prompt = """
Resume summary:
{resume}

Job description:
{job}

Question:
Is this role fundamentally aligned with the resume?

Return JSON only:
{ "relevant": true | false }
"""

    results = []

    for idx, desc in enumerate(job_descriptions):
        try:
            out = llm_json(
                prompt.format(
                    resume=resume_summary[:1500],
                    job=desc[:2000],
                ),
                max_tokens=veto_cfg["model_max_tokens"],
            )
            val = out.get("relevant")
            results.append(bool(val) if isinstance(val, bool) else True)
        except Exception as e:
            if logger:
                logger.warning(f"[LLM VETO] allow on error: {e}")
            results.append(True)

    return results
