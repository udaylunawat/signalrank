import asyncio
import json
import logging
import random
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# The free router is intentionally the only static default. Its eligible models are
# maintained by OpenRouter; concrete free model IDs are discovered during preflight.
FALLBACK_MODELS = ["openrouter/free"]

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
MODELS_URL = "https://openrouter.ai/api/v1/models"
MAX_REQUEST_ATTEMPTS = 3


def _extract_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


@dataclass(frozen=True)
class CallMetadata:
    model: str | None
    requested_models: tuple[str, ...]
    request_id: str | None
    created: int | None
    usage: dict[str, Any] | None
    latency_ms: int


@dataclass(frozen=True)
class LLMError:
    code: str
    details: str
    status_code: int | None = None
    retryable: bool = False

    def as_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "_error": self.code,
            "_details": self.details,
            "_retryable": self.retryable,
        }
        if self.status_code is not None:
            result["_status_code"] = self.status_code
        return result


@dataclass(frozen=True)
class PreflightStatus:
    status: str
    authenticated: bool
    is_free_tier: bool | None = None
    limit_remaining: float | None = None
    compatible_free_models: tuple[str, ...] = ()
    details: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _CallResponse:
    content: str
    metadata: CallMetadata


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        models: list[str] | None = None,
        timeout: float = 90.0,
    ):
        self.api_key = api_key
        self.models = list(models or FALLBACK_MODELS)
        self._http = httpx.AsyncClient(timeout=timeout)
        self.last_model: str | None = None
        self.last_metadata: CallMetadata | None = None
        self.last_error: LLMError | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://signalrank.app",
            "X-Title": "SignalRank",
        }

    def _set_error(
        self,
        code: str,
        details: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> LLMError:
        error = LLMError(
            code=code,
            details=details,
            status_code=status_code,
            retryable=retryable,
        )
        self.last_error = error
        return error

    @staticmethod
    def _supports_structured_outputs(model: dict[str, Any]) -> bool:
        supported = model.get("supported_parameters") or []
        return "structured_outputs" in supported or "response_format" in supported

    async def preflight(self) -> PreflightStatus:
        if not self.api_key.strip():
            self._set_error("missing_key", "OpenRouter API key is not configured")
            return PreflightStatus(
                status="missing_key",
                authenticated=False,
                details="OpenRouter API key is not configured",
            )

        try:
            key_response = await self._http.get(KEY_URL, headers=self._headers())
            key_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in (401, 403):
                self._set_error(
                    "auth_failed",
                    "OpenRouter rejected the configured API key",
                    status_code=status_code,
                )
                return PreflightStatus(
                    status="auth_failed",
                    authenticated=False,
                    details="OpenRouter authentication failed",
                )
            self._set_error(
                "preflight_failed",
                f"OpenRouter key check returned HTTP {status_code}",
                status_code=status_code,
                retryable=status_code == 429 or status_code >= 500,
            )
            return PreflightStatus(
                status="unavailable",
                authenticated=False,
                details=f"OpenRouter key check returned HTTP {status_code}",
            )
        except (httpx.HTTPError, ValueError) as exc:
            self._set_error("preflight_failed", str(exc), retryable=True)
            return PreflightStatus(
                status="unavailable",
                authenticated=False,
                details="OpenRouter preflight request failed",
            )

        try:
            key_data = key_response.json().get("data", {})
        except (ValueError, AttributeError) as exc:
            self._set_error("preflight_failed", str(exc), retryable=True)
            return PreflightStatus(
                status="unavailable",
                authenticated=True,
                details="OpenRouter key check returned an invalid response",
            )
        if not isinstance(key_data, dict):
            self._set_error(
                "preflight_failed",
                "OpenRouter key check returned malformed data",
                retryable=True,
            )
            return PreflightStatus(
                status="unavailable",
                authenticated=True,
                details="OpenRouter key check returned an invalid response",
            )
        try:
            models_response = await self._http.get(
                MODELS_URL,
                headers=self._headers(),
                params={"output_modalities": "text"},
            )
            models_response.raise_for_status()
            models = models_response.json().get("data", [])
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            self._set_error("model_discovery_failed", str(exc), retryable=True)
            return PreflightStatus(
                status="model_discovery_failed",
                authenticated=True,
                is_free_tier=key_data.get("is_free_tier"),
                limit_remaining=key_data.get("limit_remaining"),
                details="Authenticated, but model discovery failed",
            )

        compatible = tuple(
            model["id"]
            for model in models
            if isinstance(model, dict)
            and isinstance(model.get("id"), str)
            and model["id"].endswith(":free")
            and self._supports_structured_outputs(model)
        )
        self.last_error = None
        return PreflightStatus(
            status="ready" if compatible else "no_compatible_free_model",
            authenticated=True,
            is_free_tier=key_data.get("is_free_tier"),
            limit_remaining=key_data.get("limit_remaining"),
            compatible_free_models=compatible,
            details=(
                None if compatible else "No structured-output free model is available"
            ),
        )

    def _request_payload(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        response_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if len(self.models) == 1:
            payload["model"] = self.models[0]
        else:
            payload["models"] = self.models

        if response_schema is None:
            payload["response_format"] = {"type": "json_object"}
        else:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "signalrank_response",
                    "strict": True,
                    "schema": response_schema,
                },
            }
            payload["provider"] = {"require_parameters": True}
            payload["reasoning"] = {"effort": "none", "exclude": True}
        return payload

    async def _call(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        *,
        response_schema: dict[str, Any] | None = None,
        json_response: bool = False,
    ) -> _CallResponse | None:
        self.last_error = None
        self.last_model = None
        self.last_metadata = None
        if not self.api_key.strip():
            self._set_error("missing_key", "OpenRouter API key is not configured")
            return None

        payload: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if len(self.models) == 1:
            payload["model"] = self.models[0]
        else:
            payload["models"] = self.models
        if json_response:
            payload.update(
                self._request_payload(
                    messages,
                    max_tokens,
                    temperature,
                    response_schema,
                )
            )

        for attempt in range(MAX_REQUEST_ATTEMPTS):
            started = time.monotonic()
            try:
                response = await self._http.post(
                    BASE_URL,
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices") if isinstance(data, dict) else None
                if not isinstance(choices, list) or not choices:
                    if attempt < MAX_REQUEST_ATTEMPTS - 1:
                        logger.warning(
                            "OpenRouter returned HTTP 200 without choices; retrying request"
                        )
                        continue
                    self._set_error(
                        "invalid_response",
                        "OpenRouter returned a response without choices",
                        retryable=True,
                    )
                    return None
                message = choices[0].get("message")
                if not isinstance(message, dict):
                    raise TypeError("OpenRouter response message is malformed")
                content = message.get("content")
                metadata = CallMetadata(
                    model=data.get("model"),
                    requested_models=tuple(self.models),
                    request_id=data.get("id"),
                    created=data.get("created"),
                    usage=(
                        data.get("usage")
                        if isinstance(data.get("usage"), dict)
                        else None
                    ),
                    latency_ms=round((time.monotonic() - started) * 1000),
                )
                self.last_model = metadata.model
                self.last_metadata = metadata
                if not isinstance(content, str) or not content.strip():
                    if response_schema is not None and self.models == FALLBACK_MODELS:
                        preflight = await self.preflight()
                        if preflight.compatible_free_models:
                            self.models = list(preflight.compatible_free_models)
                            payload = self._request_payload(
                                messages,
                                max_tokens,
                                temperature,
                                response_schema,
                            )
                            logger.info(
                                "Free router returned an empty structured completion via %s; retrying with %d compatible free models",
                                metadata.model or "unknown model",
                                len(self.models),
                            )
                            continue
                    self._set_error(
                        "empty_response",
                        "OpenRouter returned an empty completion",
                        retryable=True,
                    )
                    return None
                self.last_error = None
                return _CallResponse(content=content.strip(), metadata=metadata)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code in (401, 403):
                    self._set_error(
                        "auth_failed",
                        "OpenRouter rejected the configured API key",
                        status_code=status_code,
                    )
                    logger.error(
                        "OpenRouter authentication failed with HTTP %d", status_code
                    )
                    return None
                if (
                    status_code == 404
                    and response_schema is not None
                    and self.models == FALLBACK_MODELS
                ):
                    preflight = await self.preflight()
                    if preflight.compatible_free_models:
                        self.models = list(preflight.compatible_free_models)
                        payload = self._request_payload(
                            messages,
                            max_tokens,
                            temperature,
                            response_schema,
                        )
                        logger.info(
                            "Free router lacked structured output; retrying with %d compatible free models",
                            len(self.models),
                        )
                        continue
                retryable = status_code == 429 or status_code >= 500
                if retryable and attempt < MAX_REQUEST_ATTEMPTS - 1:
                    retry_after = exc.response.headers.get("Retry-After")
                    try:
                        sleep_time = float(retry_after) if retry_after else 2**attempt
                    except ValueError:
                        sleep_time = 2**attempt
                    sleep_time = min(sleep_time, 8) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "OpenRouter HTTP %d; retrying request in %.1fs",
                        status_code,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    continue
                self._set_error(
                    "rate_limited" if status_code == 429 else "http_error",
                    f"OpenRouter returned HTTP {status_code}",
                    status_code=status_code,
                    retryable=retryable,
                )
                return None
            except (
                httpx.HTTPError,
                AttributeError,
                IndexError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                self._set_error("request_failed", str(exc), retryable=True)
                logger.warning("OpenRouter request failed: %s", exc)
                return None

        return None

    async def llm_json(
        self,
        prompt: str | None = None,
        *,
        system: str | None = None,
        user: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        response_schema: dict[str, Any] | None = None,
    ) -> dict:
        if system and user:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        else:
            messages = [{"role": "user", "content": prompt or ""}]

        response = await self._call(
            messages,
            max_tokens,
            temperature,
            response_schema=response_schema,
            json_response=True,
        )
        if response is None:
            error = self.last_error or self._set_error(
                "llm_failed", "OpenRouter returned no usable response"
            )
            return error.as_result()

        parsed = _extract_json(response.content)
        if parsed is not None:
            logger.info("llm_json success via %s", self.last_model or "unknown model")
            return parsed

        error = self._set_error(
            "invalid_json",
            "OpenRouter returned a response that was not a JSON object",
        )
        logger.warning("OpenRouter returned non-JSON content")
        return error.as_result()

    async def llm_text(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        response = await self._call(messages, max_tokens, temperature)
        if response is not None:
            logger.info("llm_text success via %s", self.last_model or "unknown model")
            return response.content

        logger.error("OpenRouter llm_text failed: %s", self.last_error)
        return ""

    async def close(self):
        await self._http.aclose()
