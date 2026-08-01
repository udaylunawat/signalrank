"""Run a bounded, opt-in OpenRouter release probe with a synthetic resume signal."""

import argparse
import json
import os
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    def emit(result: dict) -> None:
        serialized = json.dumps(result)
        print(serialized)
        if args.output:
            args.output.write_text(f"{serialized}\n", encoding="utf-8")

    if os.environ.get("SIGNALRANK_LIVE_RELEASE") != "1":
        emit(
            {
                "case_id": "REL-01",
                "status": "blocked",
                "reason": "SIGNALRANK_LIVE_RELEASE=1 is required for live calls",
            }
        )
        return 2

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        emit(
            {
                "case_id": "REL-01",
                "status": "blocked",
                "reason": "OPENROUTER_API_KEY is not set",
            }
        )
        return 2

    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Classify this synthetic resume signal as valid JSON: Python, "
                    "SQL, five years of software work."
                ),
            }
        ],
        "max_tokens": 32,
        "temperature": 0,
    }
    started = time.monotonic()
    try:
        response = httpx.post(
            f"{args.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=20,
        )
        elapsed_ms = round((time.monotonic() - started) * 1000)
        if response.status_code >= 400:
            emit(
                {
                    "case_id": "REL-01",
                    "status": "fail",
                    "http_status": response.status_code,
                    "latency_ms": elapsed_ms,
                }
            )
            return 1
        body = response.json()
        emit(
            {
                "case_id": "REL-01",
                "status": "pass",
                "model": body.get("model", args.model),
                "finish_reason": body.get("choices", [{}])[0].get("finish_reason"),
                "latency_ms": elapsed_ms,
            }
        )
        return 0
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:
        emit(
            {
                "case_id": "REL-01",
                "status": "fail",
                "error_type": type(error).__name__,
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
