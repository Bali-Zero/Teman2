"""
PredictiveEngine must read per-category urgent thresholds from system_settings,
falling back to the hardcoded default (7 days) when key missing.
"""
from __future__ import annotations

import pytest
import asyncpg

from backend.services.compliance.predictive_engine import (
    PredictiveComplianceEngine,
    _load_urgent_threshold,
)


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_load_urgent_threshold_from_system_settings(db_tx: asyncpg.Connection) -> None:
    await db_tx.execute(
        "INSERT INTO system_settings (key, value) VALUES "
        "('compliance_alert_threshold_urgent_visa_expiry','5') "
        "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
    )
    result = await _load_urgent_threshold(db_tx, "visa_expiry")
    assert result == 5


@pytest.mark.asyncio
async def test_load_urgent_threshold_default_when_missing(db_tx: asyncpg.Connection) -> None:
    await db_tx.execute(
        "DELETE FROM system_settings WHERE key='compliance_alert_threshold_urgent_unknown_category'",
    )
    result = await _load_urgent_threshold(db_tx, "unknown_category")
    assert result == 7  # default from severity_calculator.ALERT_THRESHOLDS[URGENT]
