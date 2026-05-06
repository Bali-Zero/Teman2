"""Tests for OllamaAwareThinker — graceful Ollama wrapper."""
from __future__ import annotations

import asyncio

import pytest

from cell_core.types import HomeostaticState, Proposal, SensorReading


def _state() -> HomeostaticState:
    return HomeostaticState(
        stress_level=0.2,
        energy_level=0.8,
        arousal=0.3,
        comfort_zone=(0.0, 1.0),
        setpoint_rt_ms=200,
        circadian_phase="awake",
    )


class _RecordingThinker:
    """Thinker that records call count and emits a fixed proposal."""

    name = "primary"

    def __init__(self, action: str = "magic", confidence: float = 0.95):
        self.calls = 0
        self._action = action
        self._confidence = confidence

    async def think(self, readings, state, memory_context):
        self.calls += 1
        return Proposal(
            action=self._action,
            reason="primary",
            confidence=self._confidence,
            tier_used=2,
        )


class _SlowThinker:
    """Thinker that sleeps longer than the timeout."""

    name = "slow"

    async def think(self, readings, state, memory_context):
        await asyncio.sleep(5.0)
        return Proposal(action="never", reason="slow", confidence=0.0, tier_used=2)


class _RaisingThinker:
    name = "raising"

    async def think(self, readings, state, memory_context):
        raise ConnectionError("ollama is down")


@pytest.mark.asyncio
async def test_protocol_compliance():
    from cell_core.protocols import Thinker
    from cell_core.thinkers.ollama_aware import OllamaAwareThinker

    t = OllamaAwareThinker(primary=None)
    assert isinstance(t, Thinker)


@pytest.mark.asyncio
async def test_primary_used_when_responsive():
    from cell_core.thinkers.ollama_aware import OllamaAwareThinker

    primary = _RecordingThinker(action="restart_service")
    t = OllamaAwareThinker(primary=primary)
    readings = [SensorReading(sensor_name="health", status="red")]
    proposal = await t.think(readings, _state(), {})

    assert proposal.action == "restart_service"
    assert primary.calls == 1


@pytest.mark.asyncio
async def test_fallback_when_primary_none():
    from cell_core.thinkers.ollama_aware import OllamaAwareThinker

    t = OllamaAwareThinker(primary=None)
    readings = [SensorReading(sensor_name="health", status="red")]
    proposal = await t.think(readings, _state(), {})

    # Default fallback is RuleBasedThinker → red without specific domain
    # mapping yields "alert_human".
    assert proposal.action == "alert_human"


@pytest.mark.asyncio
async def test_fallback_on_timeout():
    from cell_core.thinkers.ollama_aware import OllamaAwareThinker

    t = OllamaAwareThinker(primary=_SlowThinker(), timeout_seconds=0.05)
    readings = [SensorReading(sensor_name="health", status="red")]
    proposal = await t.think(readings, _state(), {})

    # Should land in the fallback path.
    assert proposal.action != "never"
    assert proposal.tier_used == 0


@pytest.mark.asyncio
async def test_fallback_on_exception():
    from cell_core.thinkers.ollama_aware import OllamaAwareThinker

    t = OllamaAwareThinker(primary=_RaisingThinker(), timeout_seconds=2.0)
    readings = [SensorReading(sensor_name="health", status="red")]
    proposal = await t.think(readings, _state(), {})

    # Should land in the fallback path.
    assert proposal.tier_used == 0


@pytest.mark.asyncio
async def test_primary_call_counts_only_once():
    from cell_core.thinkers.ollama_aware import OllamaAwareThinker

    primary = _RecordingThinker()
    t = OllamaAwareThinker(primary=primary)
    readings = [SensorReading(sensor_name="health", status="green")]
    await t.think(readings, _state(), {})
    await t.think(readings, _state(), {})

    assert primary.calls == 2
