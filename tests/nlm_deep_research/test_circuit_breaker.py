"""Tests for circuit_breaker.py — FSM transitions, cascade, persistence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.evaluator.nlm_deep_research.circuit_breaker import (
    CB_NLM_FAILURE_THRESHOLD,
    CB_NLM_TIMEOUT_HOURS,
    CB_SOURCE_TIMEOUT_HOURS,
    CASCADE_NLM_TO_SOURCE_DAYS,
    CASCADE_SOURCE_TO_INTEGRATION_DAYS,
    CBName,
    CBState,
    CircuitBreaker,
    CircuitBreakerRegistry,
)

from .conftest import make_cb


# =====================================================================
# CircuitBreaker — FSM transitions
# =====================================================================


class TestCircuitBreakerFSM:
    """Tests for individual circuit breaker state machine."""

    def test_initial_state_is_closed(self):
        cb = make_cb()
        assert cb.state == CBState.CLOSED
        assert cb.is_open is False
        assert cb.should_allow_request() is True

    def test_failures_below_threshold_stay_closed(self):
        cb = make_cb()
        for _ in range(CB_NLM_FAILURE_THRESHOLD - 1):
            cb.record_failure()
        assert cb.state == CBState.CLOSED
        assert cb.is_open is False

    def test_failures_at_threshold_trip_to_open(self):
        cb = make_cb()
        for _ in range(CB_NLM_FAILURE_THRESHOLD):
            cb.record_failure()
        assert cb.state == CBState.OPEN
        assert cb.is_open is True
        assert cb.should_allow_request() is False

    def test_success_resets_failure_count(self):
        cb = make_cb()
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0

    def test_success_in_half_open_transitions_to_closed(self):
        cb = make_cb(state=CBState.HALF_OPEN, failure_count=3)
        cb.record_success()
        assert cb.state == CBState.CLOSED
        assert cb.failure_count == 0
        assert cb.opened_at is None

    def test_failure_in_half_open_reopens(self):
        cb = make_cb(state=CBState.HALF_OPEN, failure_count=2)
        cb.record_failure()
        assert cb.state == CBState.OPEN
        assert cb.opened_at is not None

    def test_force_open(self):
        cb = make_cb()
        cb.force_open(reason="test")
        assert cb.state == CBState.OPEN
        assert cb.opened_at is not None

    def test_force_open_when_already_open_is_noop(self):
        cb = make_cb(state=CBState.OPEN, opened_at="2026-03-28T00:00:00+00:00")
        original_opened_at = cb.opened_at
        cb.force_open(reason="redundant")
        assert cb.opened_at == original_opened_at

    def test_force_close(self):
        cb = make_cb(state=CBState.OPEN, failure_count=5, opened_at="2026-03-28T00:00:00+00:00")
        cb.force_close()
        assert cb.state == CBState.CLOSED
        assert cb.failure_count == 0
        assert cb.opened_at is None


class TestCircuitBreakerTimeout:
    """Tests for automatic OPEN -> HALF_OPEN timeout transitions."""

    def test_timeout_transitions_to_half_open(self):
        """After timeout_hours, OPEN should become HALF_OPEN."""
        opened_time = datetime.now(tz=timezone.utc) - timedelta(hours=CB_NLM_TIMEOUT_HOURS + 1)
        cb = make_cb(state=CBState.OPEN, opened_at=opened_time.isoformat())
        # get_state evaluates timeout
        state = cb.get_state()
        assert state == CBState.HALF_OPEN

    def test_no_timeout_before_deadline(self):
        """Before timeout_hours, OPEN should stay OPEN."""
        opened_time = datetime.now(tz=timezone.utc) - timedelta(hours=CB_NLM_TIMEOUT_HOURS - 1)
        cb = make_cb(state=CBState.OPEN, opened_at=opened_time.isoformat())
        state = cb.get_state()
        assert state == CBState.OPEN

    def test_manual_close_only_never_auto_transitions(self):
        """CB_SOURCE has timeout_hours=-1 and should never auto-transition."""
        opened_time = datetime.now(tz=timezone.utc) - timedelta(days=365)
        cb = make_cb(
            name=CBName.CB_SOURCE,
            state=CBState.OPEN,
            opened_at=opened_time.isoformat(),
        )
        state = cb.get_state()
        assert state == CBState.OPEN  # still open after a year

    def test_is_open_evaluates_timeout(self):
        """is_open property should auto-transition if timeout elapsed."""
        opened_time = datetime.now(tz=timezone.utc) - timedelta(hours=CB_NLM_TIMEOUT_HOURS + 1)
        cb = make_cb(state=CBState.OPEN, opened_at=opened_time.isoformat())
        assert cb.is_open is False  # transitions to HALF_OPEN first
        assert cb.state == CBState.HALF_OPEN


# =====================================================================
# CircuitBreaker — Serialization
# =====================================================================


class TestCircuitBreakerSerialization:
    """Tests for to_dict / from_dict round-trip."""

    def test_to_dict_keys(self):
        cb = make_cb(failure_count=2)
        cb.record_failure()  # make it 3, trip to OPEN
        d = cb.to_dict()
        assert "state" in d
        assert "failure_count" in d
        assert d["state"] == "OPEN"

    def test_from_dict_restores_state(self):
        data = {
            "state": "OPEN",
            "failure_count": 3,
            "last_failure": "2026-03-28T10:00:00+00:00",
            "opened_at": "2026-03-28T10:00:00+00:00",
        }
        cb = CircuitBreaker.from_dict(
            name=CBName.CB_NLM,
            data=data,
            failure_threshold=CB_NLM_FAILURE_THRESHOLD,
            timeout_hours=CB_NLM_TIMEOUT_HOURS,
        )
        assert cb.state == CBState.OPEN
        assert cb.failure_count == 3
        assert cb.opened_at == "2026-03-28T10:00:00+00:00"

    def test_round_trip(self):
        cb = make_cb(failure_count=1)
        cb.record_failure()
        d = cb.to_dict()
        restored = CircuitBreaker.from_dict(
            name=cb.name,
            data=d,
            failure_threshold=cb.failure_threshold,
            timeout_hours=cb.timeout_hours,
        )
        assert restored.state == cb.state
        assert restored.failure_count == cb.failure_count

    def test_manual_close_marker_in_dict(self):
        cb = make_cb(name=CBName.CB_SOURCE)
        d = cb.to_dict()
        assert d.get("manual_close_only") is True
        assert "auto_close_after_hours" not in d

    def test_auto_close_marker_in_dict(self):
        cb = make_cb(name=CBName.CB_NLM)
        d = cb.to_dict()
        assert d.get("auto_close_after_hours") == CB_NLM_TIMEOUT_HOURS
        assert "manual_close_only" not in d


# =====================================================================
# CircuitBreakerRegistry — Cascade rules
# =====================================================================


class TestCascadeRules:
    """Tests for inter-breaker cascade logic."""

    def test_nlm_open_long_cascades_to_source(self):
        registry = CircuitBreakerRegistry()
        # CB_NLM open for > CASCADE_NLM_TO_SOURCE_DAYS
        opened_time = (
            datetime.now(tz=timezone.utc)
            - timedelta(days=CASCADE_NLM_TO_SOURCE_DAYS + 1)
        )
        registry.nlm.state = CBState.OPEN
        registry.nlm.opened_at = opened_time.isoformat()

        registry.evaluate_cascades()
        assert registry.source.state == CBState.OPEN

    def test_nlm_open_short_no_cascade(self):
        registry = CircuitBreakerRegistry()
        opened_time = (
            datetime.now(tz=timezone.utc)
            - timedelta(days=CASCADE_NLM_TO_SOURCE_DAYS - 1)
        )
        registry.nlm.state = CBState.OPEN
        registry.nlm.opened_at = opened_time.isoformat()

        registry.evaluate_cascades()
        assert registry.source.state == CBState.CLOSED

    def test_source_open_long_cascades_to_integration(self):
        registry = CircuitBreakerRegistry()
        opened_time = (
            datetime.now(tz=timezone.utc)
            - timedelta(days=CASCADE_SOURCE_TO_INTEGRATION_DAYS + 1)
        )
        registry.source.state = CBState.OPEN
        registry.source.opened_at = opened_time.isoformat()

        registry.evaluate_cascades()
        assert registry.integration.state == CBState.OPEN

    def test_closed_upstream_no_cascade(self):
        registry = CircuitBreakerRegistry()
        # All closed
        registry.evaluate_cascades()
        assert registry.source.state == CBState.CLOSED
        assert registry.integration.state == CBState.CLOSED

    def test_get_by_name(self):
        registry = CircuitBreakerRegistry()
        assert registry.get(CBName.CB_NLM) is registry.nlm
        assert registry.get(CBName.CB_SOURCE) is registry.source
        assert registry.get(CBName.CB_INTEGRATION) is registry.integration


# =====================================================================
# CircuitBreakerRegistry — Persistence
# =====================================================================


class TestRegistryPersistence:
    """Tests for save/load with pipeline_state.json."""

    def test_save_creates_file(self, tmp_path):
        state_path = tmp_path / "state.json"
        registry = CircuitBreakerRegistry(state_path=state_path)
        registry.nlm.record_failure()
        registry.save()
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert "circuit_breakers" in data
        assert CBName.CB_NLM.value in data["circuit_breakers"]

    def test_load_from_empty_dir(self, tmp_path):
        state_path = tmp_path / "nonexistent.json"
        registry = CircuitBreakerRegistry.load(state_path=state_path)
        assert registry.nlm.state == CBState.CLOSED
        assert registry.source.state == CBState.CLOSED
        assert registry.integration.state == CBState.CLOSED

    def test_save_then_load_round_trip(self, tmp_path):
        state_path = tmp_path / "state.json"
        reg1 = CircuitBreakerRegistry(state_path=state_path)
        # Trip NLM breaker
        for _ in range(CB_NLM_FAILURE_THRESHOLD):
            reg1.nlm.record_failure()
        reg1.save()

        reg2 = CircuitBreakerRegistry.load(state_path=state_path)
        assert reg2.nlm.state == CBState.OPEN
        assert reg2.nlm.failure_count == CB_NLM_FAILURE_THRESHOLD

    def test_load_corrupted_file(self, tmp_path):
        state_path = tmp_path / "state.json"
        state_path.write_text("NOT VALID JSON {{{")
        registry = CircuitBreakerRegistry.load(state_path=state_path)
        # Should fall back to defaults
        assert registry.nlm.state == CBState.CLOSED

    def test_save_preserves_existing_state_data(self, tmp_path):
        state_path = tmp_path / "state.json"
        # Pre-populate with extra data
        state_path.write_text(json.dumps({"extra_key": "preserved", "circuit_breakers": {}}))
        registry = CircuitBreakerRegistry(state_path=state_path)
        registry.save()
        data = json.loads(state_path.read_text())
        assert data["extra_key"] == "preserved"
        assert "circuit_breakers" in data
