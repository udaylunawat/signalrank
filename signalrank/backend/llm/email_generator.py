import logging
import re
from dataclasses import dataclass

from llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Write concise recruiter outreach using only facts from the candidate resume and job description.

Rules:
- Do not assume a profession, industry, seniority, location, or technology.
- Never invent experience, metrics, qualifications, or personal details.
- Write a specific subject and a body under 120 words.
- Address the supplied recipient naturally; use "Hiring team" when no name is supplied.
- Mention the exact role and company.
- Lead with one or two truthful achievements that are relevant to this role.
- End with a low-pressure request to connect. Do not include a signature.
- Avoid filler such as "I hope this finds you well" or unsupported claims of being a perfect fit.

Respond exactly in this format:
SUBJECT: <subject line>
BODY:
<plain-text email body>
"""


class EmailGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedEmail:
    subject: str
    body: str


def _parse_response(text: str) -> GeneratedEmail:
    subject_match = re.search(r"^SUBJECT:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    body_match = re.search(r"^BODY:\s*\n([\s\S]+)$", text, re.IGNORECASE | re.MULTILINE)
    subject = subject_match.group(1).strip() if subject_match else ""
    body = body_match.group(1).strip() if body_match else ""
    if not subject or not body:
        raise EmailGenerationError("OpenRouter returned an incomplete outreach email")
    return GeneratedEmail(subject=subject, body=body)


async def generate_email(
    *,
    resume_text: str,
    job_description: str,
    company: str,
    role: str,
    recipient_name: str,
    job_url: str | None,
    llm: OpenRouterClient,
) -> GeneratedEmail:
    recipient = recipient_name.strip() or "Hiring team"
    user_message = (
        f"RECIPIENT: {recipient}\n"
        f"COMPANY: {company}\n"
        f"ROLE: {role}\n"
        f"JOB URL: {job_url or 'Not provided'}\n\n"
        f"CANDIDATE RESUME:\n{resume_text[:8000]}\n\n"
        f"JOB DESCRIPTION:\n{job_description[:4000]}"
    )
    response = await llm.llm_text(
        SYSTEM_PROMPT,
        user_message,
        max_tokens=500,
        temperature=0.2,
    )
    if not response.strip():
        details = llm.last_error.details if llm.last_error else "No usable response"
        raise EmailGenerationError(details)
    email = _parse_response(response)
    logger.info("Generated outreach for %s at %s", role, company)
    return email
