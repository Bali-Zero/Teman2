"""Factory wires a PulseLoop; single pulse runs without exception in pre_natal.

GSCSensor makes real network calls in Sprint 2, so we mock its
blocking fetch to keep the factory test fully offline. The live smoke
test lives in scripts/ (not pytest) and is run manually.
"""
from unittest.mock import patch

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
    """One full pulse end-to-end with GSC mocked to empty rows.

    Expected: thinker sees query_count=0, returns action='none',
    actor never fires, pulse completes with action_taken=None.
    """
    cell = create_seo_cell()

    # Find GSCSensor in wired sensors and mock its blocking fetch
    gsc_sensors = [s for s in cell.sensors if s.name == "gsc"]
    assert len(gsc_sensors) == 1
    gsc = gsc_sensors[0]

    with patch.object(gsc, "_fetch_rows_blocking", return_value=[]):
        # Also mock the credentials path check to avoid yellow-before-fetch
        from pathlib import Path
        import apps.evaluator.seo_cell.sensors.gsc_sensor as gsc_mod
        tmp_path = Path("/tmp/seo_cell_test_fake_creds.json")
        tmp_path.write_text("{}")
        original = gsc_mod.GOOGLE_CREDENTIALS_PATH
        gsc_mod.GOOGLE_CREDENTIALS_PATH = tmp_path
        try:
            result = await cell.single_pulse()
        finally:
            gsc_mod.GOOGLE_CREDENTIALS_PATH = original

    assert result.pulse_number == 1
    assert result.action_taken is None
    assert result.health_status in ("green", "yellow")
