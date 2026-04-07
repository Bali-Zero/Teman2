"""Tests for PulseEngine + Cortex integration."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from cell.core.pulse import PulseEngine
from cell.fast.health_triage import HealthStatus


@pytest.fixture
def minimal_engine():
    """Minimal PulseEngine with GREEN health (no reasoner, no cortex)."""
    dna = MagicMock()
    dna.verify_integrity = MagicMock(return_value=True)
    safety = AsyncMock()
    safety.check = AsyncMock(return_value=MagicMock(can_proceed=True))
    health = AsyncMock()
    health.read = AsyncMock(return_value=MagicMock(
        reachable=True, status_code=200, response_time_seconds=0.05, error=None,
    ))
    return PulseEngine(
        dna_loader=dna,
        safety_gate=safety,
        health_sensor=health,
        metabolism=MagicMock(daily_spend=0.0, _daily_limit=10.0),
    )


class TestPulseWithoutCortex:
    @pytest.mark.asyncio
    async def test_pulse_works_without_cortex(self, minimal_engine: PulseEngine) -> None:
        """PulseEngine runs fine with cortex=None (default)."""
        result = await minimal_engine.single_pulse(pulse_number=1)
        assert result.halted is False
        assert result.skipped is False
        assert result.health_status == HealthStatus.GREEN

    def test_cortex_none_is_default(self, minimal_engine: PulseEngine) -> None:
        """cortex defaults to None in PulseEngine constructor."""
        assert minimal_engine._cortex is None


class TestPulseWithCortex:
    @pytest.mark.asyncio
    async def test_cortex_before_reasoning_called(self) -> None:
        """When cortex is provided, before_reasoning is called during pulse."""
        dna = MagicMock()
        dna.verify_integrity = MagicMock(return_value=True)
        safety = AsyncMock()
        safety.check = AsyncMock(return_value=MagicMock(can_proceed=True))
        health = AsyncMock()
        health.read = AsyncMock(return_value=MagicMock(
            reachable=True, status_code=200, response_time_seconds=0.05, error=None,
        ))
        cortex = AsyncMock()
        cortex.before_reasoning = AsyncMock(return_value="SKILL: test_skill")
        cortex.after_action = AsyncMock()
        cortex.during_idle = AsyncMock()

        engine = PulseEngine(
            dna_loader=dna,
            safety_gate=safety,
            health_sensor=health,
            metabolism=MagicMock(daily_spend=0.0, _daily_limit=10.0),
            cortex=cortex,
        )
        result = await engine.single_pulse(pulse_number=1)
        assert result.halted is False
        cortex.before_reasoning.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cortex_hook_failure_does_not_crash(self) -> None:
        """If before_reasoning raises, the pulse still completes."""
        dna = MagicMock()
        dna.verify_integrity = MagicMock(return_value=True)
        safety = AsyncMock()
        safety.check = AsyncMock(return_value=MagicMock(can_proceed=True))
        health = AsyncMock()
        health.read = AsyncMock(return_value=MagicMock(
            reachable=True, status_code=200, response_time_seconds=0.05, error=None,
        ))
        cortex = AsyncMock()
        cortex.before_reasoning = AsyncMock(side_effect=RuntimeError("boom"))
        cortex.after_action = AsyncMock()
        cortex.during_idle = AsyncMock()

        engine = PulseEngine(
            dna_loader=dna,
            safety_gate=safety,
            health_sensor=health,
            metabolism=MagicMock(daily_spend=0.0, _daily_limit=10.0),
            cortex=cortex,
        )
        result = await engine.single_pulse(pulse_number=1)
        # Pulse still completes despite cortex failure
        assert result.halted is False
        assert result.health_status == HealthStatus.GREEN

    @pytest.mark.asyncio
    async def test_during_idle_called_when_green(self) -> None:
        """During idle hook is called when health is GREEN."""
        dna = MagicMock()
        dna.verify_integrity = MagicMock(return_value=True)
        safety = AsyncMock()
        safety.check = AsyncMock(return_value=MagicMock(can_proceed=True))
        health = AsyncMock()
        health.read = AsyncMock(return_value=MagicMock(
            reachable=True, status_code=200, response_time_seconds=0.05, error=None,
        ))
        cortex = AsyncMock()
        cortex.before_reasoning = AsyncMock(return_value="")
        cortex.after_action = AsyncMock()
        cortex.during_idle = AsyncMock()

        engine = PulseEngine(
            dna_loader=dna,
            safety_gate=safety,
            health_sensor=health,
            metabolism=MagicMock(daily_spend=0.0, _daily_limit=10.0),
            cortex=cortex,
        )
        result = await engine.single_pulse(pulse_number=1)
        assert result.health_status == HealthStatus.GREEN
        cortex.during_idle.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_during_idle_not_called_when_yellow(self) -> None:
        """During idle hook is NOT called when health is YELLOW."""
        dna = MagicMock()
        dna.verify_integrity = MagicMock(return_value=True)
        safety = AsyncMock()
        safety.check = AsyncMock(return_value=MagicMock(can_proceed=True))
        health = AsyncMock()
        health.read = AsyncMock(return_value=MagicMock(
            reachable=True, status_code=500, response_time_seconds=0.2, error=None,
        ))
        cortex = AsyncMock()
        cortex.before_reasoning = AsyncMock(return_value="")
        cortex.after_action = AsyncMock()
        cortex.during_idle = AsyncMock()

        engine = PulseEngine(
            dna_loader=dna,
            safety_gate=safety,
            health_sensor=health,
            metabolism=MagicMock(daily_spend=0.0, _daily_limit=10.0),
            cortex=cortex,
        )
        result = await engine.single_pulse(pulse_number=1)
        assert result.health_status == HealthStatus.YELLOW
        cortex.during_idle.assert_not_awaited()
