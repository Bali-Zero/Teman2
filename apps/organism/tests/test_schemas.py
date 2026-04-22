import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from organism.schemas import Event, Severity, ActionDecision


def test_event_minimal_valid():
    e = Event(
        severity=Severity.CRITICAL,
        source="guardian.system_doctor",
        kind="cron_agent_failure",
        payload={"agent": "core-guardian", "exit_code": 1},
        correlation_id="abc-123",
        host="Pro",
    )
    assert e.is_actuation is False
    assert e.ts.tzinfo is timezone.utc


def test_event_payload_max_2kb():
    big = {"x": "a" * 3000}
    with pytest.raises(ValidationError, match="payload_too_large"):
        Event(
            severity=Severity.INFO, source="test", kind="test",
            payload=big, correlation_id="x", host="Pro",
        )


def test_action_decision_requires_actuator_name():
    with pytest.raises(ValidationError):
        ActionDecision(params={}, confidence=0.5, tier="L0_yaml")  # missing actuator


def test_event_payload_with_path_serializable():
    """Guardian W0.2 will pass Path objects in payload — must not raise TypeError."""
    from pathlib import Path
    e = Event(
        severity=Severity.ERROR,
        source="guardian.system_doctor",
        kind="cron_agent_failure",
        payload={"log_path": Path("/tmp/test.log"), "agent": "x"},
        correlation_id="c",
        host="Pro",
    )
    assert e.payload["agent"] == "x"
