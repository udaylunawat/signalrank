import hashlib
import inspect
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from llm.openrouter import OpenRouterClient

RUBRIC_VERSION = "company-reputation-v1"
PROMPT_VERSION = "company-reputation-prompt-v1"
DEFAULT_BATCH_SIZE = 15
MAX_BATCH_SIZE = 20
MAX_CONTEXT_LENGTH = 500
MAX_RATIONALE_LENGTH = 240

ReputationTier = Literal["S", "A", "B", "C", "unknown"]
AssessmentStatus = Literal[
    "assessed",
    "unknown",
    "unavailable",
    "invalid_response",
    "not_returned",
]

_LEGAL_SUFFIXES = {
    "ag",
    "corp",
    "corporation",
    "gmbh",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "llp",
    "ltd",
    "plc",
    "private",
    "pte",
    "pvt",
}

COMPANY_REPUTATION_JSON_SCHEMA: dict[str, Any] = {
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
                    "canonical_name",
                    "score",
                    "tier",
                    "confidence",
                    "rationale",
                ],
                "properties": {
                    "canonical_name": {"type": "string", "minLength": 1},
                    "score": {
                        "anyOf": [
                            {"type": "integer", "minimum": 0, "maximum": 100},
                            {"type": "null"},
                        ]
                    },
                    "tier": {
                        "type": "string",
                        "enum": ["S", "A", "B", "C", "unknown"],
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_RATIONALE_LENGTH,
                    },
                },
            },
        }
    },
}

SYSTEM_PROMPT = f"""You assess employer reputation globally and independently of any
candidate, resume, profession, seniority, location preference, or target role.

Use only this role-agnostic rubric:
- employer credibility and legitimacy: 0-25
- product, service, or engineering reputation: 0-25
- organizational maturity and operating standards: 0-20
- public track record and durable standing: 0-20
- learning and career-development reputation: 0-10

Do not assess candidate fit, job fit, compensation, or hiring likelihood. Do not favor
a company merely because it is large or well known. Use `unknown` when the supplied
identity and neutral company context are insufficient for a defensible assessment.

Known-score tiers are fixed: S=85-100, A=70-84, B=50-69, C=0-49. For `unknown`,
score must be null. Return one item for every canonical name, in the given order.
Rationales must be factual, concise, and no longer than {MAX_RATIONALE_LENGTH}
characters. Return JSON matching the supplied schema and nothing else.

Rubric version: {RUBRIC_VERSION}
Prompt version: {PROMPT_VERSION}"""


@dataclass(frozen=True, slots=True)
class CompanyCandidate:
    name: str
    neutral_context: str = ""


@dataclass(frozen=True, slots=True)
class CompanyReputation:
    canonical_name: str
    display_name: str
    score: int | None
    tier: ReputationTier
    confidence: float
    rationale: str
    assessment_status: AssessmentStatus
    model_id: str | None
    prompt_version: str
    rubric_version: str
    fingerprint: str


def canonicalize_company_name(
    name: str,
    aliases: Mapping[str, str] | None = None,
) -> str:
    if not isinstance(name, str):
        return ""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_name.lower()))
    tokens = normalized.strip().split()
    while len(tokens) > 1 and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    canonical = " ".join(tokens)
    if not aliases:
        return canonical

    normalized_aliases = {
        canonicalize_company_name(source): canonicalize_company_name(target)
        for source, target in aliases.items()
        if isinstance(source, str) and isinstance(target, str)
    }
    seen: set[str] = set()
    while canonical in normalized_aliases and canonical not in seen:
        seen.add(canonical)
        canonical = normalized_aliases[canonical]
    return canonical


def assessment_fingerprint(
    canonical_name: str,
    neutral_context: str = "",
    *,
    rubric_version: str = RUBRIC_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    payload = {
        "canonical_name": canonical_name,
        "neutral_context": _clean_context(neutral_context),
        "prompt_version": prompt_version,
        "rubric_version": rubric_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def batch_fingerprint(candidates: Iterable[CompanyCandidate]) -> str:
    fingerprints = sorted(
        assessment_fingerprint(
            canonicalize_company_name(candidate.name),
            candidate.neutral_context,
        )
        for candidate in candidates
    )
    return hashlib.sha256("\n".join(fingerprints).encode()).hexdigest()


def _clean_context(context: str) -> str:
    if not isinstance(context, str):
        return ""
    return re.sub(r"\s+", " ", context).strip()[:MAX_CONTEXT_LENGTH]


def _expected_tier(score: int) -> ReputationTier:
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 50:
        return "B"
    return "C"


def _unknown_result(
    candidate: CompanyCandidate,
    canonical_name: str,
    status: AssessmentStatus,
    rationale: str,
    model_id: str | None = None,
) -> CompanyReputation:
    return CompanyReputation(
        canonical_name=canonical_name,
        display_name=candidate.name.strip(),
        score=None,
        tier="unknown",
        confidence=0.0,
        rationale=rationale,
        assessment_status=status,
        model_id=model_id,
        prompt_version=PROMPT_VERSION,
        rubric_version=RUBRIC_VERSION,
        fingerprint=assessment_fingerprint(
            canonical_name,
            candidate.neutral_context,
        ),
    )


def _validate_item(
    raw: Any,
    candidate: CompanyCandidate,
    canonical_name: str,
    model_id: str | None,
) -> CompanyReputation | None:
    required = {
        "canonical_name",
        "score",
        "tier",
        "confidence",
        "rationale",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        return None
    if raw["canonical_name"] != canonical_name:
        return None

    tier = raw["tier"]
    score = raw["score"]
    confidence = raw["confidence"]
    rationale = raw["rationale"]
    if tier not in {"S", "A", "B", "C", "unknown"}:
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    if not 0 <= confidence <= 1:
        return None
    if not isinstance(rationale, str):
        return None
    rationale = rationale.strip()
    if not rationale or len(rationale) > MAX_RATIONALE_LENGTH:
        return None

    if tier == "unknown":
        if score is not None:
            return None
        status: AssessmentStatus = "unknown"
    else:
        if isinstance(score, bool) or not isinstance(score, int):
            return None
        if not 0 <= score <= 100 or tier != _expected_tier(score):
            return None
        status = "assessed"

    return CompanyReputation(
        canonical_name=canonical_name,
        display_name=candidate.name.strip(),
        score=score,
        tier=tier,
        confidence=float(confidence),
        rationale=rationale,
        assessment_status=status,
        model_id=model_id,
        prompt_version=PROMPT_VERSION,
        rubric_version=RUBRIC_VERSION,
        fingerprint=assessment_fingerprint(
            canonical_name,
            candidate.neutral_context,
        ),
    )


def _extract_payload(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw, dict):
        return None, None
    model_id = raw.get("_model")
    metadata = raw.get("_metadata")
    if not isinstance(model_id, str) and isinstance(metadata, dict):
        model_id = metadata.get("model")
    if not isinstance(model_id, str) or not model_id.strip():
        model_id = None

    payload: Any = raw.get("data", raw)
    if not isinstance(payload, dict):
        return None, model_id
    allowed = {"assessments"}
    if payload is raw:
        allowed.update({"_model", "_metadata"})
    if set(payload) - allowed or set(payload) & {"_error", "_details"}:
        return None, model_id
    if set(payload) & {"_model", "_metadata"} and "assessments" not in payload:
        return None, model_id
    if set(payload) - {"assessments", "_model", "_metadata"}:
        return None, model_id
    return payload, model_id


def _schema_kwargs(llm_client: OpenRouterClient) -> dict[str, Any]:
    try:
        parameters = inspect.signature(llm_client.llm_json).parameters
    except (TypeError, ValueError):
        return {}
    if "response_schema" in parameters:
        return {"response_schema": COMPANY_REPUTATION_JSON_SCHEMA}
    if "json_schema" in parameters:
        return {"json_schema": COMPANY_REPUTATION_JSON_SCHEMA}
    return {}


class CompanyReputationAssessor:
    def __init__(
        self,
        llm_client: OpenRouterClient,
        *,
        aliases: Mapping[str, str] | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")
        self.llm_client = llm_client
        self.aliases = aliases or {}
        self.batch_size = batch_size

    async def assess(
        self,
        companies: Iterable[str | CompanyCandidate],
    ) -> dict[str, CompanyReputation]:
        candidates = self._canonical_candidates(companies)
        results: dict[str, CompanyReputation] = {}
        for start in range(0, len(candidates), self.batch_size):
            batch = candidates[start : start + self.batch_size]
            results.update(await self._assess_batch(batch))
        return results

    def _canonical_candidates(
        self,
        companies: Iterable[str | CompanyCandidate],
    ) -> list[tuple[str, CompanyCandidate]]:
        unique: dict[str, CompanyCandidate] = {}
        for item in companies:
            candidate = (
                item if isinstance(item, CompanyCandidate) else CompanyCandidate(item)
            )
            canonical_name = canonicalize_company_name(candidate.name, self.aliases)
            if canonical_name and canonical_name not in unique:
                unique[canonical_name] = CompanyCandidate(
                    name=candidate.name.strip(),
                    neutral_context=_clean_context(candidate.neutral_context),
                )
        return list(unique.items())

    async def _assess_batch(
        self,
        batch: list[tuple[str, CompanyCandidate]],
    ) -> dict[str, CompanyReputation]:
        request_items = [
            {
                "canonical_name": canonical_name,
                "neutral_company_context": candidate.neutral_context,
            }
            for canonical_name, candidate in batch
        ]
        user_prompt = json.dumps(
            {"companies": request_items},
            ensure_ascii=True,
            separators=(",", ":"),
        )
        try:
            raw = await self.llm_client.llm_json(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=max(700, len(batch) * 120),
                temperature=0.0,
                **_schema_kwargs(self.llm_client),
            )
        except Exception:
            return {
                canonical_name: _unknown_result(
                    candidate,
                    canonical_name,
                    "unavailable",
                    "Company reputation assessment is temporarily unavailable.",
                )
                for canonical_name, candidate in batch
            }

        payload, model_id = _extract_payload(raw)
        if model_id is None:
            last_model = getattr(self.llm_client, "last_model", None)
            model_id = last_model if isinstance(last_model, str) else None
        if payload is None or not isinstance(payload.get("assessments"), list):
            return {
                canonical_name: _unknown_result(
                    candidate,
                    canonical_name,
                    "invalid_response",
                    "Company reputation could not be validated.",
                    model_id,
                )
                for canonical_name, candidate in batch
            }

        expected = dict(batch)
        raw_by_name: dict[str, list[Any]] = {}
        for item in payload["assessments"]:
            if isinstance(item, dict) and isinstance(item.get("canonical_name"), str):
                raw_by_name.setdefault(item["canonical_name"], []).append(item)

        results: dict[str, CompanyReputation] = {}
        for canonical_name, candidate in expected.items():
            matches = raw_by_name.get(canonical_name, [])
            if not matches:
                results[canonical_name] = _unknown_result(
                    candidate,
                    canonical_name,
                    "not_returned",
                    "Company was not returned by the assessment model.",
                    model_id,
                )
                continue
            if len(matches) != 1:
                validated = None
            else:
                validated = _validate_item(
                    matches[0], candidate, canonical_name, model_id
                )
            results[canonical_name] = validated or _unknown_result(
                candidate,
                canonical_name,
                "invalid_response",
                "Company reputation could not be validated.",
                model_id,
            )
        return results
