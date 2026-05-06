"""Tests for RuleBasedThinker — deterministic Thinker with no LLM dependency."""
from __future__ import annotations

import pytest

from cell_core.types import HomeostaticState, Proposal, SensorReading


def _state(stress: float = 0.2, energy: float = 0.8) -> HomeostaticState:
    return HomeostaticState(
        stress_level=stress,
        energy_level=energy,
        arousal=0.3,
        comfort_zone=(0.0, 1.0),
        setpoint_rt_ms=200,
        circadian_phase="awake",
    )


@pytest.mark.asyncio
async def test_protocol_compliance():
    from cell_core.protocols import Thinker
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    assert isinstance(t, Thinker)


@pytest.mark.asyncio
async def test_all_green_proposes_none():
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    readings = [SensorReading(sensor_name="health", status="green")]
    proposal = await t.think(readings, _state(), {})

    assert isinstance(proposal, Proposal)
    assert proposal.action == "none"
    assert proposal.tier_used == 0


@pytest.mark.asyncio
async def test_yellow_proposes_alert_silent():
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    readings = [SensorReading(sensor_name="outbox", status="yellow")]
    proposal = await t.think(readings, _state(), {})

    assert proposal.action == "alert_silent"
    assert proposal.confidence > 0.0


@pytest.mark.asyncio
async def test_red_proposes_alert_human():
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    readings = [SensorReading(sensor_name="health", status="red")]
    proposal = await t.think(readings, _state(), {})

    assert proposal.action == "alert_human"
    # Confidence should be high (≥0.7) — Codex review wanted graduation gates
    # to be reachable from rule-based output.
    assert proposal.confidence >= 0.7


@pytest.mark.asyncio
async def test_red_outbox_proposes_drain_outbox():
    """When the outbox sensor is red, propose a domain-specific action."""
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    readings = [SensorReading(sensor_name="outbox", status="red", value=500)]
    proposal = await t.think(readings, _state(), {})

    assert proposal.action == "drain_outbox"


@pytest.mark.asyncio
async def test_high_stress_overrides_to_alert_human():
    """When stress > 0.8, escalate even on yellow signals."""
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    readings = [SensorReading(sensor_name="outbox", status="yellow")]
    proposal = await t.think(readings, _state(stress=0.9), {})

    assert proposal.action == "alert_human"


@pytest.mark.asyncio
async def test_uses_worst_status_across_sensors():
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    readings = [
        SensorReading(sensor_name="a", status="green"),
        SensorReading(sensor_name="b", status="yellow"),
        SensorReading(sensor_name="c", status="green"),
    ]
    proposal = await t.think(readings, _state(), {})
    assert proposal.action == "alert_silent"


@pytest.mark.asyncio
async def test_proposal_carries_human_readable_reason():
    from cell_core.thinkers.rule_based import RuleBasedThinker

    t = RuleBasedThinker()
    readings = [SensorReading(sensor_name="health", status="red")]
    proposal = await t.think(readings, _state(stress=0.95), {})
    assert "red" in proposal.reason.lower()
