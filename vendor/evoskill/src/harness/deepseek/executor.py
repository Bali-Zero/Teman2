"""DeepSeek V4 Pro executor — Phase 1 real implementation.

Replaces the Phase 0 stub (raised NotImplementedError) with a real
adapter that POSTs to the DeepSeek V4 Pro Chat Completions API and
parses the response into AgentTrace-compatible fields.

Phase 1 owner: address known-limit L7 (DeepSeek harness Phase 0 stub)
from `agent-library/proposals/.known-limitations-v1.md`.

Contract enforced (matches goose/opencode/openhands return shape):
    execute_query(options, query) -> list[Any]
        Returns a single-item list wrapping the raw JSON response dict.
        Wrapped in a list for consistency with other executors.
    parse_response(messages, response_model, get_options) -> dict[str, Any]
        Returns a dict of AgentTrace field values (uuid, session_id,
        model, duration_ms, total_cost_usd, num_turns, usage, result,
        is_error, output, parse_error, raw_structured_output, messages).

Retry policy: identical to harness/agent.py:_run_with_retry — exponential
backoff 30s → 60s → 120s on transient errors (HTTP 5xx, network
timeout, JSON decode failure on a retryable response).

Cost reporting: DeepSeek API returns `usage` with prompt_tokens,
completion_tokens, prompt_cache_hit_tokens, prompt_cache_miss_tokens.
Total cost computed via `_estimate_cost_usd()` using public pricing
(input $0.27/M cache-miss, $0.07/M cache-hit, output $1.10/M as of
2026-05 for deepseek-v4-pro / deepseek-chat tier). Updated periodically
per spec §"LLM routing".

Phase: 1 (real impl, supersedes Phase 0 stub at commit a1f383ced).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid as uuid_lib
from typing import Any, Callable

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_CHAT_ENDPOINT = f"{DEEPSEEK_API_BASE}/chat/completions"

# Pricing snapshot (USD per 1M tokens) — verified from api-docs.deepseek.com
# 2026-05. Update this dict + the test fixture when DeepSeek revises tariffs.
# Source: https://api-docs.deepseek.com/quick_start/pricing
_PRICING_USD_PER_M_TOKENS: dict[str, dict[str, float]] = {
    "deepseek-v4-pro": {
        "input_cache_hit": 0.07,
        "input_cache_miss": 0.27,
        "output": 1.10,
    },
    "deepseek-chat": {  # alias maintained for upstream model_aliases compat
        "input_cache_hit": 0.07,
        "input_cache_miss": 0.27,
        "output": 1.10,
    },
    "deepseek-reasoner": {  # DEPRECATED 2026-07-24; kept for old configs
        "input_cache_hit": 0.14,
        "input_cache_miss": 0.55,
        "output": 2.19,
    },
}

# Connection timeouts: connect=10s, read=300s (DeepSeek reasoning can
# take 60-180s on high-effort prompts). Total request budget guarded by
# the retry loop, not by httpx.
_HTTPX_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)

# Retry policy — matches harness/agent.py:_run_with_retry
_RETRY_BACKOFFS_S: tuple[int, int, int] = (30, 60, 120)


class DeepSeekAPIError(RuntimeError):
    """Raised on non-retryable DeepSeek API errors (auth, 4xx, schema mismatch)."""


class DeepSeekTransientError(RuntimeError):
    """Raised on retryable errors (5xx, timeout, network). Triggers backoff."""


def _estimate_cost_usd(model: str, usage: dict[str, int]) -> float:
    """Compute total_cost_usd from the DeepSeek `usage` block.

    DeepSeek returns:
        prompt_tokens (total input)
        prompt_cache_hit_tokens (subset of prompt_tokens cached)
        prompt_cache_miss_tokens (subset of prompt_tokens NOT cached)
        completion_tokens (output)

    Cost = (cache_hit * price_hit + cache_miss * price_miss + completion * price_out) / 1M

    If model not in _PRICING_USD_PER_M_TOKENS, returns 0.0 with a warning
    (fail-soft: cost reporting is informational, not a gate by itself —
    BUDGET_USD enforcement happens in the wrapper script).
    """
    pricing = _PRICING_USD_PER_M_TOKENS.get(model)
    if pricing is None:
        # Try fuzzy match on model prefix (e.g. "deepseek-v4-pro-2024" → "deepseek-v4-pro")
        for key, p in _PRICING_USD_PER_M_TOKENS.items():
            if model.startswith(key):
                pricing = p
                break
    if pricing is None:
        logger.warning(
            "deepseek executor: unknown model %r — total_cost_usd=0.0",
            model,
        )
        return 0.0

    cache_hit = int(usage.get("prompt_cache_hit_tokens", 0) or 0)
    cache_miss = int(usage.get("prompt_cache_miss_tokens", 0) or 0)
    # If only prompt_tokens is reported (older API response), treat it all
    # as cache_miss (worst-case cost — defensive default).
    if cache_hit == 0 and cache_miss == 0:
        cache_miss = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)

    cost = (
        cache_hit * pricing["input_cache_hit"]
        + cache_miss * pricing["input_cache_miss"]
        + completion * pricing["output"]
    ) / 1_000_000.0
    return round(cost, 6)


def _build_messages(system: str, query: str) -> list[dict[str, str]]:
    """Build the OpenAI-compatible messages array DeepSeek expects."""
    messages = []
    if system and system.strip():
        messages.append({"role": "system", "content": system.strip()})
    messages.append({"role": "user", "content": query})
    return messages


def _build_response_format(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate a JSON schema dict into DeepSeek `response_format`.

    DeepSeek supports OpenAI-style `{"type": "json_object"}` for free-form
    JSON, and `{"type": "json_schema", "json_schema": {...}}` for strict
    schema validation. We use `json_object` when schema is non-empty
    (we'll validate against the Pydantic model in parse_response) and
    leave it unset for free-text queries.
    """
    if not schema or not isinstance(schema, dict) or not schema:
        return None
    return {"type": "json_object"}


def _is_transient_status(status_code: int) -> bool:
    """5xx + 429 (rate limit) + 408 (timeout) are retryable."""
    return status_code in (408, 429) or 500 <= status_code <= 599


async def _post_once(
    payload: dict[str, Any], api_key: str
) -> dict[str, Any]:
    """Single POST attempt — raises DeepSeekTransientError on retryable
    failures, DeepSeekAPIError on non-retryable ones."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
            response = await client.post(
                DEEPSEEK_CHAT_ENDPOINT, json=payload, headers=headers
            )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
        raise DeepSeekTransientError(
            f"network error talking to DeepSeek API: {type(e).__name__}: {e}"
        ) from e
    except httpx.HTTPError as e:
        # Generic httpx error — treat as transient (defense in depth)
        raise DeepSeekTransientError(f"httpx error: {type(e).__name__}: {e}") from e

    if response.status_code == 200:
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise DeepSeekTransientError(
                f"DeepSeek returned 200 but body is not valid JSON: {e}"
            ) from e

    body_preview = response.text[:500] if response.text else "<empty>"
    if _is_transient_status(response.status_code):
        raise DeepSeekTransientError(
            f"DeepSeek API {response.status_code} (transient): {body_preview}"
        )
    raise DeepSeekAPIError(
        f"DeepSeek API {response.status_code} (non-retryable): {body_preview}"
    )


async def execute_query(options: dict[str, Any], query: str) -> list[Any]:
    """Execute a query against DeepSeek V4 Pro Chat Completions API.

    Args:
        options: Dict built by `build_deepseek_options()` with keys:
            - sdk: "deepseek" (marker)
            - model: e.g. "deepseek-v4-pro"
            - system: system prompt text
            - schema: optional JSON schema for structured output
            - reasoning_effort: "low" | "high" | "max" (forwarded as-is
              to the API; if upstream rejects it, falls through as
              vendor extension parameter)
            - max_tokens (optional): defaults to 8000
            - temperature (optional): defaults to 0.2
            - tools (metadata only, not sent)
            - project_root (metadata only)
        query: The user query string.

    Returns:
        Single-item list wrapping the raw DeepSeek JSON response dict.
        Wrapped for AgentTrace contract symmetry with other executors.

    Raises:
        DeepSeekAPIError: On auth failure, 4xx errors, or fatal schema
            issues. NOT retried.
        DeepSeekTransientError: On 5xx / 429 / network errors AFTER all
            retries are exhausted.
        RuntimeError: If DEEPSEEK_API_KEY env var is missing.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY env var not set. The DeepSeek executor "
            "requires a valid API key. CLAUDE.md hard rule: DeepSeek "
            "API is the ONE sanctioned paid LLM endpoint for Bali Zero "
            "(per spec §'LLM routing')."
        )

    model = options.get("model", "deepseek-v4-pro")
    payload: dict[str, Any] = {
        "model": model,
        "messages": _build_messages(options.get("system", ""), query),
        "max_tokens": int(options.get("max_tokens", 8000)),
        "temperature": float(options.get("temperature", 0.2)),
        "stream": False,
    }
    response_format = _build_response_format(options.get("schema"))
    if response_format is not None:
        payload["response_format"] = response_format

    # `reasoning_effort` is a DeepSeek V4 Pro extension (low/high/max).
    # We forward it conditionally; if the API doesn't recognise it on a
    # given model, the server should silently ignore (verified empirically
    # for deepseek-chat / deepseek-v4-pro tier).
    if "reasoning_effort" in options:
        payload["reasoning_effort"] = options["reasoning_effort"]

    last_error: Exception | None = None
    for attempt, backoff in enumerate([0, *_RETRY_BACKOFFS_S]):
        if backoff > 0:
            logger.warning(
                "deepseek executor: retrying after %ds (attempt %d/%d)",
                backoff,
                attempt + 1,
                len(_RETRY_BACKOFFS_S) + 1,
            )
            await asyncio.sleep(backoff)
        try:
            response_json = await _post_once(payload, api_key)
            return [response_json]
        except DeepSeekTransientError as e:
            last_error = e
            logger.warning(
                "deepseek executor: transient error attempt %d: %s", attempt + 1, e
            )
            continue
        except DeepSeekAPIError:
            # Non-retryable — propagate immediately
            raise

    # All retries exhausted
    raise DeepSeekTransientError(
        f"DeepSeek API failed after {len(_RETRY_BACKOFFS_S) + 1} attempts: {last_error}"
    )


def parse_response(
    messages: list[Any],
    response_model: type,
    get_options: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Parse the DeepSeek JSON response into AgentTrace field values.

    Args:
        messages: Single-item list from execute_query() wrapping the raw
            DeepSeek response dict.
        response_model: Pydantic model class to validate the structured
            output against.
        get_options: Optional callable returning the options dict (for
            model + tools metadata). Same pattern as goose/openhands.

    Returns:
        Dict ready to splat into AgentTrace(**fields). All 13 AgentTrace
        fields are set:
            uuid, session_id, model, tools (from options),
            duration_ms (0 — DeepSeek does not report per-call duration),
            total_cost_usd, num_turns=1, usage (DeepSeek usage dict),
            result (assistant content string), is_error (bool),
            output (Pydantic model instance or None on parse failure),
            parse_error (str or None), raw_structured_output (dict or None),
            messages (the input list, for debugging).
    """
    if not messages:
        return _empty_trace_fields(
            get_options, parse_error="DeepSeek executor received empty messages list"
        )
    response = messages[0]
    if not isinstance(response, dict):
        return _empty_trace_fields(
            get_options,
            parse_error=f"DeepSeek response is not a dict: {type(response).__name__}",
        )

    options = (get_options() if callable(get_options) else None) or {}
    model_name = (
        options.get("model")
        if isinstance(options, dict)
        else None
    ) or response.get("model", "unknown")
    tools = (
        options.get("tools", []) if isinstance(options, dict) else []
    )

    # Extract assistant content
    output: Any = None
    parse_error: str | None = None
    raw_structured_output: Any = None
    result_text = ""

    choices = response.get("choices") or []
    if not choices:
        parse_error = "DeepSeek response has no `choices` array"
    else:
        first_choice = choices[0]
        message = first_choice.get("message") or {}
        result_text = message.get("content") or ""
        finish_reason = first_choice.get("finish_reason", "")
        if finish_reason and finish_reason != "stop":
            # Note but do not fail — content_filter / length / tool_calls
            # are all valid finishes, just may indicate truncation.
            logger.info(
                "deepseek executor: finish_reason=%r (non-stop)", finish_reason
            )

    # Try to parse the content as JSON for structured output
    if result_text and parse_error is None:
        # First strip common wrappers — DeepSeek may emit ```json blocks
        stripped = result_text.strip()
        if stripped.startswith("```"):
            # Drop fence wrappers
            lines = stripped.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                stripped = "\n".join(lines[1:-1])

        try:
            raw_structured_output = json.loads(stripped)
        except json.JSONDecodeError:
            # Not JSON — could be free-text response. Not necessarily an error;
            # only fail if a Pydantic model was requested.
            if (
                response_model is not None
                and isinstance(response_model, type)
                and issubclass(response_model, BaseModel)
            ):
                parse_error = (
                    "DeepSeek response content is not valid JSON; cannot "
                    f"validate against {response_model.__name__}"
                )

    # Validate against the Pydantic model if structured output is present
    if raw_structured_output is not None and response_model is not None:
        try:
            if isinstance(response_model, type) and issubclass(response_model, BaseModel):
                output = response_model.model_validate(raw_structured_output)
        except (ValidationError, TypeError) as e:
            parse_error = f"{type(e).__name__}: {str(e)[:500]}"

    # Cost + usage
    usage_raw = response.get("usage") or {}
    total_cost_usd = _estimate_cost_usd(model_name, usage_raw)

    return dict(
        uuid=response.get("id") or str(uuid_lib.uuid4()),
        session_id=response.get("id") or "unknown",
        model=model_name,
        tools=tools if isinstance(tools, list) else [],
        duration_ms=0,  # DeepSeek does not report per-call duration
        total_cost_usd=total_cost_usd,
        num_turns=1,
        usage=dict(usage_raw),  # copy so the caller can mutate freely
        result=result_text,
        is_error=parse_error is not None,
        output=output,
        parse_error=parse_error,
        raw_structured_output=raw_structured_output,
        messages=messages,
    )


def _empty_trace_fields(
    get_options: Callable[[], Any] | None, *, parse_error: str
) -> dict[str, Any]:
    """Build AgentTrace fields for an empty/malformed response."""
    options = (get_options() if callable(get_options) else None) or {}
    model = options.get("model", "unknown") if isinstance(options, dict) else "unknown"
    tools = options.get("tools", []) if isinstance(options, dict) else []
    return dict(
        uuid="unknown",
        session_id="unknown",
        model=model,
        tools=tools if isinstance(tools, list) else [],
        duration_ms=0,
        total_cost_usd=0.0,
        num_turns=0,
        usage={},
        result="",
        is_error=True,
        output=None,
        parse_error=parse_error,
        raw_structured_output=None,
        messages=[],
    )
