from __future__ import annotations

import os
from time import perf_counter
from typing import Any

import httpx

from .timing_log import get_timing_logger

_timing = get_timing_logger()


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
    model_id = payload["model"]
    msg_count = len(messages)
    t0 = perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
    elapsed_ms = (perf_counter() - t0) * 1000.0

    if resp.status_code >= 400:
        _timing.info(
            "timing event=openrouter_chat model=%s messages=%d status=%d elapsed_ms=%.1f ok=0",
            model_id,
            msg_count,
            resp.status_code,
            elapsed_ms,
        )
        raise LlmError(f"OpenRouter error {resp.status_code}: {resp.text[:5000]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        _timing.info(
            "timing event=openrouter_chat model=%s messages=%d status=%d elapsed_ms=%.1f ok=0 parse_error=1",
            model_id,
            msg_count,
            resp.status_code,
            elapsed_ms,
        )
        raise LlmError(f"Unexpected OpenRouter response: {e}; data={str(data)[:2000]}")

    _timing.info(
        "timing event=openrouter_chat model=%s messages=%d status=%d elapsed_ms=%.1f "
        "response_chars=%d ok=1",
        model_id,
        msg_count,
        resp.status_code,
        elapsed_ms,
        len(content),
    )
    return content

