from llm.client import llm_json

REQUIRED_KEYS = [
    "core_capabilities",
    "primary_focus",
    "secondary_skills",
    "non_focus",
    "seniority_signals",
    "target_roles",
]

PROMPT = """
You are converting a resume into a compact semantic profile for job matching.

Return JSON with keys:
- core_capabilities
- primary_focus
- secondary_skills
- non_focus
- seniority_signals
- target_roles

Be concise. No filler.

RESUME:
<<<TEXT>>>
"""


def distill_resume(resume_text: str) -> dict:
    data = llm_json(
        PROMPT.replace("<<<TEXT>>>", resume_text),
        max_tokens=700,
    )

    # ---------- schema hardening ----------
    safe = {}
    for k in REQUIRED_KEYS:
        v = data.get(k, [])
        if not isinstance(v, list):
            v = []
        safe[k] = [str(x).strip() for x in v if str(x).strip()]

    return safe
