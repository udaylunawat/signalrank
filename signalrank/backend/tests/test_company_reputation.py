import json

import pytest

from llm.company_reputation import (
    COMPANY_REPUTATION_JSON_SCHEMA,
    PROMPT_VERSION,
    RUBRIC_VERSION,
    CompanyCandidate,
    CompanyReputationAssessor,
    assessment_fingerprint,
    batch_fingerprint,
    canonicalize_company_name,
)


def _assessment(
    name: str,
    *,
    score: int | None = 78,
    tier: str = "A",
    confidence: float = 0.9,
    rationale: str = "Credible employer with a durable public track record.",
) -> dict:
    return {
        "canonical_name": name,
        "score": score,
        "tier": tier,
        "confidence": confidence,
        "rationale": rationale,
    }


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def llm_json(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class StructuredFakeLLM:
    def __init__(self, response):
        self.response = response
        self.response_schema = None

    async def llm_json(
        self,
        *,
        system,
        user,
        max_tokens,
        temperature,
        response_schema=None,
    ):
        self.response_schema = response_schema
        return self.response


def test_canonicalizes_legal_suffixes_and_explicit_aliases():
    aliases = {
        "Google India": "Google",
        "Alphabet Incorporated": "Google",
    }

    assert canonicalize_company_name("Acme Technologies, Pvt. Ltd.") == (
        "acme technologies"
    )
    assert canonicalize_company_name("Google India", aliases) == "google"
    assert canonicalize_company_name("Alphabet Inc.", aliases) == "google"


def test_fingerprints_are_stable_order_independent_and_versioned():
    first = CompanyCandidate("Acme", "Enterprise software vendor")
    second = CompanyCandidate("Beta", "Consumer payments company")

    assert assessment_fingerprint("acme", " Enterprise  software vendor ") == (
        assessment_fingerprint("acme", "Enterprise software vendor")
    )
    assert assessment_fingerprint("acme", rubric_version="v2") != (
        assessment_fingerprint("acme", rubric_version="v1")
    )
    assert batch_fingerprint([first, second]) == batch_fingerprint([second, first])


@pytest.mark.asyncio
async def test_batches_canonical_companies_and_deduplicates_aliases():
    llm = FakeLLM(
        [
            {
                "assessments": [
                    _assessment("google", score=91, tier="S"),
                    _assessment("acme", score=55, tier="B"),
                ],
                "_model": "google/gemma-free",
            }
        ]
    )
    assessor = CompanyReputationAssessor(
        llm,
        aliases={"Google India": "Google"},
    )

    result = await assessor.assess(
        ["Google LLC", "Google India", CompanyCandidate("Acme Pvt Ltd")]
    )

    assert list(result) == ["google", "acme"]
    assert result["google"].tier == "S"
    assert result["google"].model_id == "google/gemma-free"
    assert result["google"].rubric_version == RUBRIC_VERSION
    assert result["google"].prompt_version == PROMPT_VERSION
    assert len(llm.calls) == 1
    request = json.loads(llm.calls[0]["user"])
    assert [item["canonical_name"] for item in request["companies"]] == [
        "google",
        "acme",
    ]


@pytest.mark.asyncio
async def test_prompt_contains_only_neutral_company_inputs():
    llm = FakeLLM([{"assessments": [_assessment("acme", score=None, tier="unknown")]}])
    assessor = CompanyReputationAssessor(llm)

    await assessor.assess(
        [CompanyCandidate("Acme", "Privately held logistics software company")]
    )

    request = json.loads(llm.calls[0]["user"])
    assert request == {
        "companies": [
            {
                "canonical_name": "acme",
                "neutral_company_context": (
                    "Privately held logistics software company"
                ),
            }
        ]
    }
    assert "resume" not in llm.calls[0]["user"].lower()
    assert "target_role" not in llm.calls[0]["user"].lower()


@pytest.mark.asyncio
async def test_forwards_schema_when_client_supports_structured_outputs():
    llm = StructuredFakeLLM({"assessments": [_assessment("acme", score=90, tier="S")]})
    assessor = CompanyReputationAssessor(llm)

    result = await assessor.assess(["Acme"])

    assert result["acme"].assessment_status == "assessed"
    assert llm.response_schema == COMPANY_REPUTATION_JSON_SCHEMA


@pytest.mark.asyncio
async def test_strict_validation_fails_open_per_company():
    llm = FakeLLM(
        [
            {
                "assessments": [
                    _assessment("valid", score=70, tier="A"),
                    _assessment("wrong tier", score=51, tier="A"),
                    _assessment("string score", score="90", tier="S"),
                    {
                        **_assessment("extra field", score=90, tier="S"),
                        "source": "invented",
                    },
                ]
            }
        ]
    )
    assessor = CompanyReputationAssessor(llm)

    result = await assessor.assess(
        ["Valid", "Wrong Tier", "String Score", "Extra Field", "Missing"]
    )

    assert result["valid"].assessment_status == "assessed"
    for company in ("wrong tier", "string score", "extra field"):
        assert result[company].tier == "unknown"
        assert result[company].score is None
        assert result[company].assessment_status == "invalid_response"
    assert result["missing"].assessment_status == "not_returned"


@pytest.mark.asyncio
async def test_valid_unknown_is_distinct_from_model_failure():
    llm = FakeLLM(
        [
            {
                "assessments": [
                    _assessment(
                        "obscure startup",
                        score=None,
                        tier="unknown",
                        confidence=0.2,
                        rationale="Insufficient reliable public information.",
                    )
                ]
            }
        ]
    )
    result = await CompanyReputationAssessor(llm).assess(["Obscure Startup"])

    assessment = result["obscure startup"]
    assert assessment.assessment_status == "unknown"
    assert assessment.confidence == 0.2
    assert assessment.score is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,status",
    [
        ({"_error": "llm_failed"}, "invalid_response"),
        ({"assessments": "not-a-list"}, "invalid_response"),
        (RuntimeError("network down"), "unavailable"),
    ],
)
async def test_llm_failures_return_fail_open_unknown(response, status):
    result = await CompanyReputationAssessor(FakeLLM([response])).assess(["Acme"])

    assessment = result["acme"]
    assert assessment.assessment_status == status
    assert assessment.tier == "unknown"
    assert assessment.score is None
    assert assessment.confidence == 0


@pytest.mark.asyncio
async def test_batch_size_limits_requests_for_free_model_quotas():
    responses = []
    for start in (0, 2, 4):
        responses.append(
            {
                "assessments": [
                    _assessment(f"company {number}", score=60, tier="B")
                    for number in range(start, min(start + 2, 5))
                ]
            }
        )
    llm = FakeLLM(responses)
    assessor = CompanyReputationAssessor(llm, batch_size=2)

    result = await assessor.assess([f"Company {number}" for number in range(5)])

    assert len(result) == 5
    assert len(llm.calls) == 3
    assert all(len(json.loads(call["user"])["companies"]) <= 2 for call in llm.calls)


def test_rejects_batches_larger_than_openrouter_free_model_limit():
    with pytest.raises(ValueError, match="between 1 and 20"):
        CompanyReputationAssessor(FakeLLM([]), batch_size=21)
