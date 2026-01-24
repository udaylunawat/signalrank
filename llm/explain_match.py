# llm/explain_match.py
from llm.client import llm_json

MATCH_PROMPT = """
Resume skills:
{resume}

Job skills:
{job}

Explain in ONE sentence why this job is a good fit.

Return JSON exactly in this form:
{{ "explanation": "..." }}
"""

NO_MATCH_PROMPT = """
Resume skills:
{resume}

Job skills:
{job}

Explain in ONE sentence why this job is NOT a good fit.
Be honest but neutral.

Return JSON exactly in this form:
{{ "explanation": "..." }}
"""


def explain_match(resume_skills, job_skills):
    prompt = MATCH_PROMPT.format(
        resume=", ".join(resume_skills),
        job=", ".join(job_skills),
    )
    data = llm_json(prompt)
    return data.get("explanation", "")


def explain_no_match(resume_skills, job_skills):
    prompt = NO_MATCH_PROMPT.format(
        resume=", ".join(resume_skills),
        job=", ".join(job_skills),
    )
    data = llm_json(prompt)
    return data.get("explanation", "")