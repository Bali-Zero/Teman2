"""Tests for team_bot.brain.circuit_breaker. Uses an injectable fake clock
(never real time — deterministic, no sleeps)."""

from __future__ import annotations

from team_bot.brain.circuit_breaker import BreakerConfig, BreakerState, CircuitBreaker
from team_bot.brain.errors import BrainErrorClass


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def _config(**overrides: object) -> BreakerConfig:
    base = {"failure_threshold": 3, "cooldown_seconds": 60.0, "immediate_trip_cooldown_seconds": 300.0}
    base.update(overrides)
    return BreakerConfig(**base)  # type: ignore[arg-type]


def test_starts_closed_and_allows_requests() -> None:
    b = CircuitBreaker("qwen3.7-plus")
    assert b.state is BreakerState.CLOSED
    assert b.allow_request() is True


def test_stays_closed_below_failure_threshold() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    b.record_failure(BrainErrorClass.SERVER_ERROR)
    b.record_failure(BrainErrorClass.SERVER_ERROR)
    assert b.state is BreakerState.CLOSED
    assert b.allow_request() is True


def test_trips_open_at_threshold_consecutive_failures() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    for _ in range(3):
        b.record_failure(BrainErrorClass.SERVER_ERROR)
    assert b.state is BreakerState.OPEN
    assert b.allow_request() is False


def test_success_resets_consecutive_failure_count() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    b.record_failure(BrainErrorClass.SERVER_ERROR)
    b.record_failure(BrainErrorClass.SERVER_ERROR)
    b.record_success()
    b.record_failure(BrainErrorClass.SERVER_ERROR)
    b.record_failure(BrainErrorClass.SERVER_ERROR)
    # Only 2 consecutive since the reset — must still be CLOSED.
    assert b.state is BreakerState.CLOSED


def test_auth_dead_trips_on_first_occurrence() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    b.record_failure(BrainErrorClass.AUTH_DEAD)
    assert b.state is BreakerState.OPEN


def test_model_not_found_trips_on_first_occurrence() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    b.record_failure(BrainErrorClass.MODEL_NOT_FOUND)
    assert b.state is BreakerState.OPEN


def test_open_transitions_to_half_open_after_cooldown() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(cooldown_seconds=60.0), clock=clock)
    for _ in range(3):
        b.record_failure(BrainErrorClass.SERVER_ERROR)
    assert b.state is BreakerState.OPEN
    clock.advance(59.9)
    assert b.state is BreakerState.OPEN
    clock.advance(0.2)
    assert b.state is BreakerState.HALF_OPEN


def test_immediate_trip_class_uses_the_longer_cooldown() -> None:
    clock = FakeClock()
    b = CircuitBreaker(
        "qwen3.7-plus",
        config=_config(cooldown_seconds=60.0, immediate_trip_cooldown_seconds=300.0),
        clock=clock,
    )
    b.record_failure(BrainErrorClass.AUTH_DEAD)
    clock.advance(61.0)  # past the SHORT cooldown, not the immediate one
    assert b.state is BreakerState.OPEN
    clock.advance(240.0)  # now past 300s total
    assert b.state is BreakerState.HALF_OPEN


def test_half_open_allows_exactly_one_trial_call() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(cooldown_seconds=60.0), clock=clock)
    for _ in range(3):
        b.record_failure(BrainErrorClass.SERVER_ERROR)
    clock.advance(61.0)
    assert b.state is BreakerState.HALF_OPEN
    assert b.allow_request() is True  # the one trial
    assert b.allow_request() is False  # a second concurrent caller is refused


def test_half_open_success_closes_the_breaker() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(cooldown_seconds=60.0), clock=clock)
    for _ in range(3):
        b.record_failure(BrainErrorClass.SERVER_ERROR)
    clock.advance(61.0)
    assert b.allow_request() is True
    b.record_success()
    assert b.state is BreakerState.CLOSED
    assert b.allow_request() is True


def test_half_open_failure_reopens_with_fresh_cooldown() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(cooldown_seconds=60.0), clock=clock)
    for _ in range(3):
        b.record_failure(BrainErrorClass.SERVER_ERROR)
    clock.advance(61.0)
    assert b.allow_request() is True
    b.record_failure(BrainErrorClass.SERVER_ERROR)
    assert b.state is BreakerState.OPEN
    clock.advance(59.0)
    assert b.state is BreakerState.OPEN
    clock.advance(2.0)
    assert b.state is BreakerState.HALF_OPEN


def test_success_always_clears_even_an_immediate_trip_latch() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    b.record_failure(BrainErrorClass.AUTH_DEAD)
    assert b.state is BreakerState.OPEN
    b.record_success()
    assert b.state is BreakerState.CLOSED
    assert b.allow_request() is True


def test_reset_is_equivalent_to_a_manual_success() -> None:
    clock = FakeClock()
    b = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    b.record_failure(BrainErrorClass.AUTH_DEAD)
    assert b.state is BreakerState.OPEN
    b.reset()
    assert b.state is BreakerState.CLOSED


def test_invalid_configs_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        BreakerConfig(failure_threshold=0)
    with pytest.raises(ValueError):
        BreakerConfig(cooldown_seconds=0)
    with pytest.raises(ValueError):
        BreakerConfig(immediate_trip_cooldown_seconds=-1)


def test_breakers_for_different_models_are_independent() -> None:
    clock = FakeClock()
    a = CircuitBreaker("qwen3.7-plus", config=_config(), clock=clock)
    b = CircuitBreaker("qwen3.6-flash", config=_config(), clock=clock)
    a.record_failure(BrainErrorClass.AUTH_DEAD)
    assert a.state is BreakerState.OPEN
    assert b.state is BreakerState.CLOSED
