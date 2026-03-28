"""Unit tests for CB_T4 circuit breaker FSM."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import (
    CB_T4_FAILURE_THRESHOLD,
    T4CircuitBreaker,
)
from apps.evaluator.nlm_deep_research.t4_state import T4State


class TestT4CircuitBreaker:
    def _state(self, **kwargs) -> T4State:
        return T4State(**kwargs)

    def test_fresh_state_is_closed(self):
        cb = T4CircuitBreaker()
        state = self._state()
        assert cb.is_open(state) is False

    def test_three_failures_opens_cb(self):
        cb = T4CircuitBreaker()
        state = self._state()
        cb.record_failure(state)
        cb.record_failure(state)
        cb.record_failure(state)
        assert state.cb_status == "OPEN"

    def test_two_failures_stays_closed(self):
        cb = T4CircuitBreaker()
        state = self._state()
        cb.record_failure(state)
        cb.record_failure(state)
        assert state.cb_status == "CLOSED"

    def test_success_resets_failure_count(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_failure_count=2)
        cb.record_success(state)
        assert state.cb_failure_count == 0
        assert state.cb_status == "CLOSED"

    def test_open_cb_stays_open_before_timeout(self):
        cb = T4CircuitBreaker()
        state = self._state(
            cb_status="OPEN",
            cb_last_failure=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        assert cb.is_open(state) is True

    def test_open_cb_transitions_to_half_open_after_timeout(self):
        cb = T4CircuitBreaker()
        state = self._state(
            cb_status="OPEN",
            cb_last_failure=datetime.now(timezone.utc) - timedelta(minutes=35),
        )
        cb.maybe_transition(state)
        assert state.cb_status == "HALF_OPEN"

    def test_half_open_success_closes_cb(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_status="HALF_OPEN")
        cb.record_success(state)
        assert state.cb_status == "CLOSED"

    def test_half_open_failure_reopens_cb(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_status="HALF_OPEN")
        cb.record_failure(state)
        assert state.cb_status == "OPEN"

    def test_dom_changed_opens_immediately(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_failure_count=0)
        cb.open_immediately(state, reason="DOMChangedError")
        assert state.cb_status == "OPEN"
        assert state.cb_failure_count >= CB_T4_FAILURE_THRESHOLD

    def test_is_open_returns_false_when_closed(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_status="CLOSED")
        assert cb.is_open(state) is False
