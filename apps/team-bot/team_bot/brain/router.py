"""BrainRouter — the pluggable-brain fallback chain (directive#1§1):

    qwen3.7-plus -> qwen3.6-flash -> glm-5.2 -> local read-only (Mini, R0 only)

Each cloud tier has its own `CircuitBreaker` (`circuit_breaker.py`); a tier
whose breaker is OPEN is skipped without a network call. `TEAM_BOT_BRAIN_TP1_ENABLED`
(`flags.py`, default OFF) gates ALL THREE cloud tiers at once — while it is
`False`, every turn goes straight to local read-only, which is exactly the
"never a dead mute bot" contract: there is no code path in `complete()` that
returns nothing or raises past a caller without a `BrainCompletion` UNLESS
local read-only *itself* also fails, and that specific case is its own named
exception (`BrainRouterExhaustedError`), not a silent `None`.

Every attempt (skipped-by-breaker, skipped-by-kill-switch, errored, or
succeeded) is recorded in `BrainCompletion.attempts` — an audit trail for
observability (F11) without needing to re-derive "why did it fall back to
local?" from scattered log lines.

Author: Claude (lane B4-tp1 — team-bot TP1 brain adapter).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from team_bot.flags import is_team_bot_brain_tp1_enabled

from .circuit_breaker import BreakerConfig, CircuitBreaker
from .depletion_probe import DepletionAlarm, DepletionProbe
from .errors import BrainErrorClass
from .local_readonly import LocalReadOnlyClient
from .tp1_client import BrainCallError, BrainCallResult, TP1Client, TP1Model

__all__ = [
    "BrainAttemptLog",
    "BrainCompletion",
    "BrainRouter",
    "BrainRouterExhaustedError",
    "BrainTier",
]

logger = logging.getLogger(__name__)

_CHAIN: tuple[TP1Model, ...] = (
    TP1Model.QWEN_3_7_PLUS,
    TP1Model.QWEN_3_6_FLASH,
    TP1Model.GLM_5_2,
)


class BrainTier(StrEnum):
    TP1_QWEN_3_7_PLUS = "tp1:qwen3.7-plus"
    TP1_QWEN_3_6_FLASH = "tp1:qwen3.6-flash"
    TP1_GLM_5_2 = "tp1:glm-5.2"
    LOCAL_READ_ONLY = "local_read_only"


_TIER_FOR_MODEL: dict[TP1Model, BrainTier] = {
    TP1Model.QWEN_3_7_PLUS: BrainTier.TP1_QWEN_3_7_PLUS,
    TP1Model.QWEN_3_6_FLASH: BrainTier.TP1_QWEN_3_6_FLASH,
    TP1Model.GLM_5_2: BrainTier.TP1_GLM_5_2,
}

AttemptOutcome = Literal["skipped_kill_switch", "skipped_breaker_open", "error", "success"]


@dataclass(frozen=True, slots=True)
class BrainAttemptLog:
    tier: BrainTier
    outcome: AttemptOutcome
    error_class: BrainErrorClass | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class BrainCompletion:
    tier: BrainTier
    result: BrainCallResult
    degraded: bool
    degraded_reason: str | None
    attempts: tuple[BrainAttemptLog, ...]
    alarms: tuple[DepletionAlarm, ...] = ()


class BrainRouterExhaustedError(RuntimeError):
    """Raised only when EVERY tier failed, including local read-only — the
    one genuine "dead mute bot" case. Callers must treat this as a hard
    failure to surface (an operator alert), never as a silent empty reply:
    the whole point of the fallback chain is that this should be rare."""

    def __init__(self, attempts: tuple[BrainAttemptLog, ...]) -> None:
        self.attempts = attempts
        summary = "; ".join(f"{a.tier}:{a.outcome}" for a in attempts)
        super().__init__(f"every brain tier failed: {summary}")


class BrainRouter:
    def __init__(
        self,
        *,
        tp1_client: TP1Client,
        local_client: LocalReadOnlyClient,
        depletion_probe: DepletionProbe,
        breaker_config: BreakerConfig | None = None,
        breakers: dict[TP1Model, CircuitBreaker] | None = None,
        is_tp1_enabled: Callable[[], bool] = is_team_bot_brain_tp1_enabled,
    ) -> None:
        self._tp1 = tp1_client
        self._local = local_client
        self._probe = depletion_probe
        self._breakers: dict[TP1Model, CircuitBreaker] = breakers or {
            model: CircuitBreaker(model.value, config=breaker_config) for model in _CHAIN
        }
        self._is_tp1_enabled = is_tp1_enabled

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        max_tokens: int,
        enable_thinking: bool = False,
    ) -> BrainCompletion:
        attempts: list[BrainAttemptLog] = []

        if not self._is_tp1_enabled():
            attempts.append(
                BrainAttemptLog(
                    tier=BrainTier.TP1_QWEN_3_7_PLUS,
                    outcome="skipped_kill_switch",
                    detail="TEAM_BOT_BRAIN_TP1_ENABLED is false — all cloud tiers skipped",
                )
            )
        else:
            for model in _CHAIN:
                tier = _TIER_FOR_MODEL[model]
                breaker = self._breakers[model]
                if not breaker.allow_request():
                    attempts.append(BrainAttemptLog(tier=tier, outcome="skipped_breaker_open"))
                    continue
                try:
                    result = await self._tp1.chat_completion(
                        model=model,
                        messages=messages,
                        tools=tools,
                        tool_choice=tool_choice,
                        max_tokens=max_tokens,
                        enable_thinking=enable_thinking,
                    )
                except BrainCallError as e:
                    breaker.record_failure(e.verdict.error_class)
                    attempts.append(
                        BrainAttemptLog(
                            tier=tier,
                            outcome="error",
                            error_class=e.verdict.error_class,
                            detail=e.verdict.detail,
                        )
                    )
                    logger.warning(
                        "brain tier %s failed: %s (%s)", tier, e.verdict.error_class, e.verdict.detail
                    )
                    continue

                breaker.record_success()
                self._probe.record(result.usage)
                alarms = self._probe.check_alarms()
                for alarm in alarms:
                    logger.warning(
                        "TP1 depletion alarm: %.0f%% headroom remaining (%d/%d tokens used, %ds window)",
                        alarm.remaining_fraction * 100,
                        alarm.used_tokens,
                        alarm.quota_tokens,
                        int(alarm.window_seconds),
                    )
                attempts.append(BrainAttemptLog(tier=tier, outcome="success"))
                return BrainCompletion(
                    tier=tier,
                    result=result,
                    degraded=False,
                    degraded_reason=None,
                    attempts=tuple(attempts),
                    alarms=tuple(alarms),
                )

        # Every cloud tier skipped/exhausted (or the kill switch is off) —
        # local read-only is the final, always-attempted lane.
        try:
            local_result = await self._local.chat_completion(messages=messages, max_tokens=max_tokens)
        except BrainCallError as e:
            attempts.append(
                BrainAttemptLog(
                    tier=BrainTier.LOCAL_READ_ONLY,
                    outcome="error",
                    error_class=e.verdict.error_class,
                    detail=e.verdict.detail,
                )
            )
            logger.error("local read-only brain also failed: %s", e.verdict.detail)
            raise BrainRouterExhaustedError(tuple(attempts)) from e

        attempts.append(BrainAttemptLog(tier=BrainTier.LOCAL_READ_ONLY, outcome="success"))
        return BrainCompletion(
            tier=BrainTier.LOCAL_READ_ONLY,
            result=local_result.call,
            degraded=local_result.degraded,
            degraded_reason=local_result.degraded_reason,
            attempts=tuple(attempts),
        )
