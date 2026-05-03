"""
alert_metrics: precision/recall/F1 per category from alert_outcomes.

precision = acted / (acted + dismissed)   (ignore expired — user never saw)
recall    = acted / (acted + expired)     (expired counts as "missed")
f1        = 2*p*r / (p+r)
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
import asyncpg

from backend.services.compliance.alert_metrics import (
    CategoryMetrics,
    compute_metrics,
    compute_metrics_all,
)


pytestmark = pytest.mark.integration


async def _mk_alert(
    conn: asyncpg.Connection,
    client_id: int,
    category: str,
    status: str,
) -> str:
    """Insert a minimal compliance_alerts row and return its alert_id."""
    aid = f"a_{uuid4().hex[:8]}"
    await conn.execute(
        """
        INSERT INTO compliance_alerts (
          alert_id, client_id, category, severity, status,
          deadline, days_until, dedup_key
        ) VALUES ($1,$2,$3,'urgent',$4,$5,7,$6)
        """,
        aid,
        client_id,
        category,
        status,
        date.today() + timedelta(days=7),
        f"{category}:{client_id}:{aid}",
    )
    return aid


async def _mk_outcome(
    conn: asyncpg.Connection,
    alert_id: str,
    outcome: str,
) -> None:
    """Insert an alert_outcomes row."""
    await conn.execute(
        "INSERT INTO alert_outcomes (alert_id, outcome) VALUES ($1, $2)",
        alert_id,
        outcome,
    )


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_returns_zero_metrics(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """Category with no outcomes returns zero-valued metrics."""
    result = await compute_metrics(db_tx, window_days=90, category="visa_expiry")
    assert result.sample_size == 0
    assert result.precision == 0.0
    assert result.recall == 0.0
    assert result.f1 == 0.0


@pytest.mark.asyncio
async def test_precision_all_acted(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """All outcomes are 'acted' → precision == 1.0."""
    cid = sample_client["id"]
    for _ in range(5):
        aid = await _mk_alert(db_tx, cid, "visa_expiry", "acknowledged")
        await _mk_outcome(db_tx, aid, "acted")
    m = await compute_metrics(db_tx, window_days=90, category="visa_expiry")
    assert m.precision == 1.0


@pytest.mark.asyncio
async def test_mixed_gives_expected_precision(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """3 acted + 2 dismissed → precision == 0.6."""
    cid = sample_client["id"]
    for _ in range(3):
        aid = await _mk_alert(db_tx, cid, "visa_expiry", "acknowledged")
        await _mk_outcome(db_tx, aid, "acted")
    for _ in range(2):
        aid = await _mk_alert(db_tx, cid, "visa_expiry", "acknowledged")
        await _mk_outcome(db_tx, aid, "dismissed")
    m = await compute_metrics(db_tx, window_days=90, category="visa_expiry")
    assert m.precision == pytest.approx(0.6, rel=0.01)


@pytest.mark.asyncio
async def test_expired_counts_as_missed(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """1 expired + 1 acted → recall == 0.5."""
    cid = sample_client["id"]
    aid = await _mk_alert(db_tx, cid, "visa_expiry", "expired")
    await _mk_outcome(db_tx, aid, "expired")
    aid2 = await _mk_alert(db_tx, cid, "visa_expiry", "resolved")
    await _mk_outcome(db_tx, aid2, "acted")
    m = await compute_metrics(db_tx, window_days=90, category="visa_expiry")
    assert m.recall == pytest.approx(0.5, rel=0.01)


@pytest.mark.asyncio
async def test_category_filter_isolates_visa(db_tx: asyncpg.Connection, sample_client: dict) -> None:
    """Categories are independent — visa and tax don't bleed into each other."""
    cid = sample_client["id"]
    aid1 = await _mk_alert(db_tx, cid, "visa_expiry", "acknowledged")
    await _mk_outcome(db_tx, aid1, "acted")
    aid2 = await _mk_alert(db_tx, cid, "tax_filing", "acknowledged")
    await _mk_outcome(db_tx, aid2, "dismissed")

    visa = await compute_metrics(db_tx, window_days=90, category="visa_expiry")
    tax = await compute_metrics(db_tx, window_days=90, category="tax_filing")
    assert visa.precision == 1.0
    assert tax.precision == 0.0


@pytest.mark.asyncio
async def test_compute_metrics_all_covers_all_categories(
    db_tx: asyncpg.Connection, sample_client: dict
) -> None:
    """compute_metrics_all returns entries for every category with outcomes."""
    cid = sample_client["id"]
    for cat in ("visa_expiry", "tax_filing", "lkpm_deadline"):
        aid = await _mk_alert(db_tx, cid, cat, "acknowledged")
        await _mk_outcome(db_tx, aid, "acted")

    all_m = await compute_metrics_all(db_tx, window_days=90)
    assert "visa_expiry" in all_m
    assert "tax_filing" in all_m
    assert "lkpm_deadline" in all_m
    assert all(v.precision == 1.0 for v in all_m.values())
