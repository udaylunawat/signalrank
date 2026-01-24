from llm.client import llm_json

PROMPT = """
Extract normalized skill families for each text.

Return JSON:
{ "skills": [ [...], [...]] }

TEXTS:
<<<TEXT>>>
"""


def normalize_skills_batch(texts, batch_size=8, logger=None):
    all_skills = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            data = llm_json(
                PROMPT.replace("<<<TEXT>>>", "\n\n".join(batch))
            )
            all_skills.extend(data.get("skills", [[]] * len(batch)))
        except Exception as e:
            if logger:
                logger.debug(f"Skill LLM failed, fallback empty: {e}")
            all_skills.extend([[] for _ in batch])

    return all_skills