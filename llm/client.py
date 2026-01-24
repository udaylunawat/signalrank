import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"

CACHE_DIR = Path("cache/llm")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "mistralai/mistral-7b-instruct"

_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=BASE_URL)


def llm_json(prompt: str, *, model: str = DEFAULT_MODEL, max_tokens: int = 512) -> dict:
    """
    Cached, deterministic JSON-only LLM call.
    """
    key = hashlib.md5((model + prompt).encode()).hexdigest()
    path = CACHE_DIR / f"{key}.json"

    if path.exists():
        return json.loads(path.read_text())

    resp = _client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=max_tokens,
    )

    text = resp.choices[0].message.content
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("LLM did not return JSON")

    data = json.loads(text[start:end + 1])
    path.write_text(json.dumps(data, indent=2))
    return data


# --------------------------------------------------
# BACKWARD-COMPATIBILITY ALIAS (IMPORTANT)
# --------------------------------------------------
def cached_llm_call(prompt: str, *, model: str = DEFAULT_MODEL) -> dict:
    """
    Backward-compatible alias.
    Do NOT remove – older modules depend on this name.
    """
    return llm_json(prompt, model=model)