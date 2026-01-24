from llm.client import llm_json

MATCH_PROMPT = """
Resume skills:
{resume}

Job skills:
{job}

Explain in ONE sentence why this job is a good fit.
Return JSON:
{ "explanation": "..." }
"""

NO_MATCH_PROMPT = """
Resume skills:
{resume}

Job skills:
{job}

Explain in ONE sentence why this job is NOT a good fit.
Be honest but neutral.

Return JSON:
{ "explanation": "..." }
"""


def explain_match(resume_skills, job_skills):
    data = llm_json(
        MATCH_PROMPT.format(
            resume=", ".join(resume_skills),
            job=", ".join(job_skills),
        )
    )
    return data.get("explanation", "")


def explain_no_match(resume_skills, job_skills):
    data = llm_json(
        NO_MATCH_PROMPT.format(
            resume=", ".join(resume_skills),
            job=", ".join(job_skills),
        )
    )
    return data.get("explanation", "")