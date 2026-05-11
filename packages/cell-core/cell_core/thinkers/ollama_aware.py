"""OllamaAwareThinker — graceful Ollama wrapper for any Thinker.

Implements ``cell_core.protocols.Thinker``. Tries the delegate (typically
an Ollama-backed thinker) with a hard timeout. On timeout / exception
falls back to a configured fallback Thinker (default: RuleBasedThinker).

Why a wrapper, not a flag inside the Ollama thinker:
* Keeps the Ollama logic free of fallback bookkeeping.
* Lets callers compose any "expensive" thinker with any "cheap" fallback
  without touching either.
* Symbiosis Law 4 — the fallback is structural, not opt-in.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from cell_core.protocols import Thinker
from cell_core.thinkers.rule_based import RuleBasedThinker
from cell_core.types import HomeostaticState, Proposal, SensorReading

logger = logging.getLogger("cell_core.thinkers.ollama_aware")

_DEFAULT_TIMEOUT_SECONDS = 2.0


class OllamaAwareThinker:
    """Compose an expensive primary thinker with a cheap fallback.

    Args:
        primary: The expensive thinker (e.g. Ollama-backed).
        fallback: The cheap deterministic thinker. Defaults to
            :class:`RuleBasedThinker`.
        timeout_seconds: Hard timeout for the primary call. Defaults
            to 2 s — keeps the THINK phase well under the 30-120 s
            Ollama latency upper bound and well below the 60 s pulse
            interval. Per project rule, Ollama is NEVER in the critical
            decisional path.
    """

    name = "ollama_aware"

    def __init__(
        self,
        primary: Thinker | None,
        fallback: Thinker | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or RuleBasedThinker()
        self._timeout = timeout_seconds

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal:
        # No primary configured → straight to fallback.
        if self._primary is None:
            return await self._fallback.think(readings, state, memory_context)

        try:
            return await asyncio.wait_for(
                self._primary.think(readings, state, memory_context),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "OllamaAwareThinker: primary timed out after %.1fs, "
                "falling back to %s",
                self._timeout,
                getattr(self._fallback, "name", "fallback"),
            )
            return await self._fallback.think(readings, state, memory_context)
        except Exception as exc:  # noqa: BLE001 - any failure must fall back
            logger.warning(
                "OllamaAwareThinker: primary raised %s, falling back to %s",
                type(exc).__name__,
                getattr(self._fallback, "name", "fallback"),
            )
            return await self._fallback.think(readings, state, memory_context)
