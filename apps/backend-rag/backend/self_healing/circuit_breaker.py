"""
Per-check circuit breaker.

After N consecutive failures, a check enters OPEN state and is skipped
for a cooldown window. When cooldown elapses, the breaker moves to
HALF_OPEN — the next run decides CLOSED (success) or OPEN (new cooldown).

Thresholds and cooldown are per-instance so each check can tune its own
sensitivity. Defaults: 3 failures → 60s cooldown.
"""

from __future__ import annotations

import time
from enum import Enum


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        now: callable = time.monotonic,  # type: ignore[assignment]
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._now = now

        self.state: BreakerState = BreakerState.CLOSED
        self.consecutive_failures: int = 0
        self.opened_at: float | None = None
        self.last_error: str | None = None
        self.total_successes: int = 0
        self.total_failures: int = 0

    def allow(self) -> bool:
        """Return True if the next call should be allowed through."""
        if self.state is BreakerState.CLOSED:
            return True
        if self.state is BreakerState.OPEN:
            # Has cooldown elapsed?
            if self.opened_at is None:
                return True  # Defensive — shouldn't happen
            if self._now() - self.opened_at >= self.cooldown_seconds:
                self.state = BreakerState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow exactly one probe
        return True

    def record_success(self) -> None:
        self.total_successes += 1
        self.consecutive_failures = 0
        self.state = BreakerState.CLOSED
        self.opened_at = None
        self.last_error = None

    def record_failure(self, error: str | None = None) -> None:
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_error = error
        if self.consecutive_failures >= self.failure_threshold:
            self.state = BreakerState.OPEN
            self.opened_at = self._now()

    def snapshot(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "failure_threshold": self.failure_threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "opened_at": self.opened_at,
            "last_error": self.last_error,
        }
