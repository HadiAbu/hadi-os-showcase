"""Thin wrapper around an OpenAI-compatible chat API.

Owns client construction, model choice, and the base URL so the rest of the app
never imports ``openai`` directly. When ``LLM_API_KEY`` is unset, ``available()``
is ``False`` and callers must short-circuit to ``503``.

Provider-agnostic: point ``LLM_BASE_URL`` / ``LLM_MODEL`` at Groq (default),
OpenAI, a local Ollama, or any other OpenAI-compatible endpoint. There is no
provider-specific tool runner — ``chat_agent`` drives a manual tool-call loop
over :func:`create_chat`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import get_settings

_client: Any = None


def available() -> bool:
    return bool(get_settings().llm_api_key)


_REQUEST_TIMEOUT_S = 90.0


def _get_client() -> Any:
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        settings = get_settings()
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=_REQUEST_TIMEOUT_S,
            max_retries=1,
        )
    return _client


def chat_model_for(override: str | None = None) -> str:
    """A non-empty per-user model override wins, else the configured default."""
    if isinstance(override, str) and override.strip():
        return override.strip()
    return get_settings().llm_model


def _max_tokens(requested: int | None) -> int:
    """Clamp a caller's request to the configured ``LLM_MAX_TOKENS`` ceiling —
    providers count max_tokens toward the per-minute budget and 413 the whole
    request if it alone exceeds the limit."""
    cap = get_settings().llm_max_tokens
    if requested is None:
        return cap
    return max(1, min(requested, cap))


async def create_chat(
    *,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tokens: int | None = None,
) -> Any:
    """One non-streaming chat completion. Returns the raw SDK response;
    ``resp.choices[0].message`` has ``.content`` and ``.tool_calls``."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": _max_tokens(max_tokens),
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return await _get_client().chat.completions.create(**kwargs)


async def one_shot(
    *, system: str, user: str, max_tokens: int | None = None, model: str | None = None
) -> str:
    resp = await _get_client().chat.completions.create(
        model=model or chat_model_for(),
        max_tokens=_max_tokens(max_tokens),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


async def extract_json(
    *, system: str, user: str, max_tokens: int = 2000, model: str | None = None
) -> Any:
    """``one_shot`` + parse a JSON object from the reply. Raises ``ValueError``."""
    text = (
        await one_shot(system=system, user=user, max_tokens=max_tokens, model=model)
    ).strip()
    try:
        return json.loads(text)
    except ValueError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("no JSON object in model response")
        return json.loads(match.group(0))
