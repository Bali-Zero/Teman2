"""DeepSeek model client (async, OpenAI-compatible) — via the TP1 gateway.

Used by backend paths that previously ran Claude via Max OAuth but
suffered from the upstream `claude` CLI non-TTY hang inside the Fly
container (see `memory/feedback_claude_cli_linux_hang.md`). DeepSeek is
cheaper than Claude Sonnet for structured JSON generation and
returns usage counters properly.

RE-POINTED 2026-08-29 (misroute fix, not a replacement): this module used
to call DeepSeek's own metered endpoint (``api.deepseek.com`` +
``DEEPSEEK_API_KEY``) directly. That direct-billing door was RETIRED
2026-07-19 (pre-authorization revoked, balance dead — HTTP-402; CLAUDE.md
§"Cost constraint"). The SAME model family stayed live the whole time
through a second, distinct door: the Alibaba **TP1** (Token Plan) OpenAI-
compatible gateway, which `FLEET_TOPOLOGY.json` records as a 2026-08-10
"DeepSeek re-admission" — ``deepseek-v4-flash-0731`` measured ARMED (806
calls / 131.2M tokens, 2026-08-08→14 window); ``deepseek-v4-pro`` is
listed PROBATION with zero measured calls in that same window — do not
conflate the two tiers' maturity. Endpoint + slugs below now target that
door. See ``scripts/tp1_call.py`` / ``scripts/arsenal_probe.py`` for the
sibling non-backend TP1 caller this mirrors.

Models (DeepSeek V4 release 2026-04-24, ref api-docs.deepseek.com/news/news260424):
- ``deepseek-v4-pro``: V4 Pro flagship (1.6T params, 49B activated, 1M ctx).
- ``deepseek-v4-flash-0731``: V4 Flash (284B params, 13B activated, 1M ctx)
  — this is TP1's exact live slug; it does NOT resolve to the bare
  ``deepseek-v4-flash`` string DeepSeek's own docs use, and the two must
  not be assumed interchangeable on this door (confirmed live 2026-08-23,
  ``scripts/arsenal_probe.py::TP1_SEAT_MODELS``).
- Legacy aliases ``deepseek-chat`` (→ V4-Flash non-think) and
  ``deepseek-reasoner`` (→ V4-Flash thinking) were DeepSeek's own aliases,
  deprecated 2026-07-24 on the now-retired direct door — unverified
  whether TP1 recognizes them at all; do not rely on them here.

V4 supports reasoning modes via the ``reasoning_effort`` parameter. TP1's
gateway accepts exactly ``none|minimal|low|medium|high|xhigh`` — NOT
``max`` (HTTP 400, confirmed live 2026-08-27 per
``scripts/tp1_call.py::EFFORT_TO_REASONING_EFFORT``); ``complete_async``
below clamps ``"max"`` to ``"xhigh"`` for exactly that reason, mirroring
that script's mapping instead of drifting a second copy of it.

Auth: ``BAILIAN_TOKEN_PLAN_API_KEY`` env var — the TP1 credential name,
NOT ``DEEPSEEK_API_KEY`` (that name now names only the retired direct
door and must never be topped up). On Fly this must exist as a real Fly
secret on `nuzantara-rag` (``fly secrets set BAILIAN_TOKEN_PLAN_API_KEY=...
-a nuzantara-rag``) — provisioning it is an operator[secret] action, not
something this module or its author can do; see PENDING-ARMS.md.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Final, Literal

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL: Final[str] = "deepseek-v4-flash-0731"
DEFAULT_BASE_URL: Final[str] = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_TIMEOUT_S: Final[float] = 60.0

ReasoningEffort = Literal["low", "high", "max"]

# TP1 rejects "max" literally (HTTP 400) — it wants "xhigh" for the same
# intent. Kept here (not just clamped inline) so the mapping has one place
# to read, matching scripts/tp1_call.py::EFFORT_TO_REASONING_EFFORT.
_REASONING_EFFORT_TP1_MAP: Final[dict[str, str]] = {
    "low": "low",
    "high": "high",
    "max": "xhigh",
}


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
    endpoint: str | None = None,
    request_id: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> DeepSeekResponse:
    """Run a one-shot chat completion against DeepSeek.

    Every call is recorded through
    :func:`backend.services.observability.record_llm_call` (triple-write
    Prometheus + Postgres + JSONL). Failures are recorded too, with the
    exception class as ``error_class``.

    Args:
        prompt: User prompt. Kept as a single string for call-site parity
            with the old ``claude -p`` subprocess wrapper.
        model: Model slug. Defaults to ``deepseek-v4-flash-0731`` (TP1's
            confirmed-live slug — NOT the bare ``deepseek-v4-flash``
            string). Use ``deepseek-v4-pro`` for the flagship tier (TP1
            PROBATION, less production mileage than flash-0731).
        system: Optional system prompt.
        max_tokens: Upper bound on completion tokens.
        temperature: Sampling temperature. 0.3 is a reasonable default
            for structured JSON generation.
        response_format: Pass ``{"type": "json_object"}`` to enable
            DeepSeek's JSON mode. The prompt must mention "JSON" for this
            to be accepted by the API.
        timeout_s: Per-request wall-clock timeout.
        endpoint: Caller identifier for cost attribution
            (e.g. ``"article_composer"``). Strongly recommended — without
            it all DeepSeek calls show up as ``endpoint=unknown``.
        request_id: Correlation id propagated from the HTTP request, if
            available.
        reasoning_effort: DeepSeek V4 reasoning mode. One of
            ``"low"`` (Non-think, fast), ``"high"`` (Think High,
            balanced) or ``"max"`` (Think Max, deep chain-of-thought).
            ``None`` lets the API pick the default. Recommended values:
            ``"max"`` for Consiglio gate-6 deliberation, ``"low"`` for
            structured JSON generation, ``"high"`` for general reasoning.

    Returns:
        :class:`DeepSeekResponse` with the completion text + usage
        counters.

    Raises:
        :class:`DeepSeekAuthError`: if ``BAILIAN_TOKEN_PLAN_API_KEY`` is
            missing or TP1 returns 401.
        :class:`DeepSeekError`: on any other HTTP error, empty response,
            or malformed JSON.
    """
    t0 = time.monotonic()
    input_tokens = 0
    output_tokens = 0
    cache_hit_tokens = 0
    cost_usd = 0.0
    model_returned = model
    success = False
    error_class: str | None = None

    try:
        api_key = os.getenv("BAILIAN_TOKEN_PLAN_API_KEY", "").strip()
        if not api_key:
            raise DeepSeekAuthError(
                "BAILIAN_TOKEN_PLAN_API_KEY env var is not set. Cannot call "
                "DeepSeek via the TP1 gateway (the direct DEEPSEEK_API_KEY "
                "door is retired — see this module's docstring).",
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
        if reasoning_effort is not None:
            payload["reasoning_effort"] = _REASONING_EFFORT_TP1_MAP.get(
                reasoning_effort, reasoning_effort,
            )

        # DEEPSEEK_BASE_URL name kept for escape-valve continuity (a caller
        # can still point this client elsewhere); the DEFAULT is now TP1,
        # not the retired direct door.
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
            raise DeepSeekAuthError(
                f"TP1 gateway rejected BAILIAN_TOKEN_PLAN_API_KEY (401): {resp.text[:200]}",
            )
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
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
        model_returned = str(data.get("model") or model)

        # Cost: DeepSeek V4 pricing (USD per 1M tokens, 2026-04-24 release).
        # V4 Pro flagship: cache hit $0.435, cache miss $0.435 (input),
        # output $0.87. (75% promo until 2026-05-31 lowers cache-hit input
        # to $0.003625; we use list price here to be conservative.)
        # V4 Flash: cache hit $0.0028, cache miss $0.14, output $0.28.
        # Legacy ``deepseek-chat``/``deepseek-reasoner`` aliases route to
        # V4-Flash on DeepSeek side and are billed at flash rates.
        model_lc = (model_returned or model).lower()
        is_v4_pro = "v4-pro" in model_lc or model_lc.endswith("-pro")
        if is_v4_pro:
            input_cm_rate = 0.435  # V4-Pro cache-miss input
            input_ch_rate = 0.435  # V4-Pro cache-hit input (promo aside)
            output_rate = 0.87  # V4-Pro output
        else:
            input_cm_rate = 0.14  # V4-Flash / legacy aliases
            input_ch_rate = 0.0028
            output_rate = 0.28
        cache_miss_tokens = max(0, input_tokens - cache_hit_tokens)
        cost_usd = (
            cache_miss_tokens * input_cm_rate / 1_000_000
            + cache_hit_tokens * input_ch_rate / 1_000_000
            + output_tokens * output_rate / 1_000_000
        )

        success = True
        return DeepSeekResponse(
            text=text,
            model=model_returned,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit_tokens=cache_hit_tokens,
            finish_reason=str(choice0.get("finish_reason") or "stop"),
        )

    except BaseException as exc:
        error_class = type(exc).__name__
        raise
    finally:
        # Record the call no matter what. Never let tracking exceptions
        # propagate to the caller.
        try:
            from backend.services.observability import record_llm_call

            await record_llm_call(
                provider="deepseek",
                model=model_returned,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_hit_tokens=cache_hit_tokens,
                cost_usd=cost_usd,
                success=success,
                latency_ms=int((time.monotonic() - t0) * 1000),
                endpoint=endpoint,
                request_id=request_id,
                error_class=error_class,
            )
        except Exception as exc:
            logger.warning("llm_cost recorder failed for deepseek: %s", exc)
