from __future__ import annotations

import os
from typing import Any

import httpx


def _base_url() -> str:
    return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def _api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "")


def _model() -> str:
    return os.getenv("OPENROUTER_MODEL", "openrouter/auto")


class LlmError(RuntimeError):
    pass


async def chat_completion(messages: list[dict[str, Any]]) -> str:
    api_key = _api_key()
    if not api_key:
        raise LlmError("Missing OPENROUTER_API_KEY env var")

    url = f"{_base_url()}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        # Optional but recommended by OpenRouter
        "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost"),
        "X-Title": os.getenv("OPENROUTER_APP_TITLE", "omnivoice-chat"),
    }

    payload = {
        "model": _model(),
        "messages": messages,
        "temperature": 0.7,
    }

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code >= 400:
        raise LlmError(f"OpenRouter error {resp.status_code}: {resp.text[:5000]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LlmError(f"Unexpected OpenRouter response: {e}; data={str(data)[:2000]}")

