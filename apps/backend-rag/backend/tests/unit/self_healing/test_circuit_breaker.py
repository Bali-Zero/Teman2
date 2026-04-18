"""
Unit tests for the per-check circuit breaker used by self_healing.orchestrator.
"""

from __future__ import annotations

from backend.self_healing.circuit_breaker import BreakerState, CircuitBreaker


class ClockStub:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class TestCircuitBreaker:
    def test_starts_closed_and_allows(self):
        cb = CircuitBreaker("x")
        assert cb.state is BreakerState.CLOSED
        assert cb.allow() is True

    def test_opens_after_threshold_failures(self):
        clock = ClockStub()
        cb = CircuitBreaker("x", failure_threshold=3, cooldown_seconds=60, now=clock)
        cb.record_failure("e1")
        cb.record_failure("e2")
        assert cb.state is BreakerState.CLOSED
        cb.record_failure("e3")
        assert cb.state is BreakerState.OPEN
        assert cb.opened_at == 0.0
        # While OPEN and inside cooldown, allow() is False
        assert cb.allow() is False

    def test_transitions_to_half_open_after_cooldown(self):
        clock = ClockStub()
        cb = CircuitBreaker("x", failure_threshold=2, cooldown_seconds=30, now=clock)
        cb.record_failure("e1")
        cb.record_failure("e2")
        assert cb.state is BreakerState.OPEN
        assert cb.allow() is False

        clock.t = 29.5
        assert cb.allow() is False

        clock.t = 30.0
        assert cb.allow() is True
        assert cb.state is BreakerState.HALF_OPEN

    def test_half_open_success_closes(self):
        clock = ClockStub()
        cb = CircuitBreaker("x", failure_threshold=1, cooldown_seconds=10, now=clock)
        cb.record_failure()
        assert cb.state is BreakerState.OPEN
        clock.t = 11
        cb.allow()  # half-open
        cb.record_success()
        assert cb.state is BreakerState.CLOSED
        assert cb.consecutive_failures == 0
        assert cb.last_error is None

    def test_half_open_failure_reopens(self):
        clock = ClockStub()
        cb = CircuitBreaker("x", failure_threshold=1, cooldown_seconds=10, now=clock)
        cb.record_failure()
        clock.t = 20
        cb.allow()
        cb.record_failure("again")
        assert cb.state is BreakerState.OPEN
        assert cb.opened_at == 20

    def test_snapshot_shape(self):
        cb = CircuitBreaker("db", failure_threshold=2, cooldown_seconds=45)
        snap = cb.snapshot()
        assert snap["name"] == "db"
        assert snap["state"] == "closed"
        assert snap["failure_threshold"] == 2
        assert snap["cooldown_seconds"] == 45
        assert snap["consecutive_failures"] == 0
