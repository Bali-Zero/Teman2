"""
classify_client_risk and get_weighted_revenue (decision #5).

Bands (fixed weights):
  green  → 1.0  (no active alerts, no stale practices)
  yellow → 0.8  (WARNING-level alerts)
  orange → 0.5  (URGENT alerts OR overdue practices <30d)
  red    → 0.2  (CRITICAL alerts OR overdue practices ≥30d)
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
import asyncpg

from backend.services.compliance.revenue_estimator import (
    classify_client_risk,
    get_weighted_revenue,
    RiskBand,
)


pytestmark = pytest.mark.integration


async def _mk_alert(conn: asyncpg.Connection, client_id: int, severity: str) -> None:
    aid = f"a_{uuid4().hex[:8]}"
    await conn.execute(
        "INSERT INTO compliance_alerts (alert_id, client_id, category, severity, status, "
        "deadline, days_until, dedup_key) "
        "VALUES ($1,$2,'visa_expiry',$3,'pending',$4,7,$5)",
        aid, client_id, severity, date.today() + timedelta(days=7),
        f"visa:{client_id}:{aid}",
    )


@pytest.mark.asyncio
async def test_no_alerts_returns_green(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    band = await classify_client_risk(db_tx, sample_client["id"])
    assert band == RiskBand.GREEN


@pytest.mark.asyncio
async def test_warning_alert_yields_yellow(
    db_tx: asyncpg.Connection, sample_client: dict,
) -> None:
    await _mk_alert(db_tx, sample_client["id"], "warning")
    band = await classify_client_risk(db_tx, sample_client["id"])
    assert band == RiskBand.YELLOW


@pytest.mark.asyncio
async def test_urgent_alert_yields_orange(
    db_tx: asyncpg.Connection, sample_client: dict,
) -> None:
    await _mk_alert(db_tx, sample_client["id"], "urgent")
    band = await classify_client_risk(db_tx, sample_client["id"])
    assert band == RiskBand.ORANGE


@pytest.mark.asyncio
async def test_critical_alert_yields_red(
    db_tx: asyncpg.Connection, sample_client: dict,
) -> None:
    await _mk_alert(db_tx, sample_client["id"], "critical")
    band = await classify_client_risk(db_tx, sample_client["id"])
    assert band == RiskBand.RED


@pytest.mark.asyncio
async def test_highest_severity_wins(
    db_tx: asyncpg.Connection, sample_client: dict,
) -> None:
    await _mk_alert(db_tx, sample_client["id"], "warning")
    await _mk_alert(db_tx, sample_client["id"], "critical")
    band = await classify_client_risk(db_tx, sample_client["id"])
    assert band == RiskBand.RED


@pytest.mark.asyncio
async def test_weighted_revenue_multiplies_by_band(
    db_tx: asyncpg.Connection, sample_client: dict,
) -> None:
    await _mk_alert(db_tx, sample_client["id"], "urgent")
    weighted = await get_weighted_revenue(
        db_tx, sample_client["id"], expected_idr=10_000_000,
    )
    assert weighted == int(10_000_000 * 0.5)  # orange → 0.5
