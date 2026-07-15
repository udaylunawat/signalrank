import logging
import re
from dataclasses import dataclass, field

from llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)
RESUME_PARSER_VERSION = "resume-parser-v2"

EXTRACTION_PROMPT = """Extract structured data from this resume. Return JSON only with these keys:
- skills: list of technical skills (strings)
- years_of_experience: integer or null
- recent_titles: list of recent job titles (strings)
- industries: list of industries worked in (strings)
- education: list of degrees/certifications (strings)

Be concise. No explanations.

RESUME:
{resume_text}"""

RESUME_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "years_of_experience": {"type": ["integer", "null"]},
        "recent_titles": {"type": "array", "items": {"type": "string"}},
        "industries": {"type": "array", "items": {"type": "string"}},
        "education": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "skills",
        "years_of_experience",
        "recent_titles",
        "industries",
        "education",
    ],
    "additionalProperties": False,
}

_SECTION_END = re.compile(
    r"^(?:professional\s+experience|experience|employment|education|certifications?|projects?)\s*$",
    re.I,
)
_TITLE_MARKER = re.compile(
    r"\b(?:accountant|administrator|analyst|architect|associate|consultant|"
    r"coordinator|designer|developer|director|engineer|executive|lead|manager|"
    r"officer|owner|producer|recruiter|researcher|scientist|specialist|teacher|"
    r"tester|writer)\b",
    re.I,
)
_SKILL_CATEGORY = re.compile(
    r"^(?:languages?|automation|testing\s+types?|manual\s+testing|api\s+testing|"
    r"databases?|version\s+control|ai\s+tools?|frameworks?|tools?|technologies?|"
    r"platforms?|methodologies?)\s+",
    re.I,
)
_TRAILING_LOCATION = re.compile(
    r"\s+(?:(?:[A-Z][A-Za-z.'-]+),\s*)?"
    r"(?:India|United States|USA|US|United Kingdom|UK|Canada|Australia|Germany|"
    r"France|Singapore|Remote)\s*$",
)


def _repair_extracted_text(value: str) -> str:
    repairs = {
        "W eb": "Web",
        "T esting": "Testing",
        "T ester": "Tester",
        "F unctional": "Functional",
        "V ersion": "Version",
        "T ools": "Tools",
    }
    for broken, repaired in repairs.items():
        value = value.replace(broken, repaired)
    return re.sub(r"\s+", " ", value).strip()


@dataclass
class ResumeParseResult:
    skills: list[str] = field(default_factory=list)
    years_of_experience: int | None = None
    recent_titles: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    status: str = "complete"
    confidence: float = 1.0
    source: str = "llm"
    model: str | None = None
    error: str | None = None


def _validate_extraction(data: dict) -> ResumeParseResult:
    if "_error" in data:
        return ResumeParseResult(
            status="degraded",
            confidence=0.0,
            source="none",
            error=str(data.get("_details") or data.get("_error")),
        )

    def to_list(val) -> list[str]:
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        if isinstance(val, str):
            return [val.strip()] if val.strip() else []
        return []

    def to_int(val) -> int | None:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    return ResumeParseResult(
        skills=to_list(data.get("skills")),
        years_of_experience=to_int(data.get("years_of_experience")),
        recent_titles=to_list(data.get("recent_titles")),
        industries=to_list(data.get("industries")),
        education=to_list(data.get("education")),
    )


def _dedupe(values: list[str], limit: int = 30) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip(" \t,;:|•-")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            result.append(cleaned)
            seen.add(key)
        if len(result) >= limit:
            break
    return result


def _heuristic_skills(resume_text: str) -> list[str]:
    lines = [line.strip() for line in resume_text.splitlines()]
    skills: list[str] = []
    in_skills = False
    for line in lines:
        line = _repair_extracted_text(line)
        if re.match(r"^(?:technical\s+)?skills(?:\s+summary)?\s*$", line, re.I):
            in_skills = True
            continue
        if in_skills and _SECTION_END.match(line):
            break
        if not in_skills:
            match = re.search(
                r"\b(?:skilled|proficient|experienced)\s+in\s+(.+)", line, re.I
            )
            if match:
                skills.extend(re.split(r",|;|\band\b", match.group(1)))
            continue
        value = _SKILL_CATEGORY.sub("", line)
        skills.extend(re.split(r",|;|\||\s{2,}", value))
    return _dedupe([_repair_extracted_text(skill) for skill in skills])


def _heuristic_titles(resume_text: str) -> list[str]:
    candidates: list[str] = []
    for line in resume_text.splitlines():
        cleaned = _repair_extracted_text(line).strip(" \t|•-")
        words = cleaned.split()
        if not 1 < len(words) <= 10 or not _TITLE_MARKER.search(cleaned):
            continue
        if "@" in cleaned or re.search(r"\d{4}|\+?\d[\d -]{7,}", cleaned):
            continue
        candidates.append(_TRAILING_LOCATION.sub("", cleaned).strip())
    return _dedupe(candidates, limit=8)


def _heuristic_parse(resume_text: str) -> ResumeParseResult:
    years = None
    matches = [
        int(value)
        for value in re.findall(r"\b(\d{1,2})(?:\+)?\s+years?\b", resume_text, re.I)
        if 0 < int(value) < 60
    ]
    if matches:
        years = max(matches)
    skills = _heuristic_skills(resume_text)
    titles = _heuristic_titles(resume_text)
    populated = int(bool(skills)) + int(bool(titles)) + int(years is not None)
    return ResumeParseResult(
        skills=skills,
        years_of_experience=years,
        recent_titles=titles,
        status="degraded",
        confidence=round(populated / 3 * 0.7, 2),
        source="heuristic",
    )


def _merge_with_fallback(
    primary: ResumeParseResult,
    fallback: ResumeParseResult,
) -> ResumeParseResult:
    used_fallback = (
        not primary.skills
        or not primary.recent_titles
        or primary.years_of_experience is None
    )
    result = ResumeParseResult(
        skills=primary.skills or fallback.skills,
        years_of_experience=(
            primary.years_of_experience
            if primary.years_of_experience is not None
            else fallback.years_of_experience
        ),
        recent_titles=primary.recent_titles or fallback.recent_titles,
        industries=primary.industries,
        education=primary.education,
        status="degraded" if primary.error or used_fallback else "complete",
        confidence=(
            max(primary.confidence, fallback.confidence)
            if primary.error
            else (0.85 if used_fallback else 1.0)
        ),
        source="heuristic" if primary.error else ("hybrid" if used_fallback else "llm"),
        model=primary.model,
        error=primary.error,
    )
    return result


async def parse_resume(
    resume_text: str,
    llm_client: OpenRouterClient,
) -> ResumeParseResult:
    prompt = EXTRACTION_PROMPT.format(resume_text=resume_text[:10000])
    fallback = _heuristic_parse(resume_text)
    try:
        data = await llm_client.llm_json(
            prompt,
            max_tokens=700,
            response_schema=RESUME_EXTRACTION_SCHEMA,
        )
        parsed = _validate_extraction(data)
        parsed.model = getattr(llm_client, "last_model", None)
        return _merge_with_fallback(parsed, fallback)
    except Exception as exc:
        logger.exception("Resume parse failed — using deterministic fallback")
        fallback.error = f"{type(exc).__name__}: {exc}"
        fallback.model = getattr(llm_client, "last_model", None)
        return fallback
