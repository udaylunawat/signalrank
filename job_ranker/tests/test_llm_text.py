from unittest.mock import patch, MagicMock
from job_ranker.llm.client import llm_text


def _mock_response(text: str):
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_llm_text_returns_string(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("job_ranker.llm.client.OPENROUTER_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_response("## Section\nSome text")

    with patch("job_ranker.llm.client._sync_client", return_value=mock_client):
        result = llm_text("system", "user", model_pool=["test/model"])

    assert isinstance(result, str)
    assert "Section" in result


def test_llm_text_no_api_key(monkeypatch):
    # Must patch the module-level constant too — it's read at import time, not call time
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("job_ranker.llm.client.OPENROUTER_API_KEY", None)
    result = llm_text("system", "user", model_pool=["test/model"])
    assert result == ""


def test_llm_text_all_models_fail(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("job_ranker.llm.client.OPENROUTER_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API error")

    with patch("job_ranker.llm.client._sync_client", return_value=mock_client):
        result = llm_text("system", "user", model_pool=["test/model"])

    assert result == ""


def test_llm_text_uses_model_pool_in_order(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("job_ranker.llm.client.OPENROUTER_API_KEY", "test-key")
    call_log = []

    def fake_create(**kwargs):
        call_log.append(kwargs["model"])
        if kwargs["model"] == "model-a":
            raise Exception("unavailable")
        return _mock_response("ok")

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = fake_create

    with patch("job_ranker.llm.client._sync_client", return_value=mock_client):
        result = llm_text("sys", "usr", model_pool=["model-a", "model-b"])

    assert call_log == ["model-a", "model-b"]
    assert result == "ok"
