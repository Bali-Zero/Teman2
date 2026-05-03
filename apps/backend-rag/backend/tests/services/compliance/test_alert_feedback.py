"""
AlertFeedback.retrain adjusts thresholds based on precision.

Rules (decision #2):
  precision < 0.6 AND sample_size >= 20 → threshold += 1 (fire later, fewer FP)
  precision > 0.9 AND sample_size >= 50 → threshold -= 1 (fire earlier, catch more)
  else no change
  clamp to [1, 30]

Kill-switch: system_settings.compliance_alert_autotune_enabled must be 'true'.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
import asyncpg

from backend.services.compliance.alert_feedback import AlertFeedback


pytestmark = pytest.mark.integration


async def _enable_autotune(conn: asyncpg.Connection, enabled: bool = True) -> None:
    await conn.execute(
        "INSERT INTO system_settings (key, value) VALUES "
        "('compliance_alert_autotune_enabled', $1) "
        "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
        "true" if enabled else "false",
    )


async def _seed_outcomes(
    conn: asyncpg.Connection,
    client_id: int,
    category: str,
    acted: int,
    dismissed: int,
    expired: int = 0,
) -> None:
    """Insert compliance_alerts + alert_outcomes rows with actioned_at = NOW()."""
    for _ in range(acted):
        aid = f"a_{uuid4().hex[:8]}"
        await conn.execute(
            "INSERT INTO compliance_alerts (alert_id, client_id, category, severity, status, deadline, days_until, dedup_key) "
            "VALUES ($1,$2,$3,'urgent','acknowledged',$4,7,$5)",
            aid,
            client_id,
            category,
            date.today() + timedelta(days=7),
            f"{category}:{client_id}:{aid}",
        )
        await conn.execute(
            "INSERT INTO alert_outcomes (alert_id, outcome) VALUES ($1,'acted')",
            aid,
        )
    for _ in range(dismissed):
        aid = f"d_{uuid4().hex[:8]}"
        await conn.execute(
            "INSERT INTO compliance_alerts (alert_id, client_id, category, severity, status, deadline, days_until, dedup_key) "
            "VALUES ($1,$2,$3,'urgent','acknowledged',$4,7,$5)",
            aid,
            client_id,
            category,
            date.today() + timedelta(days=7),
            f"{category}:{client_id}:{aid}",
        )
        await conn.execute(
            "INSERT INTO alert_outcomes (alert_id, outcome) VALUES ($1,'dismissed')",
            aid,
        )
    for _ in range(expired):
        aid = f"e_{uuid4().hex[:8]}"
        await conn.execute(
            "INSERT INTO compliance_alerts (alert_id, client_id, category, severity, status, deadline, days_until, dedup_key) "
            "VALUES ($1,$2,$3,'urgent','expired',$4,7,$5)",
            aid,
            client_id,
            category,
            date.today() - timedelta(days=1),
            f"{category}:{client_id}:{aid}",
        )
        await conn.execute(
            "INSERT INTO alert_outcomes (alert_id, outcome) VALUES ($1,'expired')",
            aid,
        )


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retrain_disabled_by_default(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """When autotune is disabled, retrain returns autotune_disabled and changes nothing."""
    await _enable_autotune(db_tx, False)
    await _seed_outcomes(db_tx, sample_client["id"], "visa_expiry", acted=1, dismissed=10)
    fb = AlertFeedback(connection=db_tx)
    result = await fb.retrain()
    assert result["changed"] == []
    assert result["reason"] == "autotune_disabled"


@pytest.mark.asyncio
async def test_low_precision_widens_threshold(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """p < 0.6 and n >= 20 → threshold += 1."""
    await _enable_autotune(db_tx)
    await db_tx.execute(
        "INSERT INTO system_settings (key, value) VALUES "
        "('compliance_alert_threshold_urgent_visa_expiry','7') "
        "ON CONFLICT (key) DO UPDATE SET value='7'",
    )
    # precision = 5 / (5+20) = 0.20, n = 25 → triggers UP rule
    await _seed_outcomes(db_tx, sample_client["id"], "visa_expiry", acted=5, dismissed=20)
    fb = AlertFeedback(connection=db_tx)
    result = await fb.retrain()
    new = await db_tx.fetchval(
        "SELECT value FROM system_settings WHERE key='compliance_alert_threshold_urgent_visa_expiry'",
    )
    assert int(new) == 8  # 7 + 1
    assert ("visa_expiry", 7, 8) in [
        (c["category"], c["old"], c["new"]) for c in result["changed"]
    ]


@pytest.mark.asyncio
async def test_high_precision_tightens_threshold(
    db_tx: asyncpg.Connection, sample_client: dict
) -> None:
    """p > 0.9 and n >= 50 → threshold -= 1."""
    await _enable_autotune(db_tx)
    await db_tx.execute(
        "INSERT INTO system_settings (key, value) VALUES "
        "('compliance_alert_threshold_urgent_visa_expiry','7') "
        "ON CONFLICT (key) DO UPDATE SET value='7'",
    )
    # precision = 55 / (55+2) ≈ 0.965, n = 57 → triggers DOWN rule
    await _seed_outcomes(db_tx, sample_client["id"], "visa_expiry", acted=55, dismissed=2)
    fb = AlertFeedback(connection=db_tx)
    result = await fb.retrain()
    new = await db_tx.fetchval(
        "SELECT value FROM system_settings WHERE key='compliance_alert_threshold_urgent_visa_expiry'",
    )
    assert int(new) == 6  # 7 - 1


@pytest.mark.asyncio
async def test_clamp_min_1(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """Threshold cannot go below THRESHOLD_MIN = 1."""
    await _enable_autotune(db_tx)
    await db_tx.execute(
        "INSERT INTO system_settings (key, value) VALUES "
        "('compliance_alert_threshold_urgent_visa_expiry','1') "
        "ON CONFLICT (key) DO UPDATE SET value='1'",
    )
    await _seed_outcomes(db_tx, sample_client["id"], "visa_expiry", acted=55, dismissed=2)
    fb = AlertFeedback(connection=db_tx)
    await fb.retrain()
    new = await db_tx.fetchval(
        "SELECT value FROM system_settings WHERE key='compliance_alert_threshold_urgent_visa_expiry'",
    )
    assert int(new) == 1  # floor — should NOT go to 0


@pytest.mark.asyncio
async def test_small_sample_size_no_change(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """Sample too small to trigger either rule → no change."""
    await _enable_autotune(db_tx)
    await db_tx.execute(
        "INSERT INTO system_settings (key, value) VALUES "
        "('compliance_alert_threshold_urgent_visa_expiry','7') "
        "ON CONFLICT (key) DO UPDATE SET value='7'",
    )
    # precision = 2/(2+8) = 0.2 but n=10 < MIN_SAMPLES_UP=20 → no change
    await _seed_outcomes(db_tx, sample_client["id"], "visa_expiry", acted=2, dismissed=8)
    fb = AlertFeedback(connection=db_tx)
    result = await fb.retrain()
    new = await db_tx.fetchval(
        "SELECT value FROM system_settings WHERE key='compliance_alert_threshold_urgent_visa_expiry'",
    )
    assert int(new) == 7  # unchanged
    assert result["changed"] == []
    assert result["reason"] == "no_change"
