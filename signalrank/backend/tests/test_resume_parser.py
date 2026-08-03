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


def test_heuristic_parser_builds_experience_evidence_and_computes_yoe():
    result = _heuristic_parse("""Summary
Engineer with 5 years of experience.
Professional Experience
Machine Learning Engineer | Example Labs | Jan 2022 - Present
- Built production ranking systems with Python.
Data Analyst | Example Analytics | Jan 2020 - Dec 2021
- Developed SQL reporting workflows.
Education
Bachelor of Engineering
""")

    assert result.declared_years_of_experience == 5
    assert result.computed_years_of_experience is not None
    assert result.years_of_experience == 5
    assert result.experiences[0]["company"] == "Example Labs"
    assert "Jan 2022 - Present" in result.experiences[0]["evidence"]
    assert result.field_confidence["experiences"] > 0


def test_declared_yoe_ignores_company_history_claims():
    result = _heuristic_parse(
        "Our company has over 25 years of experience serving customers."
    )

    assert result.declared_years_of_experience is None
    assert result.years_of_experience is None


def test_heuristic_parser_handles_stacked_headings_and_numeric_dates():
    result = _heuristic_parse("""Work Experience
Product Designer
Example Studio
02/2021 - 06/2023
- Designed accessible customer workflows.
Education
Bachelor of Design
""")

    assert result.experiences[0]["title"] == "Product Designer"
    assert result.experiences[0]["company"] == "Example Studio"
    assert result.experiences[0]["start_date"] == "02/2021"
    assert result.computed_years_of_experience == 2


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


def test_validate_extraction_rejects_ungrounded_structured_evidence():
    result = _validate_extraction(
        {
            "skills": ["Python"],
            "recent_titles": [],
            "experiences": [
                {
                    "title": "Chief Scientist",
                    "company": "Invented Co",
                    "start_date": "2020",
                    "end_date": "Present",
                    "responsibilities": [],
                    "evidence": "Chief Scientist at Invented Co",
                }
            ],
            "skill_evidence": [{"name": "Rust", "evidence": "Expert Rust developer"}],
        },
        resume_text="Python Engineer at Example Labs",
    )

    assert result.experiences == []
    assert result.skill_evidence == []
    assert result.skills == ["Python"]


def test_validate_extraction_filters_invented_experience_details():
    resume_text = (
        "Platform Engineer at Example Co Jan 2022 - Present\n"
        "Built reliable Python APIs."
    )
    result = _validate_extraction(
        {
            "experiences": [
                {
                    "title": "Platform Engineer",
                    "company": "Example Co",
                    "start_date": "2022-01",
                    "end_date": "Present",
                    "responsibilities": [
                        "Built reliable Python APIs.",
                        "Managed a global team.",
                    ],
                    "evidence": "Platform Engineer at Example Co Jan 2022 - Present",
                }
            ]
        },
        resume_text=resume_text,
    )

    assert result.experiences[0]["start_date"] is None
    assert result.experiences[0]["end_date"] == "Present"
    assert result.experiences[0]["responsibilities"] == ["Built reliable Python APIs."]


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
