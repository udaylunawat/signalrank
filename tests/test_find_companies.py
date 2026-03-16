"""
tests/test_find_companies.py — unit tests for scripts/find_companies.py
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# find_companies.py lives in scripts/ — add that to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import find_companies as fc

# ── fixtures ──────────────────────────────────────────────────────────────────

VALID_JSON = json.dumps({
    "companies": [
        {
            "name": "icertis",
            "tier": "1",
            "location": "pune",
            "salary_est_lpa": "55-80",
            "reason": "Pune HQ, contract AI",
            "careers_url": "https://icertis.com/careers",
            "linkedin_search_url": "https://linkedin.com/jobs/search?q=icertis",
        }
    ]
})


def _make_completion(content: str, finish_reason: str = "stop", tool_calls=None) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    msg.role = "assistant"

    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish_reason

    response = MagicMock()
    response.choices = [choice]
    return response


def _make_tool_call(name: str, arguments: dict) -> MagicMock:
    func = MagicMock()
    func.name = name
    func.arguments = json.dumps(arguments)

    tc = MagicMock()
    tc.id = "call_123"
    tc.function = func
    return tc


def test_happy_path_writes_yaml(tmp_path):
    resume = tmp_path / "resume.tex"
    resume.write_text("Senior AI Platform Engineer, 7 YOE, GCP, Kubernetes")
    output = tmp_path / "out.yaml"

    with patch("find_companies.litellm.completion", return_value=_make_completion(VALID_JSON)):
        fc.run(
            resume_path=resume,
            output_path=output,
            model="openrouter/google/gemini-2.0-flash-exp:free",
            api_key="test-key",
        )

    assert output.exists()
    data = yaml.safe_load(output.read_text())
    assert "companies" in data
    assert data["companies"][0]["name"] == "icertis"
    assert data["companies"][0]["tier"] == "1"
    assert data["companies"][0]["careers_url"] == "https://icertis.com/careers"


def test_tool_use_round_trip(tmp_path):
    resume = tmp_path / "resume.tex"
    resume.write_text("some resume")
    output = tmp_path / "out.yaml"

    tool_call = _make_tool_call("web_search", {"query": "icertis pune careers"})
    first_response = _make_completion("", finish_reason="tool_calls", tool_calls=[tool_call])
    final_response = _make_completion(VALID_JSON)

    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        return first_response if call_count["n"] == 1 else final_response

    fake_results = [{"title": "Icertis Careers", "href": "https://icertis.com/careers", "body": "AI roles"}]

    with patch("find_companies.litellm.completion", side_effect=side_effect), \
         patch("find_companies.ddg_search", return_value=fake_results):
        fc.run(
            resume_path=resume,
            output_path=output,
            model="openrouter/google/gemini-2.0-flash-exp:free",
            api_key="test-key",
        )

    assert output.exists()
    assert call_count["n"] == 2


def test_json_parse_failure_exits(tmp_path, capsys):
    resume = tmp_path / "resume.tex"
    resume.write_text("some resume")
    output = tmp_path / "out.yaml"

    with patch("find_companies.litellm.completion", return_value=_make_completion("not valid json")):
        with pytest.raises(SystemExit) as exc:
            fc.run(
                resume_path=resume,
                output_path=output,
                model="openrouter/google/gemini-2.0-flash-exp:free",
                api_key="test-key",
            )

    assert exc.value.code != 0
    assert not output.exists()
    assert "Error" in capsys.readouterr().err


def test_loop_runaway_raises(tmp_path):
    resume = tmp_path / "resume.tex"
    resume.write_text("some resume")
    output = tmp_path / "out.yaml"

    tool_call = _make_tool_call("web_search", {"query": "test"})
    always_tool = _make_completion("", finish_reason="tool_calls", tool_calls=[tool_call])

    fake_results = [{"title": "x", "href": "http://x.com", "body": "y"}]

    with patch("find_companies.litellm.completion", return_value=always_tool), \
         patch("find_companies.ddg_search", return_value=fake_results):
        with pytest.raises(RuntimeError, match="exceeded max iterations"):
            fc.run(
                resume_path=resume,
                output_path=output,
                model="openrouter/google/gemini-2.0-flash-exp:free",
                api_key="test-key",
            )


def test_missing_resume_exits(tmp_path, capsys):
    output = tmp_path / "out.yaml"

    with pytest.raises(SystemExit) as exc:
        fc.run(
            resume_path=Path("/nonexistent/resume.tex"),
            output_path=output,
            model="openrouter/google/gemini-2.0-flash-exp:free",
            api_key="test-key",
        )

    assert exc.value.code != 0
    assert "Error" in capsys.readouterr().err


def test_missing_api_key_exits(monkeypatch, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with patch("sys.argv", ["find_companies.py"]):
        with pytest.raises(SystemExit) as exc:
            fc.main()

    assert exc.value.code != 0
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err
