# llm/client.py
"""
Resilient LLM client for Job Ranker.

- Discovers working free models (OpenRouter)
- Refreshes model pool every 3 days
- Uses disk cache + TTL
- Retries with exponential backoff + jitter
- JSON-only enforcement
- Graceful degradation (LLMs are advisory)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Iterable, List

import aiohttp
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI, RateLimitError

logger = logging.getLogger(__name__)


# --------------------------------------------------
# ENV / CONFIG
# --------------------------------------------------
load_dotenv()
logging.getLogger("openai").setLevel(logging.WARNING)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
MODELS_ENDPOINT = f"{BASE_URL}/models"

CACHE_DIR = Path("cache/llm")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_TTL = 86400  # 24h
MODEL_REFRESH_TTL = 3 * 24 * 3600  # 3 days
MAX_RETRIES_PER_MODEL = 1
MAX_DISCOVERY_MODELS = 5

MODEL_POOL_PATH = Path("telemetry/working_models.json")

# Used ONLY if no discovered models exist yet
DEFAULT_MODEL_POOL = [
    "google/gemini-2.0-flash-exp:free",
    "google/gemma-3-4b-it:free",
    "mistralai/devstral-2512:free",
]


# --------------------------------------------------
# CLIENTS
# --------------------------------------------------
def _sync_client():
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=BASE_URL)


def _async_client():
    return AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=BASE_URL,
        default_headers={
            "HTTP-Referer": "http://localhost",
            "X-Title": "job-ranker-llm-probe",
        },
    )


# --------------------------------------------------
# UTIL
# --------------------------------------------------
def _jitter_sleep(attempt: int):
    base = min(2**attempt, 8)
    time.sleep(base + random.uniform(0.3, 1.1))


def _extract_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    return json.loads(raw[start : end + 1])


def _cache_path(model: str, prompt: str) -> Path:
    key = hashlib.md5((model + prompt).encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


# --------------------------------------------------
# MODEL POOL MANAGEMENT
# --------------------------------------------------
def _model_pool_is_stale() -> bool:
    if not MODEL_POOL_PATH.exists():
        return True
    age = time.time() - MODEL_POOL_PATH.stat().st_mtime
    return age > MODEL_REFRESH_TTL


def load_model_pool() -> List[str]:
    """
    Priority:
    1. Fresh discovered working models
    2. Stale discovered models (still usable)
    3. DEFAULT_MODEL_POOL (bootstrap only)
    """
    if MODEL_POOL_PATH.exists():
        try:
            data = json.loads(MODEL_POOL_PATH.read_text())
            models = data.get("models", [])
            if models:
                return models
            if not models:
                logger.warning(
                    "[LLM] Discovered model pool empty; falling back to defaults"
                )
        except Exception:
            pass

    return DEFAULT_MODEL_POOL.copy()


def save_model_pool(models: Iterable[str]):
    MODEL_POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_POOL_PATH.write_text(
        json.dumps(
            {
                "generated_at": int(time.time()),
                "models": list(models),
            },
            indent=2,
        )
    )


# --------------------------------------------------
# FREE MODEL DISCOVERY
# --------------------------------------------------
async def _fetch_free_models() -> List[str]:
    async with aiohttp.ClientSession() as session:
        async with session.get(MODELS_ENDPOINT) as resp:
            data = await resp.json()

    free = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
            free.append(m["id"])
    return free[:MAX_DISCOVERY_MODELS]


async def _probe_model(model: str, client: AsyncOpenAI) -> bool:
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": 'Return JSON only: {"ok": true}'}],
            temperature=0,
            max_tokens=10,
        )
        raw = resp.choices[0].message.content.strip()
        _ = _extract_json(raw)
        return True
    except Exception:
        return False


def discover_working_models() -> List[str]:
    """
    Runs lightweight probes and returns a list of model IDs
    that passed all sanity checks.
    """

    if not OPENROUTER_API_KEY:
        return []

    async def _run():
        candidates = await _fetch_free_models()
        client = _async_client()
        semaphore = asyncio.Semaphore(2)

        async def guarded(model):
            async with semaphore:
                ok = await _probe_model(model, client)
                await asyncio.sleep(1.0)
                return model if ok else None

        tasks = [guarded(m) for m in candidates]
        results = await asyncio.gather(*tasks)
        return [m for m in results if m]

    try:
        return asyncio.run(_run())
    except Exception:
        return []


# --------------------------------------------------
# MAIN ENTRY
# --------------------------------------------------
def llm_json(prompt: str, *, max_tokens: int = 512) -> dict:
    if not OPENROUTER_API_KEY:
        return {"_error": "llm_disabled", "_details": "Missing OPENROUTER_API_KEY"}

    # Refresh working models every 3 days
    if _model_pool_is_stale():
        discovered = discover_working_models()
        if discovered:
            save_model_pool(discovered)

    model_pool = load_model_pool()
    client = _sync_client()
    last_error = None

    for model in model_pool:
        cache_path = _cache_path(model, prompt)

        if cache_path.exists():
            if time.time() - cache_path.stat().st_mtime < CACHE_TTL:
                return json.loads(cache_path.read_text())

        for attempt in range(MAX_RETRIES_PER_MODEL):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=max_tokens,
                )

                raw = resp.choices[0].message.content.strip()
                data = _extract_json(raw)
                cache_path.write_text(json.dumps(data, indent=2))
                return data

            except RateLimitError as e:
                last_error = e
                _jitter_sleep(attempt)

            except Exception as e:
                last_error = e

                # Fast fail on auth issues
                if "401" in str(e) or "Unauthorized" in str(e):
                    return {
                        "_error": "llm_auth_failed",
                        "_details": "OpenRouter API key invalid or missing",
                    }
                break

    return {
        "_error": "llm_failed",
        "_details": str(last_error),
    }


def llm_text(
    system_prompt: str,
    user_message: str,
    *,
    model_pool: list[str] | None = None,
    max_tokens: int = 2048,
    timeout: int = 60,
) -> str:
    """
    Like llm_json() but returns raw text (no JSON parsing).
    Falls through model_pool until one succeeds.
    Returns empty string on complete failure — never raises.
    """
    if not OPENROUTER_API_KEY:
        logger.warning("[LLM] llm_text: OPENROUTER_API_KEY not set, skipping")
        return ""

    if model_pool is None:
        if _model_pool_is_stale():
            discovered = discover_working_models()
            if discovered:
                save_model_pool(discovered)
        pool = load_model_pool()
    else:
        pool = model_pool
    client = _sync_client()

    for model in pool:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            return (resp.choices[0].message.content or "").strip()
        except RateLimitError:
            logger.warning("[LLM] llm_text: rate limited on %s, sleeping before next", model)
            _jitter_sleep(0)
        except Exception as e:
            if "401" in str(e) or "Unauthorized" in str(e):
                logger.error("[LLM] llm_text: auth failed")
                return ""
            logger.warning("[LLM] llm_text: %s failed: %s", model, e)

    logger.error("[LLM] llm_text: all models exhausted")
    return ""


# Backward compatibility
def cached_llm_call(prompt: str, *, model: str | None = None) -> dict:
    return llm_json(prompt)
