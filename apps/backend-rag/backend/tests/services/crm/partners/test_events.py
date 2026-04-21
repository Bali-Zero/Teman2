# tests/services/crm/partners/test_events.py
"""
EventBus handler tests for the partners module (Task 6).

These tests exercise handle_practice_status_changed and
register_partner_handlers.  Because the real get_pool() would require a
running application pool, we monkey-patch get_pool to return a FakePool that
wraps the test's db_conn fixture — routing all pool.acquire() calls through
the same connection used by the test.
"""
import contextlib
from decimal import Decimal

import pytest

from backend.services.crm.partners.events import (
    PARTNER_COMMISSION_CHANGED,
    handle_practice_status_changed,
    register_partner_handlers,
)
from backend.services.events.event_bus import EventBus


# ---------------------------------------------------------------------------
# FakePool helper
# ---------------------------------------------------------------------------

def _make_fake_get_pool(db_conn):
    """Return an async get_pool() replacement that yields db_conn."""

    class _FakePool:
        def acquire(self):
            @contextlib.asynccontextmanager
            async def _cm():
                yield db_conn

            return _cm()

    async def fake_get_pool():
        return _FakePool()

    return fake_get_pool


# ---------------------------------------------------------------------------
# 1. Noop when process is not completed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_practice_status_changed_noop_if_not_completed(
    db_conn,
    partner_factory,
    practice_factory,
    monkeypatch,
):
    """Handler must be silent (no commission) for non-completed statuses."""
    import backend.services.crm.partners.events as _events_mod

    proc_id = await practice_factory(status="in_progress", payment_status="pending")
    monkeypatch.setattr(_events_mod, "get_pool", _make_fake_get_pool(db_conn))

    payload = {"practice_id": str(proc_id), "new_status": "in_progress"}
    await handle_practice_status_changed(payload)

    row = await db_conn.fetchrow("SELECT COUNT(*) AS n FROM partner_commissions")
    assert row["n"] == 0


# ---------------------------------------------------------------------------
# 2. Completed + paid → accrual row created
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_practice_status_changed_creates_accrual(
    db_conn,
    partner_factory,
    practice_factory,
    referral_factory,
    monkeypatch,
):
    """Handler must create a commission when a paid practice completes."""
    import backend.services.crm.partners.events as _events_mod

    p = await partner_factory(tax_withholding_category="exempt")
    proc_id = await practice_factory(
        total_invoiced_idr=Decimal("5000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p, practice_id=proc_id)
    monkeypatch.setattr(_events_mod, "get_pool", _make_fake_get_pool(db_conn))

    payload = {"practice_id": str(proc_id), "new_status": "completed"}
    await handle_practice_status_changed(payload)

    row = await db_conn.fetchrow(
        "SELECT COUNT(*) AS n FROM partner_commissions WHERE partner_id = $1",
        p,
    )
    assert row["n"] == 1


# ---------------------------------------------------------------------------
# 3. register_partner_handlers wires the bus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_partner_handlers_subscribes_to_bus():
    """register_partner_handlers must subscribe to practice.status_changed."""
    # EventBus requires db_dsn for full init, but subscribe() only touches
    # the in-process _subscribers dict — instantiate with a sentinel DSN.
    bus = EventBus(db_dsn="postgresql://test:test@localhost/test")
    register_partner_handlers(bus)
    assert "practice.status_changed" in bus._subscribers
    handlers = bus._subscribers["practice.status_changed"]
    assert any(h.__name__ == "handle_practice_status_changed" for h in handlers)
