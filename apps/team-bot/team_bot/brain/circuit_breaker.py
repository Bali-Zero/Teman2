"""Per-model circuit breaker for the TP1 brain adapter.

One breaker per model slug (`qwen3.7-plus`, `qwen3.6-flash`, `glm-5.2` share
one door/key but fail independently — a stale pin on one tier must not stop
`BrainRouter` from trying the next). Classic three-state machine (CLOSED /
OPEN / HALF_OPEN); no framework, ~80 lines, per the same "hand-rolled typed
structure, not a framework" spirit F4 states for the tool loop.

Design choices, and why (team-lead brief: "circuit breaker that degrades to
read-only... never a dead mute bot" — self-healing by default, no operator
gesture required to recover):

- Every failure class eventually auto-heals via a cooldown timer — there is
  no manual-reset-only latch. `AUTH_DEAD`/`MODEL_NOT_FOUND` (a dead key or a
  deprecated pin) get a LONGER cooldown (`immediate_trip_cooldown_seconds`,
  default 300s) than transient classes (`cooldown_seconds`, default 60s)
  because retrying a dead key/pin every 60s wastes calls for no benefit, but
  the breaker still eventually rechecks on its own rather than requiring an
  SSH session at 3am.
- `AUTH_DEAD`/`MODEL_NOT_FOUND` trip on the FIRST occurrence
  (`immediate_trip_classes`) — one 401/404-model_not_found is already
  conclusive (a config/pin problem does not need three strikes to confirm).
  Every other failure class needs `failure_threshold` CONSECUTIVE failures
  (default 3) before tripping, so one transient 5xx/429/timeout does not
  yank a healthy model out of rotation.
- `record_success()` always closes the breaker immediately and clears every
  counter, including a latched/immediate trip — if a call just succeeded,
  whatever tripped it is empirically no longer true, and there is no value
  in refusing to believe fresh evidence.

Injectable `clock` (defaults to `time.monotonic`) — never wall-clock `Date.now()`-
style nondeterminism in the tests; `test_circuit_breaker.py` uses a fake
clock it advances explicitly.

Author: Claude (lane B4-tp1 — team-bot TP1 brain adapter).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from time import monotonic

from .errors import BrainErrorClass

__all__ = ["BreakerConfig", "BreakerState", "CircuitBreaker"]

_DEFAULT_IMMEDIATE_TRIP_CLASSES: frozenset[BrainErrorClass] = frozenset(
    {BrainErrorClass.AUTH_DEAD, BrainErrorClass.MODEL_NOT_FOUND}
)


class BreakerState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass(frozen=True, slots=True)
class BreakerConfig:
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    immediate_trip_cooldown_seconds: float = 300.0
    immediate_trip_classes: frozenset[BrainErrorClass] = field(
        default_factory=lambda: _DEFAULT_IMMEDIATE_TRIP_CLASSES
    )

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.cooldown_seconds <= 0 or self.immediate_trip_cooldown_seconds <= 0:
            raise ValueError("cooldown durations must be > 0")


class CircuitBreaker:
    """One breaker instance per model slug. Not thread-safe by itself —
    `BrainRouter` owns one instance per model and calls it from a single
    asyncio task at a time per model (no shared mutation across concurrent
    coroutines without an external lock)."""

    def __init__(
        self,
        model_slug: str,
        config: BreakerConfig | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.model_slug = model_slug
        self._config = config or BreakerConfig()
        self._clock = clock
        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._cooldown_seconds = self._config.cooldown_seconds
        self._half_open_trial_in_flight = False

    @property
    def state(self) -> BreakerState:
        """Resolves OPEN -> HALF_OPEN lazily (as of now, via the injected
        clock) rather than requiring a background timer."""
        if self._state is BreakerState.OPEN and self._opened_at is not None:
            elapsed = self._clock() - self._opened_at
            if elapsed >= self._cooldown_seconds:
                return BreakerState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        """CLOSED -> always allow. OPEN (cooldown not elapsed) -> refuse.
        HALF_OPEN -> allow exactly ONE trial call at a time (a second
        concurrent caller while a trial is in flight is refused, so a
        burst of calls arriving the instant the cooldown elapses cannot
        all pile onto the still-unproven model at once)."""
        current = self.state
        if current is BreakerState.CLOSED:
            return True
        if current is BreakerState.OPEN:
            return False
        # HALF_OPEN
        if self._half_open_trial_in_flight:
            return False
        self._half_open_trial_in_flight = True
        return True

    def record_success(self) -> None:
        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None
        self._half_open_trial_in_flight = False

    def record_failure(self, error_class: BrainErrorClass) -> None:
        self._half_open_trial_in_flight = False
        self._consecutive_failures += 1
        immediate = error_class in self._config.immediate_trip_classes
        if immediate or self._consecutive_failures >= self._config.failure_threshold:
            self._state = BreakerState.OPEN
            self._opened_at = self._clock()
            self._cooldown_seconds = (
                self._config.immediate_trip_cooldown_seconds
                if immediate
                else self._config.cooldown_seconds
            )

    def reset(self) -> None:
        """Manual override for ops tooling/tests — never required for the
        breaker to self-heal (see module docstring), but available."""
        self.record_success()
