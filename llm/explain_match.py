# llm/explain_match.py
from llm.client import llm_json

BATCH_PROMPT = """
You are explaining job matches.

Resume skills:
{resume}

For EACH job below, produce ONE sentence explanation.

Return JSON exactly:
{{ "explanations": [ "...", "..." ] }}

JOBS:
{jobs}
"""

def explain_matches_batch(resume_skills, jobs_skills):
    job_blocks = []
    for i, skills in enumerate(jobs_skills):
        job_blocks.append(
            f"Job {i+1}: {', '.join(skills)}"
        )

    prompt = BATCH_PROMPT.format(
        resume=", ".join(resume_skills),
        jobs="\n".join(job_blocks),
    )

    data = llm_json(prompt, max_tokens=300)
    exps = data.get("explanations", [])

    if not isinstance(exps, list):
        return [""] * len(jobs_skills)

    return exps