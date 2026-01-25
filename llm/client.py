# llm/client.py
import os
import json
import hashlib
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"

CACHE_DIR = Path("cache/llm")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_TTL = 86400  # 24h

# Ordered by preference
MODEL_POOL = [
    "google/gemini-2.0-flash-exp:free",
    "google/gemma-3-4b-it:free",
    "mistralai/devstral-2512:free",
    "google/gemini-2.5-flash-lite"
]

_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=BASE_URL)


def llm_json(prompt: str, *, max_tokens: int = 512) -> dict:
    last_error = None

    for model in MODEL_POOL:
        key = hashlib.md5((model + prompt).encode()).hexdigest()
        path = CACHE_DIR / f"{key}.json"

        if path.exists():
            if time.time() - path.stat().st_mtime < CACHE_TTL:
                return json.loads(path.read_text())

        try:
            resp = _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=max_tokens,
            )

            raw = resp.choices[0].message.content.strip()
            start, end = raw.find("{"), raw.rfind("}")

            if start == -1 or end == -1:
                raise ValueError("No JSON in response")

            data = json.loads(raw[start:end + 1])
            path.write_text(json.dumps(data, indent=2))
            return data

        except RateLimitError as e:
            last_error = e
            time.sleep(1.5)
            continue

        except Exception as e:
            last_error = e
            continue

    # Final graceful fallback
    return {
        "_error": "llm_failed",
        "_details": str(last_error),
    }


# Backward compatibility
def cached_llm_call(prompt: str, *, model: str = None) -> dict:
    return llm_json(prompt)