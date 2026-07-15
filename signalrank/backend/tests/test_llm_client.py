from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llm.openrouter import (
    FALLBACK_MODELS,
    MAX_REQUEST_ATTEMPTS,
    OpenRouterClient,
    PreflightStatus,
    _extract_json,
)


def test_extract_json_from_clean():
    raw = '{"skills": ["python", "ml"]}'
    assert _extract_json(raw) == {"skills": ["python", "ml"]}


def test_extract_json_from_markdown_fence():
    raw = '```json\n{"name": "test"}\n```'
    assert _extract_json(raw) == {"name": "test"}


def test_extract_json_from_surrounding_text():
    raw = 'Here is the result: {"ok": true} hope that helps!'
    assert _extract_json(raw) == {"ok": True}


def test_extract_json_returns_none_on_garbage():
    assert _extract_json("no json here") is None


def test_default_uses_managed_free_router():
    assert FALLBACK_MODELS == ["openrouter/free"]


def _mock_success_response(
    content: str,
    *,
    model: str = "test/actual-model:free",
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "id": "generation-123",
        "created": 123,
        "model": model,
        "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        "choices": [{"message": {"content": content}}],
    }
    resp.raise_for_status = MagicMock()
    return resp


def _mock_error_response(status_code: int = 500) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = {}
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=MagicMock(),
        response=resp,
    )
    return resp


def _mock_no_choices_response() -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "error": {"code": 429, "message": "Upstream model temporarily unavailable"}
    }
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_client_returns_json_on_success():
    client = OpenRouterClient(api_key="test-key")
    mock_resp = _mock_success_response('{"result": "ok"}')

    with patch.object(client._http, "post", AsyncMock(return_value=mock_resp)):
        result = await client.llm_json("test prompt")

    assert result == {"result": "ok"}
    assert client.last_model == "test/actual-model:free"
    assert client.last_metadata is not None
    assert client.last_metadata.request_id == "generation-123"
    assert client.last_metadata.usage == {
        "prompt_tokens": 2,
        "completion_tokens": 3,
    }


@pytest.mark.asyncio
async def test_client_retries_http_200_response_without_choices():
    client = OpenRouterClient(api_key="test-key")
    with patch.object(
        client._http,
        "post",
        AsyncMock(
            side_effect=[
                _mock_no_choices_response(),
                _mock_success_response('{"result": "ok"}'),
            ]
        ),
    ) as post:
        result = await client.llm_json("test prompt")

    assert result == {"result": "ok"}
    assert post.await_count == 2


@pytest.mark.asyncio
async def test_client_returns_error_dict_on_500():
    client = OpenRouterClient(api_key="test-key")
    mock_resp = _mock_error_response(500)

    with (
        patch.object(client._http, "post", AsyncMock(return_value=mock_resp)) as post,
        patch("llm.openrouter.asyncio.sleep", AsyncMock()),
    ):
        result = await client.llm_json("test prompt")

    assert result["_error"] == "http_error"
    assert result["_status_code"] == 500
    assert result["_retryable"] is True
    assert post.await_count == MAX_REQUEST_ATTEMPTS


@pytest.mark.asyncio
async def test_client_text_returns_string():
    client = OpenRouterClient(api_key="test-key")
    mock_resp = _mock_success_response("Hello world")

    with patch.object(client._http, "post", AsyncMock(return_value=mock_resp)):
        result = await client.llm_text("system", "user msg")

    assert result == "Hello world"


@pytest.mark.asyncio
async def test_client_text_returns_empty_on_failure():
    client = OpenRouterClient(api_key="test-key")
    mock_resp = _mock_error_response(500)

    with (
        patch.object(client._http, "post", AsyncMock(return_value=mock_resp)),
        patch("llm.openrouter.asyncio.sleep", AsyncMock()),
    ):
        result = await client.llm_text("system", "user msg")

    assert result == ""
    assert client.last_error is not None
    assert client.last_error.code == "http_error"


@pytest.mark.asyncio
async def test_client_routes_ordered_models_in_one_request():
    client = OpenRouterClient(
        api_key="test-key", models=["model-a:free", "model-b:free"]
    )
    mock_resp = _mock_success_response('{"result": "ok"}', model="model-b:free")

    with patch.object(client._http, "post", AsyncMock(return_value=mock_resp)) as post:
        result = await client.llm_json("test prompt")

    assert result == {"result": "ok"}
    assert post.await_count == 1
    payload = post.await_args.kwargs["json"]
    assert payload["models"] == ["model-a:free", "model-b:free"]
    assert "model" not in payload
    assert client.last_model == "model-b:free"


@pytest.mark.asyncio
async def test_client_sends_strict_response_schema():
    client = OpenRouterClient(api_key="test-key")
    mock_resp = _mock_success_response('{"score": 91}')
    schema = {
        "type": "object",
        "properties": {"score": {"type": "integer"}},
        "required": ["score"],
        "additionalProperties": False,
    }

    with patch.object(client._http, "post", AsyncMock(return_value=mock_resp)) as post:
        result = await client.llm_json("test prompt", response_schema=schema)

    assert result == {"score": 91}
    payload = post.await_args.kwargs["json"]
    assert payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "signalrank_response",
            "strict": True,
            "schema": schema,
        },
    }
    assert payload["provider"] == {"require_parameters": True}
    assert payload["reasoning"] == {"effort": "none", "exclude": True}


@pytest.mark.asyncio
async def test_structured_404_retries_once_with_discovered_free_models():
    client = OpenRouterClient(api_key="test-key")
    schema = {
        "type": "object",
        "properties": {"score": {"type": "integer"}},
        "required": ["score"],
        "additionalProperties": False,
    }
    with (
        patch.object(
            client._http,
            "post",
            AsyncMock(
                side_effect=[
                    _mock_error_response(404),
                    _mock_success_response('{"score": 91}', model="model-b:free"),
                ]
            ),
        ) as post,
        patch.object(
            client,
            "preflight",
            AsyncMock(
                return_value=PreflightStatus(
                    status="ready",
                    authenticated=True,
                    compatible_free_models=("model-a:free", "model-b:free"),
                )
            ),
        ),
    ):
        result = await client.llm_json("test prompt", response_schema=schema)

    assert result == {"score": 91}
    assert post.await_count == 2
    assert post.await_args_list[0].kwargs["json"]["model"] == "openrouter/free"
    assert post.await_args_list[1].kwargs["json"]["models"] == [
        "model-a:free",
        "model-b:free",
    ]


@pytest.mark.asyncio
async def test_empty_structured_completion_retries_with_discovered_free_models():
    client = OpenRouterClient(api_key="test-key")
    schema = {
        "type": "object",
        "properties": {"score": {"type": "integer"}},
        "required": ["score"],
        "additionalProperties": False,
    }
    empty = _mock_success_response("", model="reasoning-model:free")
    with (
        patch.object(
            client._http,
            "post",
            AsyncMock(
                side_effect=[
                    empty,
                    _mock_success_response('{"score": 91}', model="model-a:free"),
                ]
            ),
        ) as post,
        patch.object(
            client,
            "preflight",
            AsyncMock(
                return_value=PreflightStatus(
                    status="ready",
                    authenticated=True,
                    compatible_free_models=("model-a:free", "model-b:free"),
                )
            ),
        ),
    ):
        result = await client.llm_json("test prompt", response_schema=schema)

    assert result == {"score": 91}
    assert post.await_count == 2
    assert post.await_args_list[1].kwargs["json"]["models"] == [
        "model-a:free",
        "model-b:free",
    ]
    assert client.last_model == "model-a:free"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_client_never_retries_auth_failures(status_code):
    client = OpenRouterClient(api_key="secret-key", models=["a:free", "b:free"])
    mock_resp = _mock_error_response(status_code)

    with patch.object(client._http, "post", AsyncMock(return_value=mock_resp)) as post:
        result = await client.llm_json("test prompt")

    assert result == {
        "_error": "auth_failed",
        "_details": "OpenRouter rejected the configured API key",
        "_retryable": False,
        "_status_code": status_code,
    }
    assert post.await_count == 1


@pytest.mark.asyncio
async def test_preflight_reports_auth_and_dynamic_free_structured_models():
    client = OpenRouterClient(api_key="secret-key")
    key_response = MagicMock(spec=httpx.Response)
    key_response.raise_for_status = MagicMock()
    key_response.json.return_value = {
        "data": {"is_free_tier": True, "limit_remaining": 7}
    }
    models_response = MagicMock(spec=httpx.Response)
    models_response.raise_for_status = MagicMock()
    models_response.json.return_value = {
        "data": [
            {
                "id": "vendor/structured:free",
                "supported_parameters": ["response_format"],
            },
            {"id": "vendor/unstructured:free", "supported_parameters": []},
            {
                "id": "vendor/paid",
                "supported_parameters": ["structured_outputs"],
            },
        ]
    }

    with patch.object(
        client._http,
        "get",
        AsyncMock(side_effect=[key_response, models_response]),
    ) as get:
        status = await client.preflight()

    assert status.status == "ready"
    assert status.authenticated is True
    assert status.is_free_tier is True
    assert status.limit_remaining == 7
    assert status.compatible_free_models == ("vendor/structured:free",)
    assert "secret-key" not in str(status.as_dict())
    assert get.await_count == 2


@pytest.mark.asyncio
async def test_preflight_auth_failure_is_key_safe_and_not_retried():
    client = OpenRouterClient(api_key="secret-key")
    response = _mock_error_response(401)

    with patch.object(client._http, "get", AsyncMock(return_value=response)) as get:
        status = await client.preflight()

    assert status.status == "auth_failed"
    assert status.authenticated is False
    assert "secret-key" not in str(status.as_dict())
    assert get.await_count == 1
