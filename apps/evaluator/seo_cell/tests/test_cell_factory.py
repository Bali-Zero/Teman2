"""Factory wires a PulseLoop; single pulse runs without exception in pre_natal."""
import pytest

from cell_core.pulse import PulseLoop
from apps.evaluator.seo_cell import create_seo_cell


def test_factory_returns_pulse_loop():
    cell = create_seo_cell()
    assert isinstance(cell, PulseLoop)
    assert cell.config.name == "seo-guardian"
    assert len(cell.sensors) == 6


@pytest.mark.asyncio
async def test_single_pulse_completes_in_pre_natal():
    cell = create_seo_cell()
    result = await cell.single_pulse()
    assert result.pulse_number == 1
    # All sensors yellow + thinker no-op → action_taken should be None
    assert result.action_taken is None
    assert result.health_status in ("green", "yellow")
