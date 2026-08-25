"""TP1Client — async HTTP client for the Alibaba Model Studio "Token Plan"
door (`MODEL_ROSTER.md` "Alibaba Token Plan (TP1)"; directive#1§1 names it
the team bot's primary/fallback brain: `qwen3.7-plus` -> `qwen3.6-flash` ->
`glm-5.2`, all three live on this ONE door/key).

**Pinned, not aliased** (Kimi refuter warning, directive#1§4: "pin an
explicit VERSION, never an alias — deprecation churn is quarterly, every
re-pin needs a smoke test"). `TP1Model`'s three values were read verbatim
from a LIVE `GET /models` call against this exact door on 2026-08-25 (see
`errors.py`'s evidence ledger and `scripts/duebot/tp1_pin_smoketest.py`,
which re-runs that call and fails if any pinned slug goes missing).

**Persistent client, never per-call** (CLAUDE.md Golden Rule #10): one
`httpx.AsyncClient` lives for the lifetime of a `TP1Client` instance;
callers `aclose()` it (or use it as an async context manager) once, not per
request.

**Secrets discipline** (team-lead brief: "Read secret NAMES, never values...
never log a token, a body, or a signature"): the API key is held only inside
the `httpx.AsyncClient`'s default headers, set once at construction, never
re-read or logged after that. No method on this class ever logs a request
or response BODY — chat content can carry client PII discussed by team
members (directive#1§1's PII deroga is scoped to the model seeing it, not to
logs: "Law 2 frontiera-output resta — mai PII in log/memorie persistite in
chiaro"). Only `UsageSample` (token counts) and `BrainErrorVerdict.detail`
(TP1's own generic account/request diagnostics, emitted before any chat
content exists) are safe-to-log by construction.

**`enable_thinking`** (directive#1§1: "`max_tokens` copre thinking+risposta,
thinking≈0 per i turni tool"): live-verified 2026-08-25 that TP1's OpenAI-
compatible endpoint honors a TOP-LEVEL `enable_thinking: false` request
field (not nested under `extra_body` — that shape was tried and did NOT
suppress reasoning tokens) and returns a `reasoning_content`-free response
at a fraction of the token cost. `chat_completion()` defaults to `False`.

Author: Claude (lane B4-tp1 — team-bot TP1 brain adapter).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter, time
from typing import Any

import httpx

from .depletion_probe import UsageSample
from .errors import (
    BrainErrorVerdict,
    classify_response,
    verdict_for_network_error,
    verdict_for_output_invalid,
    verdict_for_timeout,
)
from .settings import TP1_BASE_URL, load_tp1_api_key

__all__ = ["BrainCallError", "BrainCallResult", "TP1Client", "TP1Model"]


class TP1Model(StrEnum):
    """Pinned, live-verified exact slugs (2026-08-25 `GET /models`) — see
    module docstring. `qwen3.7-max`/`qwen3.8-max`/`deepseek-v4-*` are also
    live on this door (MODEL_ROSTER.md) but are NOT part of directive#1§1's
    fallback chain and are deliberately absent here."""

    QWEN_3_7_PLUS = "qwen3.7-plus"
    QWEN_3_6_FLASH = "qwen3.6-flash"
    GLM_5_2 = "glm-5.2"


class BrainCallError(RuntimeError):
    """Raised by every `TP1Client` failure path. `verdict` is always a
    `BrainErrorVerdict` — never a bare exception a caller has to
    re-classify itself."""

    def __init__(self, verdict: BrainErrorVerdict) -> None:
        self.verdict = verdict
        super().__init__(f"{verdict.error_class}: {verdict.detail}")


@dataclass(frozen=True, slots=True)
class BrainCallResult:
    """The raw OpenAI-compatible `message` dict, verbatim — this is the
    "shared serving endpoint contract" MANDATE.md's Lanes section names
    ("B3/B4 share only the ToolDecision schema and the serving endpoint
    contract"): `team_bot.loop.tool_decision.ToolDecision.from_raw_message`
    consumes `.message` directly, unmodified, regardless of which brain
    tier produced it."""

    model: str
    message: dict[str, Any]
    usage: UsageSample
    latency_s: float
    finish_reason: str | None


def _safe_exc_str(exc: Exception) -> str:
    """httpx transport exceptions may embed the request URL (never a
    secret — auth here is a header, not a query string) but never a
    header value. Defensive length cap regardless."""
    text = f"{type(exc).__name__}: {exc}"
    return text if len(text) <= 300 else text[:300] + "…"


class TP1Client:
    """One persistent async client per process. Construct via `from_settings()`
    in production (reads the key once, never re-reads it); pass an explicit
    `api_key` + `transport=httpx.MockTransport(...)` in tests."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = TP1_BASE_URL,
        timeout_s: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_s),
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    @classmethod
    def from_settings(cls, *, timeout_s: float = 30.0) -> TP1Client:
        return cls(load_tp1_api_key(), timeout_s=timeout_s)

    async def __aenter__(self) -> TP1Client:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat_completion(
        self,
        *,
        model: TP1Model,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        max_tokens: int,
        enable_thinking: bool = False,
    ) -> BrainCallResult:
        """Raises `BrainCallError` on any non-2xx response, transport
        failure, timeout, or unparseable 2xx body — never returns a partial
        or best-effort result silently."""
        body: dict[str, Any] = {
            "model": model.value,
            "messages": messages,
            "max_tokens": max_tokens,
            "enable_thinking": enable_thinking,
        }
        if tools is not None:
            body["tools"] = tools
            # F4's single-mutation-per-turn discipline: harmless to request
            # even though B4 measured neither llama.cpp nor Ollama honors
            # it (memory: parallel-tool-calls-false-is-not-honored-locally)
            # — TP1 is an UNMEASURED third stack, and `ToolDecision` already
            # enforces single-tool-call by construction regardless, so this
            # is defense-in-depth, never the sole guarantee.
            body["parallel_tool_calls"] = False
        if tool_choice is not None:
            body["tool_choice"] = tool_choice

        t0 = perf_counter()
        try:
            response = await self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise BrainCallError(
                verdict_for_timeout(f"{type(e).__name__} after {perf_counter() - t0:.1f}s")
            ) from e
        except httpx.TransportError as e:
            raise BrainCallError(verdict_for_network_error(_safe_exc_str(e))) from e
        latency = perf_counter() - t0

        if response.status_code != 200:
            raise BrainCallError(classify_response(response.status_code, response.text))

        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError("message is not an object")
            usage_raw = data.get("usage") or {}
            usage = UsageSample(
                ts=time(),
                model=model.value,
                prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
                completion_tokens=int(usage_raw.get("completion_tokens", 0)),
                total_tokens=int(usage_raw.get("total_tokens", 0)),
            )
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise BrainCallError(
                verdict_for_output_invalid(f"{type(e).__name__} parsing 200 body shape")
            ) from e

        return BrainCallResult(
            model=model.value,
            message=message,
            usage=usage,
            latency_s=latency,
            finish_reason=choice.get("finish_reason"),
        )

    async def list_models(self) -> list[str]:
        """Live pin-verification primitive — used by
        `scripts/duebot/tp1_pin_smoketest.py`, never by the hot chat path
        (directive#1§1: "slug esatti via GET /models — mai dedurre dalla
        tabella", but re-listing on every chat call would be a wasted
        round-trip; the smoke test is the re-pin discipline instead)."""
        response = await self._client.get("/models")
        if response.status_code != 200:
            raise BrainCallError(classify_response(response.status_code, response.text))
        data = response.json()
        ids = [
            m["id"]
            for m in data.get("data", [])
            if isinstance(m, dict) and isinstance(m.get("id"), str)
        ]
        return sorted(ids)
