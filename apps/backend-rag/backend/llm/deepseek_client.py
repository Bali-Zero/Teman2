"""DeepSeek API client (async, OpenAI-compatible).

Used by backend paths that previously ran Claude via Max OAuth but
suffered from the upstream `claude` CLI non-TTY hang inside the Fly
container (see `memory/feedback_claude_cli_linux_hang.md`). DeepSeek is
cheaper (~100x) than Claude Sonnet for structured JSON generation and
returns usage counters properly.

Endpoint: `https://api.deepseek.com/v1/chat/completions` (OpenAI-style).
Models:
- ``deepseek-chat``: DeepSeek V3.2, general-purpose, cheapest.
- ``deepseek-reasoner``: DeepSeek R1 reasoning (not used here).

Auth: ``DEEPSEEK_API_KEY`` env var (already deployed on `nuzantara-rag`).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Final

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL: Final[str] = "deepseek-chat"
DEFAULT_BASE_URL: Final[str] = "https://api.deepseek.com/v1"
DEFAULT_TIMEOUT_S: Final[float] = 60.0


class DeepSeekError(RuntimeError):
    """Raised on any DeepSeek call failure (HTTP error, bad JSON, empty choice)."""


class DeepSeekAuthError(DeepSeekError):
    """Raised when the API key is missing or rejected."""


@dataclass(frozen=True)
class DeepSeekResponse:
    """Minimal envelope for a one-shot chat completion."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    finish_reason: str


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Get or create the persistent async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT_S, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )
    return _client


async def close_deepseek_client() -> None:
    """Close the persistent HTTP client. Called from FastAPI lifespan."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
    _client = None
    logger.info("DeepSeek HTTP client closed.")


async def complete_async(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    response_format: dict[str, str] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> DeepSeekResponse:
    """Run a one-shot chat completion against DeepSeek.

    Args:
        prompt: User prompt. Kept as a single string for call-site parity
            with the old ``claude -p`` subprocess wrapper.
        model: Model slug (``deepseek-chat`` by default).
        system: Optional system prompt. Callers that embed the system
            instructions inline in ``prompt`` can leave this ``None``.
        max_tokens: Upper bound on completion tokens.
        temperature: Sampling temperature. 0.3 is a reasonable default
            for structured JSON generation.
        response_format: Pass ``{"type": "json_object"}`` to enable
            DeepSeek's JSON mode. The prompt must mention "JSON" for this
            to be accepted by the API.
        timeout_s: Per-request wall-clock timeout.

    Returns:
        :class:`DeepSeekResponse` with the completion text + usage
        counters.

    Raises:
        :class:`DeepSeekAuthError`: if ``DEEPSEEK_API_KEY`` is missing or
            the API returns 401.
        :class:`DeepSeekError`: on any other HTTP error, empty response,
            or malformed JSON.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise DeepSeekAuthError(
            "DEEPSEEK_API_KEY env var is not set. Cannot call DeepSeek API.",
        )

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}/chat/completions"

    try:
        client = _get_client()
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
        )
    except httpx.TimeoutException as exc:
        raise DeepSeekError(f"DeepSeek request timed out after {timeout_s}s") from exc
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek HTTP transport error: {exc}") from exc

    if resp.status_code == 401:
        raise DeepSeekAuthError(f"DeepSeek rejected API key (401): {resp.text[:200]}")
    if resp.status_code >= 400:
        raise DeepSeekError(
            f"DeepSeek HTTP {resp.status_code}: {resp.text[:500]}",
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise DeepSeekError(f"DeepSeek returned non-JSON body: {resp.text[:200]}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise DeepSeekError(f"DeepSeek returned empty choices: {data}")

    choice0 = choices[0]
    message = choice0.get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        raise DeepSeekError(f"DeepSeek returned empty content: {data}")

    usage = data.get("usage") or {}
    return DeepSeekResponse(
        text=text,
        model=str(data.get("model") or model),
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        cache_hit_tokens=int(usage.get("prompt_cache_hit_tokens") or 0),
        finish_reason=str(choice0.get("finish_reason") or "stop"),
    )
