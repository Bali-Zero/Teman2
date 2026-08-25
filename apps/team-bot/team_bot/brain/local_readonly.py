"""LocalReadOnlyClient — the third, always-available degradation lane
(directive#1§1: "modello locale Qwen sul Mini in sola-lettura ... quando il
cloud è giù risponde solo ai tool R0 e lo dice").

Two structural guarantees, both enforced by construction rather than by
trusting a caller to pass the right arguments (same philosophy
`reply_composer.py` already uses for gc-015 — "a construction that cannot
lie, rather than a detector that tries to catch every way it might"):

1. **R0-only, always.** `chat_completion()` takes no `tools` parameter at
   all — it is hard-wired to `r0_tools_as_openai_schema()`, the read-only
   subset of `team_bot.registry.TOOL_REGISTRY` (F5). There is no code path
   in this module that can hand the model an R1/R2/R3 mutation tool, so a
   caller cannot accidentally (or a compromised caller cannot deliberately)
   arm a write while degraded.
2. **It says so.** Every `chat_completion()` call returns `degraded=True`
   with a fixed `degraded_reason` — this is DATA, not prose baked into the
   model's own reply text (mutating `content` here would risk corrupting a
   `tool_calls`-carrying message and duplicates `reply_composer.py`'s own
   job of rendering a fixed, server-authored disclosure sentence). Wiring
   `degraded`/`degraded_reason` into an actual outbound WhatsApp reply is
   `reply_composer.py`'s integration point, not built here — this module
   only guarantees the fact is never lost between the brain and the caller.

**Endpoint is intentionally unpinned.** B4's OTHER, separate local-serving
track (`scripts/duebot/serving_roundtrip_gate.py`,
`scripts/duebot/golden_multilingual_gate.py`) has not yet landed a final
production model tag+digest for the Mini's llama-server/Ollama stack — F8's
golden multilingual eval is what selects it, and inventing a placeholder
digest here would silently disconnect from that measured process. Both
`base_url` and `model` are REQUIRED constructor arguments (no baked-in
default) so a caller that has not configured them fails loudly at
construction, not with a cryptic connection-refused deep in a request.

Author: Claude (lane B4-tp1 — team-bot TP1 brain adapter).
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, time
from typing import Any

import httpx

from team_bot.registry import TOOL_REGISTRY, RiskTier

from .depletion_probe import UsageSample
from .errors import (
    classify_response,
    verdict_for_network_error,
    verdict_for_output_invalid,
    verdict_for_timeout,
)
from .tp1_client import BrainCallError, BrainCallResult

__all__ = ["DEGRADED_REASON", "LocalReadOnlyClient", "r0_tools_as_openai_schema"]

DEGRADED_REASON = (
    "cloud brain unavailable — answered from the local read-only model; "
    "read-only tools only, no writes possible in this mode"
)


def r0_tools_as_openai_schema() -> list[dict[str, Any]]:
    """The R0 (read, never confirmed) subset of the frozen ten-tool
    registry, as OpenAI-compatible `tools` entries. Recomputed each call
    (the registry is a frozen module-level tuple — this is cheap) rather
    than cached, so a future registry edit can never leave a stale R1+
    tool baked into an old cached list."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters_schema,
            },
        }
        for spec in TOOL_REGISTRY
        if spec.risk_tier == RiskTier.R0
    ]


@dataclass(frozen=True, slots=True)
class LocalReadOnlyResult:
    call: BrainCallResult
    degraded: bool = True
    degraded_reason: str = DEGRADED_REASON


class LocalReadOnlyClient:
    """Talks to a local OpenAI-compatible `/v1/chat/completions` endpoint
    (llama.cpp `llama-server` or Ollama — F8's reference stacks). Same
    error-classification and persistent-client discipline as `TP1Client`;
    kept as a separate class (not a `TP1Client` subclass) because it is a
    DIFFERENT vendor door with a different failure meaning — a local 5xx/
    connection-refused means "the Mini's serving process is down", not
    "the cloud plan is exhausted", and callers (the router's logging/
    alerting) must be able to tell the two apart from the exception type
    alone if needed.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_s: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url is required (no baked-in default — see module docstring)")
        if not model.strip():
            raise ValueError("model is required (no baked-in default — see module docstring)")
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_s),
            transport=transport,
            headers={"Content-Type": "application/json"},
        )

    async def __aenter__(self) -> LocalReadOnlyClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> LocalReadOnlyResult:
        """No `tools` parameter by design — always R0-only (see module
        docstring). Raises `BrainCallError` on any failure, exactly like
        `TP1Client.chat_completion`, so `BrainRouter` can handle both
        uniformly."""
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "tools": r0_tools_as_openai_schema(),
            "parallel_tool_calls": False,
        }

        t0 = perf_counter()
        try:
            response = await self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise BrainCallError(
                verdict_for_timeout(f"{type(e).__name__} after {perf_counter() - t0:.1f}s")
            ) from e
        except httpx.TransportError as e:
            raise BrainCallError(verdict_for_network_error(f"{type(e).__name__}: {e}")) from e
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
                model=self._model,
                prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
                completion_tokens=int(usage_raw.get("completion_tokens", 0)),
                total_tokens=int(usage_raw.get("total_tokens", 0)),
            )
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise BrainCallError(
                verdict_for_output_invalid(f"{type(e).__name__} parsing 200 body shape")
            ) from e

        call = BrainCallResult(
            model=self._model,
            message=message,
            usage=usage,
            latency_s=latency,
            finish_reason=choice.get("finish_reason"),
        )
        return LocalReadOnlyResult(call=call)
