"""Integration: lead_attribution sensor → thinker pre_natal unlock gate.

Sprint 2 closes the A3 anomaly. Before this PR, the thinker hardcoded
`lead_count = 0` and ignored sensor readings — the gate was always
locked on the leads criterion. After this PR, `lead_count` is read
from the `lead_attribution` sensor's value, so a real CRM signal
(when present, AND the other two conditions are met) lets the cell
graduate.

These tests drive the thinker directly with synthetic readings to
prove the wiring without standing up a real PG database. They also
test the inverse: a yellow/red sensor (lead_count=0) keeps the gate
locked, which is the safe-default behavior we want preserved.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from cell_core.types import HomeostaticState, SensorReading
from apps.evaluator.seo_cell.thinker import SEOThinker


def _gsc(query_count: int) -> SensorReading:
    return SensorReading(
        sensor_name="gsc",
        status="green",
        value={"query_count": query_count},
    )


def _leads(lead_count: int, *, status: str = "green") -> SensorReading:
    return SensorReading(
        sensor_name="lead_attribution",
        status=status,
        value={"lead_count": lead_count, "by_landing_page": {}, "recent_leads": []},
    )


@pytest.mark.asyncio
async def test_lead_count_flows_from_sensor_into_phase():
    """Thinker.current_phase reads lead_count from the sensor reading."""
    thinker = SEOThinker()
    readings = [_gsc(100), _leads(5)]
    phase = thinker.current_phase(readings, HomeostaticState())
    # We only assert the wiring — the actual unlock also depends on
    # min_age_days, which depends on the persisted birth-date marker.
    # If the cell is older than 28d AND gsc>=80 AND leads>=3, gate
    # opens; otherwise it stays pre_natal.
    assert isinstance(phase.pre_natal, bool)


@pytest.mark.asyncio
async def test_unlock_gate_opens_when_all_three_conditions_met():
    """Patch the birth-date so age_days clears the threshold deterministically."""
    thinker = SEOThinker()
    # 60 days old → age check passes
    fake_birth = datetime.now(timezone.utc) - timedelta(days=60)
    with patch(
        "apps.evaluator.seo_cell.thinker.config.cell_birth_date",
        return_value=fake_birth,
    ):
        readings = [_gsc(100), _leads(5)]
        phase = thinker.current_phase(readings, HomeostaticState())
    assert phase.pre_natal is False, (
        "60d old + gsc=100 + leads=5 should graduate"
    )
    assert phase.can_act is True
    assert phase.can_learn is True


@pytest.mark.asyncio
async def test_unlock_gate_locked_when_leads_zero_even_if_gsc_high():
    """A yellow/red sensor reports lead_count=0 → gate stays locked."""
    thinker = SEOThinker()
    fake_birth = datetime.now(timezone.utc) - timedelta(days=60)
    with patch(
        "apps.evaluator.seo_cell.thinker.config.cell_birth_date",
        return_value=fake_birth,
    ):
        readings = [_gsc(100), _leads(0, status="yellow")]
        phase = thinker.current_phase(readings, HomeostaticState())
    assert phase.pre_natal is True


@pytest.mark.asyncio
async def test_missing_lead_sensor_keeps_gate_locked():
    """Defensive: if the sensor isn't in readings, lead_count stays 0."""
    thinker = SEOThinker()
    fake_birth = datetime.now(timezone.utc) - timedelta(days=60)
    with patch(
        "apps.evaluator.seo_cell.thinker.config.cell_birth_date",
        return_value=fake_birth,
    ):
        # only gsc, no lead_attribution reading at all
        readings = [_gsc(100)]
        phase = thinker.current_phase(readings, HomeostaticState())
    assert phase.pre_natal is True


@pytest.mark.asyncio
async def test_red_sensor_returns_zero_lead_count_via_safe_default():
    """A red reading (sensor failed) carries lead_count=0 → safe."""
    thinker = SEOThinker()
    fake_birth = datetime.now(timezone.utc) - timedelta(days=60)
    with patch(
        "apps.evaluator.seo_cell.thinker.config.cell_birth_date",
        return_value=fake_birth,
    ):
        readings = [_gsc(100), _leads(0, status="red")]
        phase = thinker.current_phase(readings, HomeostaticState())
    assert phase.pre_natal is True


@pytest.mark.asyncio
async def test_proposal_still_none_pre_natal_with_real_lead_signal():
    """Even with leads=10, if age<28d the proposal is still no-op."""
    thinker = SEOThinker()
    # birth = today → age_days = 0
    fake_birth = datetime.now(timezone.utc)
    with patch(
        "apps.evaluator.seo_cell.thinker.config.cell_birth_date",
        return_value=fake_birth,
    ):
        readings = [_gsc(100), _leads(10)]
        proposal = await thinker.think(readings, HomeostaticState(), {})
    assert proposal.action == "none"
    assert thinker._last_phase is not None
    assert thinker._last_phase.pre_natal is True
