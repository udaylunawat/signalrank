from unittest.mock import AsyncMock

import pytest

from llm.resume_parser import (
    ResumeParseResult,
    _heuristic_parse,
    _validate_extraction,
    parse_resume,
)


def test_heuristic_fallback_cleans_pdf_spacing_and_location_suffixes():
    result = _heuristic_parse("""Technical Skills
Languages Java, JavaScript, TypeScript
Automation Playwright, Selenium W ebDriver, TestNG
T esting Types Functional T esting, Regression T esting
Professional Experience
QA Engineer / Functional T ester Pune, India
QA Engineer India
""")

    assert result.skills[:3] == ["Java", "JavaScript", "TypeScript"]
    assert "Selenium WebDriver" in result.skills
    assert result.recent_titles == [
        "QA Engineer / Functional Tester",
        "QA Engineer",
    ]


def test_validate_extraction_with_valid_data():
    data = {
        "skills": ["python", "ml", "pytorch"],
        "years_of_experience": 5,
        "recent_titles": ["ML Engineer", "Data Scientist"],
        "industries": ["tech", "finance"],
        "education": ["MS Computer Science"],
        "intent_suggestions": {
            "role_aliases": ["Machine Learning Engineer"],
            "seniority_band": "senior",
        },
    }
    result = _validate_extraction(data)
    assert isinstance(result, ResumeParseResult)
    assert result.skills == ["python", "ml", "pytorch"]
    assert result.years_of_experience == 5
    assert result.intent_suggestions == {
        "role_aliases": ["Machine Learning Engineer"],
        "seniority_band": "senior",
    }


def test_validate_extraction_with_missing_keys():
    data = {"skills": ["python"]}
    result = _validate_extraction(data)
    assert result.skills == ["python"]
    assert result.years_of_experience is None
    assert result.recent_titles == []


def test_validate_extraction_with_garbage():
    data = {"_error": "llm_failed"}
    result = _validate_extraction(data)
    assert result.skills == []


def test_validate_extraction_coerces_types():
    data = {
        "skills": "python, ml",
        "years_of_experience": "5",
        "recent_titles": "ML Engineer",
    }
    result = _validate_extraction(data)
    assert result.skills == ["python, ml"]
    assert result.years_of_experience == 5
    assert result.recent_titles == ["ML Engineer"]


@pytest.mark.asyncio
async def test_parse_resume_returns_result():
    mock_client = AsyncMock()
    mock_client.llm_json.return_value = {
        "skills": ["python", "tensorflow"],
        "years_of_experience": 3,
        "recent_titles": ["Software Engineer"],
        "industries": ["tech"],
        "education": ["BS CS"],
    }

    result = await parse_resume(
        resume_text="I am a software engineer with 3 years of Python experience.",
        llm_client=mock_client,
    )
    assert isinstance(result, ResumeParseResult)
    assert "python" in result.skills
    mock_client.llm_json.assert_called_once()


@pytest.mark.asyncio
async def test_parse_resume_fails_open():
    mock_client = AsyncMock()
    mock_client.llm_json.return_value = {"_error": "llm_failed"}

    result = await parse_resume(
        resume_text="Some resume text",
        llm_client=mock_client,
    )
    assert isinstance(result, ResumeParseResult)
    assert result.skills == []
