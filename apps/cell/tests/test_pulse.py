"""Tests for the pulse cycle — CELL's heartbeat."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cell.core.dna_interpreter import DNAInterpreter
from cell.core.pulse import PulseEngine
from cell.fast.health_triage import HealthStatus


@pytest.fixture
def mock_deps() -> dict:
    return {
        "dna_loader": MagicMock(),
        "safety_gate": AsyncMock(),
        "health_sensor": AsyncMock(),
        "metabolism": MagicMock(),
    }


@pytest.mark.asyncio
async def test_pulse_dna_check_fails(mock_deps: dict) -> None:
    mock_deps["dna_loader"].verify_integrity.return_value = False
    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash")
    result = await engine.single_pulse()
    assert result.halted is True
    assert "dna" in result.halt_reason.lower()


@pytest.mark.asyncio
async def test_pulse_disabled(mock_deps: dict) -> None:
    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = False
    safety_result.reason = "disabled"
    safety_result.detail = "Redis key set"
    mock_deps["safety_gate"].check.return_value = safety_result
    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash")
    result = await engine.single_pulse()
    assert result.skipped is True
    assert result.skip_reason == "disabled"


@pytest.mark.asyncio
async def test_pulse_healthy_system(mock_deps: dict) -> None:
    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = True
    mock_deps["safety_gate"].check.return_value = safety_result
    health_reading = MagicMock()
    health_reading.reachable = True
    health_reading.status_code = 200
    health_reading.response_time_seconds = 0.1
    mock_deps["health_sensor"].read.return_value = health_reading
    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash")
    result = await engine.single_pulse()
    assert result.halted is False
    assert result.skipped is False
    assert result.health_status == HealthStatus.GREEN
    assert result.action_taken is None


@pytest.mark.asyncio
async def test_pulse_updates_homeostatic_state(mock_deps: dict) -> None:
    """Homeostatic controller gets updated each pulse."""
    from cell.fast.homeostatic_controller import HomeostaticController
    homeo = HomeostaticController()
    initial_setpoint = homeo.state.setpoint_rt_ms

    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = True
    mock_deps["safety_gate"].check.return_value = safety_result
    health_reading = MagicMock()
    health_reading.reachable = True
    health_reading.status_code = 200
    health_reading.response_time_seconds = 0.5
    mock_deps["health_sensor"].read.return_value = health_reading

    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash", homeostatic=homeo)
    await engine.single_pulse(pulse_number=1)

    # Setpoint should have moved toward 500ms (from default ~100ms)
    assert homeo.state.setpoint_rt_ms != initial_setpoint


# ---------------------------------------------------------------------------
# TestPulseOutboxWiring (LEVA 3, 2026-05-13)
# ---------------------------------------------------------------------------


def _make_healthy_pulse_deps() -> dict:
    """Same shape as the mock_deps fixture but inlined for the wiring tests."""
    dna = MagicMock()
    dna.verify_integrity.return_value = True
    safety = AsyncMock()
    safety_result = MagicMock()
    safety_result.can_proceed = True
    safety.check.return_value = safety_result
    health = AsyncMock()
    health_reading = MagicMock()
    health_reading.reachable = True
    health_reading.status_code = 200
    health_reading.response_time_seconds = 0.1
    health.read.return_value = health_reading
    metabolism = MagicMock()
    return {
        "dna_loader": dna,
        "safety_gate": safety,
        "health_sensor": health,
        "metabolism": metabolism,
    }


def _make_outbox_sensor(status: str, count: int = 0) -> MagicMock:
    """Return an outbox sensor mock that returns a deterministic reading."""
    reading = MagicMock()
    reading.status = status
    reading.metadata = {
        "unconsumed_count": count,
        "channel": None,
        "channels": ["cell_pulse_observed"],
        "exclude": True,
        "lookback_seconds": 3600,
        "red_threshold": 200,
    }
    sensor = MagicMock()
    sensor.read = AsyncMock(return_value=reading)
    return sensor


def _make_backup_sensor(status: str, metadata: dict) -> MagicMock:
    reading = MagicMock()
    reading.status = status
    reading.metadata = metadata
    sensor = MagicMock()
    sensor.read.return_value = reading
    return sensor


@pytest.mark.asyncio
async def test_pulse_without_outbox_sensor_is_no_op() -> None:
    """A PulseEngine with outbox_sensor=None (default) must work unchanged."""
    deps = _make_healthy_pulse_deps()
    engine = PulseEngine(**deps, dna_expected_hash="hash")
    result = await engine.single_pulse(pulse_number=1)
    assert result.halted is False
    assert result.skipped is False
    assert result.health_status == HealthStatus.GREEN


@pytest.mark.asyncio
async def test_pulse_with_outbox_sensor_green_records_metadata() -> None:
    """outbox_sensor green-reading is recorded in sensor_metadata."""
    deps = _make_healthy_pulse_deps()
    outbox = _make_outbox_sensor("green", count=0)
    engine = PulseEngine(**deps, dna_expected_hash="hash", outbox_sensor=outbox)
    result = await engine.single_pulse(pulse_number=1)
    outbox.read.assert_awaited_once()
    # green outbox does not downgrade the overall status
    assert result.health_status == HealthStatus.GREEN


@pytest.mark.asyncio
async def test_pulse_with_outbox_sensor_red_escalates_status() -> None:
    """outbox_sensor red-reading must escalate the overall status to RED."""
    deps = _make_healthy_pulse_deps()
    outbox = _make_outbox_sensor("red", count=500)
    engine = PulseEngine(**deps, dna_expected_hash="hash", outbox_sensor=outbox)
    result = await engine.single_pulse(pulse_number=1)
    outbox.read.assert_awaited_once()
    assert result.health_status == HealthStatus.RED


@pytest.mark.asyncio
async def test_pulse_outbox_sensor_exception_does_not_break_pulse() -> None:
    """If outbox_sensor.read() raises, pulse continues (logged at WARNING)."""
    deps = _make_healthy_pulse_deps()
    outbox = MagicMock()
    outbox.read = AsyncMock(side_effect=RuntimeError("PG down"))
    engine = PulseEngine(**deps, dna_expected_hash="hash", outbox_sensor=outbox)
    result = await engine.single_pulse(pulse_number=1)
    # exception isolated → yellow contribution → overall YELLOW (worst of
    # green http + yellow outbox = yellow)
    assert result.halted is False
    assert result.skipped is False
    assert result.health_status == HealthStatus.YELLOW


@pytest.mark.asyncio
async def test_pulse_red_backup_persists_driver_headline() -> None:
    deps = _make_healthy_pulse_deps()
    deps["metabolism"].daily_spend = 0.0
    deps["metabolism"]._daily_limit = 10.0
    backup = _make_backup_sensor(
        "red",
        {"age_hours": 113.3, "path": "fly_pg_backup.sql.gz"},
    )
    engine = PulseEngine(**deps, dna_expected_hash="hash", backup_sensor=backup)

    with patch("cell.core.pulse.cell_db.log_pulse", new_callable=AsyncMock) as log_pulse:
        result = await engine.single_pulse(pulse_number=7)

    assert result.health_status == HealthStatus.RED
    assert result.driver_sensors == ["backup"]
    assert result.health_headline is not None
    assert "backup" in result.health_headline
    log_pulse.assert_awaited_once()
    error_message = log_pulse.call_args.kwargs["error_message"]
    assert "backup" in error_message
    assert "113h" in error_message


@pytest.mark.asyncio
async def test_pulse_blocked_alert_human_records_suppressed_alert() -> None:
    deps = _make_healthy_pulse_deps()
    deps["metabolism"].daily_spend = 0.0
    deps["metabolism"]._daily_limit = 10.0
    backup = _make_backup_sensor(
        "red",
        {"age_hours": 113.3, "path": "fly_pg_backup.sql.gz"},
    )
    reasoner = AsyncMock()
    reasoner.think.return_value = SimpleNamespace(
        action="alert_human",
        reason="operator needed",
        confidence=0.9,
        tier_used=0,
        cost_usd=0.0,
    )
    interpreter = DNAInterpreter()
    interpreter.record_action("alert_human")

    engine = PulseEngine(
        **deps,
        dna_expected_hash="hash",
        backup_sensor=backup,
        reasoner=reasoner,
        dna_interpreter=interpreter,
    )

    with (
        patch("cell.core.pulse.cell_db.log_alert", new_callable=AsyncMock) as log_alert,
        patch("cell.core.pulse.cell_db.log_pulse", new_callable=AsyncMock),
    ):
        result = await engine.single_pulse(pulse_number=8)

    assert result.health_status == HealthStatus.RED
    assert result.action_taken is None
    assert result.action_reason is not None
    assert "blocked" in result.action_reason
    suppressed_calls = [
        call.kwargs
        for call in log_alert.await_args_list
        if call.kwargs.get("action") == "alert_suppressed"
    ]
    assert len(suppressed_calls) == 1
    assert suppressed_calls[0]["level"] == "warn"
    assert suppressed_calls[0]["health_status"] == "red"
    assert suppressed_calls[0]["pulse_number"] == 8
    assert "backup" in suppressed_calls[0]["message"]
    assert "113h" in suppressed_calls[0]["message"]
