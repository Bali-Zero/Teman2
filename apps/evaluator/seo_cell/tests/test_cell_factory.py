"""Factory wires a PulseLoop; single pulse runs without exception in pre_natal.

GSCSensor (Sprint 2) and GA4Sensor (Sprint 2b) make real network calls,
so we mock both blocking fetches to keep the factory test fully offline.
Live smoke tests are run manually from a shell, not in pytest.
"""
from pathlib import Path
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
    """One full pulse end-to-end with GSC + GA4 mocked to empty rows.

    Expected: thinker sees query_count=0, returns action='none',
    actor never fires, pulse completes with action_taken=None.
    """
    cell = create_seo_cell()

    gsc = next(s for s in cell.sensors if s.name == "gsc")
    ga4 = next(s for s in cell.sensors if s.name == "ga4")

    # Make credentials-path checks pass
    tmp_creds = Path("/tmp/seo_cell_test_fake_creds.json")
    tmp_creds.write_text("{}")

    import apps.evaluator.seo_cell.sensors.gsc_sensor as gsc_mod
    import apps.evaluator.seo_cell.sensors.ga4_sensor as ga4_mod

    orig_gsc = gsc_mod.GOOGLE_CREDENTIALS_PATH
    orig_ga4 = ga4_mod.GOOGLE_CREDENTIALS_PATH
    gsc_mod.GOOGLE_CREDENTIALS_PATH = tmp_creds
    ga4_mod.GOOGLE_CREDENTIALS_PATH = tmp_creds

    try:
        with patch.object(gsc, "_fetch_rows_blocking", return_value=[]), \
             patch.object(ga4, "_fetch_report_blocking", return_value={"rows": []}):
            result = await cell.single_pulse()
    finally:
        gsc_mod.GOOGLE_CREDENTIALS_PATH = orig_gsc
        ga4_mod.GOOGLE_CREDENTIALS_PATH = orig_ga4

    assert result.pulse_number == 1
    assert result.action_taken is None
    assert result.health_status in ("green", "yellow")
