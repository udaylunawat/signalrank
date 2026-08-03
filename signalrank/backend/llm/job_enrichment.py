import inspect
import json
from dataclasses import dataclass
from typing import Any, Iterable, Literal

from llm.openrouter import OpenRouterClient

RUBRIC_VERSION = "job-enrichment-v1"
PROMPT_VERSION = "job-enrichment-prompt-v1"
DEFAULT_BATCH_SIZE = 8
MAX_BATCH_SIZE = 12
MAX_DESCRIPTION_CHARS = 3_000
MAX_ROLE_ALIASES = 8
MAX_SKILLS = 20

SeniorityBand = Literal[
    "intern",
    "entry",
    "mid",
    "senior",
    "staff",
    "lead",
    "manager",
    "director",
    "executive",
    "unknown",
]
CoherenceStatus = Literal[
    "coherent",
    "ambiguous",
    "contradictory",
    "insufficient",
    "unassessed",
]
AssessmentStatus = Literal[
    "assessed",
    "unavailable",
    "invalid_response",
    "not_returned",
]

JOB_ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["assessments"],
    "properties": {
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "job_key",
                    "role_summary",
                    "role_aliases",
                    "seniority_band",
                    "required_skills",
                    "preferred_skills",
                    "workplace",
                    "coherence_status",
                    "coherence_confidence",
                    "coherence_reason",
                ],
                "properties": {
                    "job_key": {"type": "string", "minLength": 1},
                    "role_summary": {"type": "string", "maxLength": 500},
                    "role_aliases": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 120},
                        "maxItems": MAX_ROLE_ALIASES,
                    },
                    "seniority_band": {
                        "type": "string",
                        "enum": [
                            "intern",
                            "entry",
                            "mid",
                            "senior",
                            "staff",
                            "lead",
                            "manager",
                            "director",
                            "executive",
                            "unknown",
                        ],
                    },
                    "required_skills": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 100},
                        "maxItems": MAX_SKILLS,
                    },
                    "preferred_skills": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 100},
                        "maxItems": MAX_SKILLS,
                    },
                    "workplace": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["mode", "locations"],
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["remote", "hybrid", "onsite", "unknown"],
                            },
                            "locations": {
                                "type": "array",
                                "items": {"type": "string", "maxLength": 120},
                                "maxItems": 12,
                            },
                        },
                    },
                    "coherence_status": {
                        "type": "string",
                        "enum": [
                            "coherent",
                            "ambiguous",
                            "contradictory",
                            "insufficient",
                        ],
                    },
                    "coherence_confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "coherence_reason": {
                        "type": "string",
                        "enum": [
                            "aligned",
                            "responsibility_mismatch",
                            "multi_role_posting",
                            "insufficient_description",
                        ],
                    },
                },
            },
        }
    },
}

SYSTEM_PROMPT = f"""You enrich job postings independently of any candidate, resume,
career preference, location preference, company reputation, or target role.

Return a role-agnostic structured assessment for each posting:
- Summarize the actual responsibilities in `role_summary`.
- List only title- or responsibility-supported alternative role names in
  `role_aliases`; do not invent a role family.
- Infer the seniority band from the title and stated requirements. Use `unknown`
  when evidence is insufficient.
- Separate explicit required skills from preferred skills. Do not turn every tool
  mentioned in prose into a required skill.
- Normalize workplace mode and locations from the posting.
- Assess whether the title and primary responsibilities agree. Use
  `contradictory` only for a clear mismatch, `ambiguous` for multi-role postings,
  and `insufficient` when the description cannot support an assessment.

Return JSON matching the supplied schema and nothing else.
Rubric version: {RUBRIC_VERSION}
Prompt version: {PROMPT_VERSION}"""


@dataclass(frozen=True, slots=True)
class JobCandidate:
    job_key: str
    title: str
    description: str
    location: str


@dataclass(frozen=True, slots=True)
class JobEnrichmentAssessment:
    job_key: str
    role_summary: str | None
    role_aliases: list[str]
    seniority_band: SeniorityBand
    required_skills: list[str]
    preferred_skills: list[str]
    workplace: dict[str, object]
    coherence_status: CoherenceStatus
    coherence_confidence: float
    coherence_reason: str | None
    assessment_status: AssessmentStatus
    model_id: str | None


def _schema_kwargs(llm_client: OpenRouterClient) -> dict[str, Any]:
    try:
        parameters = inspect.signature(llm_client.llm_json).parameters
    except (TypeError, ValueError):
        return {}
    if "response_schema" in parameters:
        return {"response_schema": JOB_ENRICHMENT_SCHEMA}
    if "json_schema" in parameters:
        return {"json_schema": JOB_ENRICHMENT_SCHEMA}
    return {}


def _clean_list(value: object, limit: int) -> list[str] | None:
    if not isinstance(value, list) or len(value) > limit:
        return None
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return None
        cleaned = " ".join(item.split()).strip()
        if not cleaned or len(cleaned) > 120:
            return None
        key = cleaned.casefold()
        if key not in seen:
            result.append(cleaned)
            seen.add(key)
    return result


def _unavailable(
    candidate: JobCandidate,
    status: AssessmentStatus,
    model_id: str | None = None,
) -> JobEnrichmentAssessment:
    return JobEnrichmentAssessment(
        job_key=candidate.job_key,
        role_summary=None,
        role_aliases=[],
        seniority_band="unknown",
        required_skills=[],
        preferred_skills=[],
        workplace={"mode": "unknown", "locations": []},
        coherence_status="unassessed",
        coherence_confidence=0.0,
        coherence_reason=None,
        assessment_status=status,
        model_id=model_id,
    )


def _model_id(raw: object, llm_client: OpenRouterClient) -> str | None:
    if isinstance(raw, dict):
        candidate = raw.get("_model")
        if isinstance(candidate, str) and candidate.strip():
            return candidate
        metadata = raw.get("_metadata")
        if isinstance(metadata, dict):
            candidate = metadata.get("model")
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    candidate = getattr(llm_client, "last_model", None)
    return candidate if isinstance(candidate, str) and candidate.strip() else None


def _validate_assessment(
    raw: object,
    candidate: JobCandidate,
    model_id: str | None,
) -> JobEnrichmentAssessment | None:
    if not isinstance(raw, dict) or set(raw) != {
        "job_key",
        "role_summary",
        "role_aliases",
        "seniority_band",
        "required_skills",
        "preferred_skills",
        "workplace",
        "coherence_status",
        "coherence_confidence",
        "coherence_reason",
    }:
        return None
    if raw["job_key"] != candidate.job_key:
        return None
    if not isinstance(raw["role_summary"], str):
        return None
    role_summary = " ".join(raw["role_summary"].split()).strip()
    if not role_summary or len(role_summary) > 500:
        return None
    role_aliases = _clean_list(raw["role_aliases"], MAX_ROLE_ALIASES)
    required_skills = _clean_list(raw["required_skills"], MAX_SKILLS)
    preferred_skills = _clean_list(raw["preferred_skills"], MAX_SKILLS)
    if role_aliases is None or required_skills is None or preferred_skills is None:
        return None
    seniority_band = raw["seniority_band"]
    if seniority_band not in {
        "intern",
        "entry",
        "mid",
        "senior",
        "staff",
        "lead",
        "manager",
        "director",
        "executive",
        "unknown",
    }:
        return None
    workplace = raw["workplace"]
    if not isinstance(workplace, dict) or set(workplace) != {"mode", "locations"}:
        return None
    locations = _clean_list(workplace["locations"], 12)
    if workplace["mode"] not in {"remote", "hybrid", "onsite", "unknown"}:
        return None
    if locations is None:
        return None
    coherence_status = raw["coherence_status"]
    coherence_reason = raw["coherence_reason"]
    confidence = raw["coherence_confidence"]
    if coherence_status not in {
        "coherent",
        "ambiguous",
        "contradictory",
        "insufficient",
    } or coherence_reason not in {
        "aligned",
        "responsibility_mismatch",
        "multi_role_posting",
        "insufficient_description",
    }:
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    if not 0 <= confidence <= 1:
        return None
    return JobEnrichmentAssessment(
        job_key=candidate.job_key,
        role_summary=role_summary,
        role_aliases=role_aliases,
        seniority_band=seniority_band,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        workplace={"mode": workplace["mode"], "locations": locations},
        coherence_status=coherence_status,
        coherence_confidence=float(confidence),
        coherence_reason=coherence_reason,
        assessment_status="assessed",
        model_id=model_id,
    )


class JobEnrichmentAssessor:
    def __init__(
        self, llm_client: OpenRouterClient, *, batch_size: int = DEFAULT_BATCH_SIZE
    ):
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")
        self.llm_client = llm_client
        self.batch_size = batch_size

    async def assess(
        self, candidates: Iterable[JobCandidate]
    ) -> dict[str, JobEnrichmentAssessment]:
        values = [candidate for candidate in candidates if candidate.job_key]
        results: dict[str, JobEnrichmentAssessment] = {}
        for start in range(0, len(values), self.batch_size):
            batch = values[start : start + self.batch_size]
            results.update(await self._assess_batch(batch))
        return results

    async def _assess_batch(
        self, batch: list[JobCandidate]
    ) -> dict[str, JobEnrichmentAssessment]:
        user_prompt = json.dumps(
            {
                "jobs": [
                    {
                        "job_key": candidate.job_key,
                        "title": candidate.title,
                        "description": " ".join(candidate.description.split())[
                            :MAX_DESCRIPTION_CHARS
                        ],
                        "location": candidate.location,
                    }
                    for candidate in batch
                ]
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
        try:
            raw = await self.llm_client.llm_json(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=max(900, len(batch) * 220),
                temperature=0.0,
                **_schema_kwargs(self.llm_client),
            )
        except Exception:
            return {
                candidate.job_key: _unavailable(candidate, "unavailable")
                for candidate in batch
            }

        model_id = _model_id(raw, self.llm_client)
        payload = raw.get("data", raw) if isinstance(raw, dict) else None
        assessments = payload.get("assessments") if isinstance(payload, dict) else None
        if not isinstance(assessments, list):
            return {
                candidate.job_key: _unavailable(candidate, "invalid_response", model_id)
                for candidate in batch
            }
        raw_by_key: dict[str, list[object]] = {}
        for item in assessments:
            if isinstance(item, dict) and isinstance(item.get("job_key"), str):
                raw_by_key.setdefault(item["job_key"], []).append(item)
        results: dict[str, JobEnrichmentAssessment] = {}
        for candidate in batch:
            matches = raw_by_key.get(candidate.job_key, [])
            if not matches:
                results[candidate.job_key] = _unavailable(
                    candidate, "not_returned", model_id
                )
                continue
            valid = (
                _validate_assessment(matches[0], candidate, model_id)
                if len(matches) == 1
                else None
            )
            results[candidate.job_key] = valid or _unavailable(
                candidate, "invalid_response", model_id
            )
        return results
