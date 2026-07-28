import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)
RESUME_PARSER_VERSION = "resume-parser-v4"

EXTRACTION_PROMPT = """Extract structured data from this resume. Return JSON only with these keys:
- skills: list of technical skills (strings)
- years_of_experience: integer or null
- recent_titles: list of recent job titles (strings)
- industries: list of industries worked in (strings)
- education: list of degrees/certifications (strings)
- skill_evidence: list of objects with name and an exact supporting resume excerpt
- experiences: list of objects with title, company, start_date, end_date,
  responsibilities, and an exact supporting resume excerpt
- declared_years_of_experience: integer or null; only when explicitly stated
- field_confidence: object with skills, experiences, titles, and years values in [0, 1]
- intent_suggestions: object with role_aliases (alternative names supported by the
  recent titles) and seniority_band (intern, entry, mid, senior, lead, manager,
  executive, or unknown)

`intent_suggestions` is career evidence only. Do not infer a target role,
required skills, preferred locations, salary, or job-search preference.
Do not invent dates, employers, titles, skills, or experience. Use null or an
empty list when evidence is absent. Evidence excerpts must occur verbatim in
the supplied resume. Copy date values exactly as written in the resume. Do not
calculate total experience; the application will derive it from the extracted
dates.

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
        "skill_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "evidence"],
                "additionalProperties": False,
            },
        },
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "start_date": {"type": ["string", "null"]},
                    "end_date": {"type": ["string", "null"]},
                    "responsibilities": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "evidence": {"type": "string"},
                },
                "required": [
                    "title",
                    "company",
                    "start_date",
                    "end_date",
                    "responsibilities",
                    "evidence",
                ],
                "additionalProperties": False,
            },
        },
        "declared_years_of_experience": {"type": ["integer", "null"]},
        "field_confidence": {
            "type": "object",
            "properties": {
                "skills": {"type": "number", "minimum": 0, "maximum": 1},
                "experiences": {"type": "number", "minimum": 0, "maximum": 1},
                "titles": {"type": "number", "minimum": 0, "maximum": 1},
                "years": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["skills", "experiences", "titles", "years"],
            "additionalProperties": False,
        },
        "intent_suggestions": {
            "type": "object",
            "properties": {
                "role_aliases": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 12,
                },
                "seniority_band": {
                    "type": "string",
                    "enum": [
                        "intern",
                        "entry",
                        "mid",
                        "senior",
                        "lead",
                        "manager",
                        "executive",
                        "unknown",
                    ],
                },
            },
            "required": ["role_aliases", "seniority_band"],
            "additionalProperties": False,
        },
    },
    "required": [
        "skills",
        "years_of_experience",
        "recent_titles",
        "industries",
        "education",
        "skill_evidence",
        "experiences",
        "declared_years_of_experience",
        "field_confidence",
        "intent_suggestions",
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
_EXPERIENCE_HEADER = re.compile(
    r"^(?:professional\s+experience|work\s+experience|experience|employment|"
    r"employment\s+history|work\s+history)\s*$",
    re.I,
)
_RESUME_SECTION_HEADER = re.compile(
    r"^(?:education|certifications?|projects?|publications?|awards?|"
    r"technical\s+skills|skills(?:\s+summary)?|summary|objective)\s*$",
    re.I,
)
_MONTH_PATTERN = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
)
_DATE_VALUE = (
    rf"(?:(?:{_MONTH_PATTERN})[\s./-]+(?:19|20)\d{{2}}|"
    rf"(?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{{2}}|(?:19|20)\d{{2}})"
)
_DATE_RANGE = re.compile(
    rf"(?P<start>{_DATE_VALUE})\s*(?:-|–|—|to)\s*"
    rf"(?P<end>present|current|now|{_DATE_VALUE})",
    re.I,
)
_MONTH_NUMBERS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


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
    skill_evidence: list[dict] = field(default_factory=list)
    experiences: list[dict] = field(default_factory=list)
    declared_years_of_experience: int | None = None
    computed_years_of_experience: int | None = None
    field_confidence: dict[str, float] = field(default_factory=dict)
    intent_suggestions: dict = field(default_factory=dict)
    status: str = "complete"
    confidence: float = 1.0
    source: str = "llm"
    model: str | None = None
    error: str | None = None


def _validate_extraction(data: dict, resume_text: str = "") -> ResumeParseResult:
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

    skill_evidence: list[dict] = []
    for item in data.get("skill_evidence", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if (
            name
            and _evidence_is_grounded(evidence, resume_text)
            and _evidence_is_grounded(name, evidence)
        ):
            skill_evidence.append({"name": name, "evidence": evidence})

    experiences: list[dict] = []
    for item in data.get("experiences", []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        company = str(item.get("company") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if (
            not title
            or not _evidence_is_grounded(evidence, resume_text)
            or not _evidence_is_grounded(title, evidence)
            or (company and not _evidence_is_grounded(company, evidence))
        ):
            continue
        responsibilities = [
            value
            for value in to_list(item.get("responsibilities"))
            if _evidence_is_grounded(value, resume_text)
        ]
        start_date = str(item.get("start_date") or "").strip()
        end_date = str(item.get("end_date") or "").strip()
        experiences.append(
            {
                "title": title,
                "company": company,
                "start_date": (
                    start_date
                    if start_date and _evidence_is_grounded(start_date, evidence)
                    else None
                ),
                "end_date": (
                    end_date
                    if end_date and _evidence_is_grounded(end_date, evidence)
                    else None
                ),
                "responsibilities": responsibilities,
                "evidence": evidence,
                "confidence": 0.9,
            }
        )

    raw_suggestions = data.get("intent_suggestions")
    aliases = (
        to_list(raw_suggestions.get("role_aliases"))
        if isinstance(raw_suggestions, dict)
        else []
    )
    seniority_band = (
        raw_suggestions.get("seniority_band")
        if isinstance(raw_suggestions, dict)
        else "unknown"
    )
    if seniority_band not in {
        "intern",
        "entry",
        "mid",
        "senior",
        "lead",
        "manager",
        "executive",
        "unknown",
    }:
        seniority_band = "unknown"

    skills = to_list(data.get("skills"))
    recent_titles = to_list(data.get("recent_titles"))
    declared_years = to_int(data.get("declared_years_of_experience"))
    computed_years = _computed_years(experiences)
    provided_years = to_int(data.get("years_of_experience"))
    years = provided_years
    field_confidence = _confidence_values(data.get("field_confidence"))
    if not any(field_confidence.values()):
        field_confidence = {
            "skills": 0.9 if skills else 0.0,
            "experiences": 0.9 if experiences else 0.0,
            "titles": 0.9 if recent_titles else 0.0,
            "years": 0.85 if years is not None else 0.0,
        }

    return ResumeParseResult(
        skills=skills,
        years_of_experience=years,
        recent_titles=recent_titles,
        industries=to_list(data.get("industries")),
        education=to_list(data.get("education")),
        skill_evidence=skill_evidence,
        experiences=experiences,
        declared_years_of_experience=declared_years,
        computed_years_of_experience=computed_years,
        field_confidence=field_confidence,
        intent_suggestions={
            "role_aliases": _dedupe(aliases, limit=12),
            "seniority_band": seniority_band,
        },
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


def _confidence_values(value: object) -> dict[str, float]:
    fields = ("skills", "experiences", "titles", "years")
    raw = value if isinstance(value, dict) else {}
    result: dict[str, float] = {}
    for name in fields:
        try:
            result[name] = max(0.0, min(float(raw.get(name, 0.0)), 1.0))
        except (TypeError, ValueError):
            result[name] = 0.0
    return result


def _evidence_is_grounded(evidence: str, resume_text: str) -> bool:
    if not resume_text:
        return True
    normalized_evidence = re.sub(r"\s+", " ", evidence).strip().casefold()
    normalized_resume = re.sub(r"\s+", " ", resume_text).casefold()
    return bool(normalized_evidence and normalized_evidence in normalized_resume)


def _date_month(value: object) -> int | None:
    text = str(value or "").strip().casefold()
    if text in {"present", "current", "now"}:
        current = datetime.now(timezone.utc)
        return current.year * 12 + current.month - 1
    year_match = re.search(r"\b((?:19|20)\d{2})\b", text)
    if not year_match:
        return None
    numeric_month = re.search(r"\b(0?[1-9]|1[0-2])[/.-](?:19|20)\d{2}\b", text)
    month = int(numeric_month.group(1)) if numeric_month else 1
    for name, number in _MONTH_NUMBERS.items():
        if re.search(rf"\b{name}", text):
            month = number
            break
    return int(year_match.group(1)) * 12 + month - 1


def _computed_years(experiences: list[dict]) -> int | None:
    intervals: list[tuple[int, int]] = []
    for experience in experiences:
        start = _date_month(experience.get("start_date"))
        end = _date_month(experience.get("end_date"))
        if start is None or end is None or end < start:
            continue
        intervals.append((start, end))
    if not intervals:
        return None
    intervals.sort()
    merged: list[list[int]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    months = sum(end - start + 1 for start, end in merged)
    return max(1, round(months / 12))


def _declared_years(resume_text: str) -> int | None:
    values: list[int] = []
    for match in re.finditer(
        r"\b(?P<years>\d{1,2})(?:\+)?\s+years?\s+(?:of\s+)?"
        r"(?:professional\s+|relevant\s+|total\s+)?experience\b",
        resume_text,
        re.I,
    ):
        years = int(match.group("years"))
        context = resume_text[max(0, match.start() - 60) : match.end()].casefold()
        if not 0 < years < 60 or re.search(
            r"\b(?:company|organization|business)\s+(?:has|with|over)\b", context
        ):
            continue
        values.append(years)
    return max(values) if values else None


def _experience_section_lines(resume_text: str) -> list[str]:
    lines = [_repair_extracted_text(line) for line in resume_text.splitlines()]
    start = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if _EXPERIENCE_HEADER.match(line)
        ),
        None,
    )
    if start is None:
        return lines
    section: list[str] = []
    for line in lines[start:]:
        if _RESUME_SECTION_HEADER.match(line):
            break
        section.append(line)
    return section


def _heuristic_experiences(resume_text: str) -> list[dict]:
    lines = _experience_section_lines(resume_text)
    experiences: list[dict] = []
    for index, line in enumerate(lines):
        match = _DATE_RANGE.search(line)
        if not match:
            continue
        prefix = line[: match.start()].strip(" \t|,-–—")
        parts = [
            part.strip()
            for part in re.split(r"\s*\|\s*|\s{2,}", prefix)
            if part.strip()
        ]
        title = parts[0] if parts else ""
        company = parts[1] if len(parts) > 1 else ""
        evidence_lines = [line]
        confidence = 0.75 if len(parts) > 1 else 0.6
        if not title:
            preceding = [value for value in lines[max(0, index - 2) : index] if value]
            if len(preceding) > 1:
                first, second = preceding[-2:]
                first_is_title = bool(_TITLE_MARKER.search(first))
                second_is_title = bool(_TITLE_MARKER.search(second))
                if first_is_title and not second_is_title:
                    title, company = first, second
                else:
                    title, company = second, first
                evidence_lines[:0] = [first, second]
                confidence = 0.6 if first_is_title != second_is_title else 0.45
            elif preceding:
                title = preceding[-1].strip(" \t|•-")
                evidence_lines.insert(0, preceding[-1])
                confidence = 0.4
        responsibilities: list[str] = []
        for following in lines[index + 1 : index + 8]:
            if _DATE_RANGE.search(following) or _RESUME_SECTION_HEADER.match(following):
                break
            if following.strip().startswith(("-", "•")):
                responsibility = following.strip(" \t•-")
                if responsibility:
                    responsibilities.append(responsibility)
                    evidence_lines.append(following)
        if not title:
            continue
        experiences.append(
            {
                "title": title,
                "company": company,
                "start_date": match.group("start"),
                "end_date": match.group("end"),
                "responsibilities": responsibilities,
                "evidence": "\n".join(evidence_lines),
                "confidence": confidence,
            }
        )
    return experiences[:20]


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


def _heuristic_skill_evidence(resume_text: str, skills: list[str]) -> list[dict]:
    lines = [_repair_extracted_text(line) for line in resume_text.splitlines()]
    evidence: list[dict] = []
    for skill in skills:
        matched_line = next(
            (line for line in lines if skill.casefold() in line.casefold()), ""
        )
        if matched_line:
            evidence.append({"name": skill, "evidence": matched_line})
    return evidence


def _heuristic_parse(resume_text: str) -> ResumeParseResult:
    experiences = _heuristic_experiences(resume_text)
    declared_years = _declared_years(resume_text)
    computed_years = _computed_years(experiences)
    years = declared_years
    skills = _heuristic_skills(resume_text)
    titles = _heuristic_titles(resume_text)
    skill_evidence = _heuristic_skill_evidence(resume_text, skills)
    field_confidence = {
        "skills": 0.75 if skill_evidence else 0.0,
        "experiences": (
            sum(float(item["confidence"]) for item in experiences) / len(experiences)
            if experiences
            else 0.0
        ),
        "titles": 0.45 if titles else 0.0,
        "years": 0.8 if computed_years is not None else (0.65 if years else 0.0),
    }
    populated = int(bool(skills)) + int(bool(titles)) + int(years is not None)
    return ResumeParseResult(
        skills=skills,
        years_of_experience=years,
        recent_titles=titles,
        skill_evidence=skill_evidence,
        experiences=experiences,
        declared_years_of_experience=declared_years,
        computed_years_of_experience=computed_years,
        field_confidence=field_confidence,
        intent_suggestions={},
        status="degraded",
        confidence=round(populated / 3 * 0.7, 2),
        source="heuristic",
    )


def _merge_with_fallback(
    primary: ResumeParseResult,
    fallback: ResumeParseResult,
) -> ResumeParseResult:
    merged_skill_evidence = primary.skill_evidence or fallback.skill_evidence
    merged_experiences = primary.experiences or fallback.experiences
    used_fallback = (
        not primary.skills
        or not primary.recent_titles
        or primary.years_of_experience is None
        or (not primary.experiences and bool(fallback.experiences))
    )
    field_confidence = {
        name: max(
            float(primary.field_confidence.get(name, 0.0)),
            float(fallback.field_confidence.get(name, 0.0)),
        )
        for name in ("skills", "experiences", "titles", "years")
    }
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
        skill_evidence=merged_skill_evidence,
        experiences=merged_experiences,
        declared_years_of_experience=(
            primary.declared_years_of_experience
            if primary.declared_years_of_experience is not None
            else fallback.declared_years_of_experience
        ),
        computed_years_of_experience=(
            primary.computed_years_of_experience
            if primary.computed_years_of_experience is not None
            else fallback.computed_years_of_experience
        ),
        field_confidence=field_confidence,
        intent_suggestions=primary.intent_suggestions,
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
            max_tokens=1800,
            response_schema=RESUME_EXTRACTION_SCHEMA,
        )
        parsed = _validate_extraction(data, resume_text=resume_text[:10000])
        parsed.model = getattr(llm_client, "last_model", None)
        return _merge_with_fallback(parsed, fallback)
    except Exception as exc:
        logger.exception("Resume parse failed — using deterministic fallback")
        fallback.error = f"{type(exc).__name__}: {exc}"
        fallback.model = getattr(llm_client, "last_model", None)
        return fallback
