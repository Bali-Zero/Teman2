# tests/services/crm/partners/test_commission_engine.py
"""
Commission engine integration tests.

All tests use the db_conn fixture (real asyncpg connection with partner
tables + system_settings + extended processes stub).
See conftest.py for fixture definitions — Task 5 pre-flight outcome (c):
processes table did not exist in the live DB, so the 4 required columns
(status, payment_status, total_invoiced_idr, completed_at) were added to
the conftest DDL stub.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.services.crm.partners.commission_engine import CommissionEngine


@pytest.fixture
async def engine(db_conn):
    return CommissionEngine(db_conn)


# ---------------------------------------------------------------------------
# 1. Accrual creates row with correct math and cooling-off timestamp
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accrue_creates_accrued_row_with_cooling_off(
    engine, partner_factory, process_factory, referral_factory
):
    p = await partner_factory(
        default_commission_value=Decimal("10.0"),
        tax_withholding_category="pph23",
    )
    proc = await process_factory(
        total_invoiced_idr=Decimal("10000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p.id, process_id=proc.id)

    await engine.accrue_from_process(proc.id, p.id)

    commissions = await engine.repo.list_commissions_for_partner(p.id)
    assert len(commissions) == 1
    c = commissions[0]
    assert c.status == "accrued"
    assert c.base_amount_idr == Decimal("10000000")
    assert c.gross_amount_idr == Decimal("1000000")
    assert c.withholding_category == "pph23"
    assert c.withholding_rate == Decimal("2.0")
    assert c.withholding_amount_idr == Decimal("20000")
    assert c.net_amount_idr == Decimal("980000")
    assert c.eligible_for_approval_at > c.accrued_at


# ---------------------------------------------------------------------------
# 2. Accrual is idempotent via idempotency_key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accrue_is_idempotent_via_key(
    engine, partner_factory, process_factory, referral_factory
):
    p = await partner_factory()
    proc = await process_factory(status="completed", payment_status="paid")
    await referral_factory(partner_id=p.id, process_id=proc.id)

    await engine.accrue_from_process(proc.id, p.id)
    await engine.accrue_from_process(proc.id, p.id)  # second call: no-op

    commissions = await engine.repo.list_commissions_for_partner(p.id)
    assert len(commissions) == 1


# ---------------------------------------------------------------------------
# 3. approve() is blocked before cooling-off window expires
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_blocked_before_cooling_off(
    engine, partner_factory, process_factory, referral_factory, admin
):
    p = await partner_factory(tax_withholding_category="exempt")
    proc = await process_factory(status="completed", payment_status="paid")
    await referral_factory(partner_id=p.id, process_id=proc.id)

    await engine.accrue_from_process(proc.id, p.id)
    c = (await engine.repo.list_commissions_for_partner(p.id))[0]

    with pytest.raises(ValueError, match="cooling-off"):
        await engine.approve(c.id, actor=admin)


# ---------------------------------------------------------------------------
# 4. approve() is blocked when withholding_category is 'tbd'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_blocked_when_withholding_tbd(
    engine, partner_factory, process_factory, referral_factory, admin, db_conn
):
    p = await partner_factory(tax_withholding_category="tbd")
    proc = await process_factory(status="completed", payment_status="paid")
    await referral_factory(partner_id=p.id, process_id=proc.id)

    await engine.accrue_from_process(proc.id, p.id)
    c = (await engine.repo.list_commissions_for_partner(p.id))[0]

    # Simulate cooling-off elapsed
    await db_conn.execute(
        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' "
        "WHERE id = $1",
        c.id,
    )
    with pytest.raises(ValueError, match="withholding.*tbd"):
        await engine.approve(c.id, actor=admin)


# ---------------------------------------------------------------------------
# 5. Flat commission type: gross = fixed amount, no percentage of base
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flat_commission_type(
    engine, partner_factory, process_factory, referral_factory
):
    p = await partner_factory(
        default_commission_type="flat",
        default_commission_value=Decimal("500000"),
        tax_withholding_category="exempt",
    )
    proc = await process_factory(
        total_invoiced_idr=Decimal("10000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p.id, process_id=proc.id)

    await engine.accrue_from_process(proc.id, p.id)
    c = (await engine.repo.list_commissions_for_partner(p.id))[0]

    assert c.gross_amount_idr == Decimal("500000")
    assert c.withholding_amount_idr == Decimal("0")
    assert c.net_amount_idr == Decimal("500000")


# ---------------------------------------------------------------------------
# 6. clawback() inserts negative row with FK to original
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clawback_inserts_negative_row_with_fk(engine, partner_factory, admin):
    p = await partner_factory(tax_withholding_category="pph23")
    orig = await engine.repo.insert_commission(
        partner_id=p.id,
        entry_type="accrual",
        base_amount_idr=Decimal("10000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("1000000"),
        net_amount_idr=Decimal("980000"),
        status="paid",
        idempotency_key="manual-1",
    )
    cb = await engine.clawback(orig, actor=admin, reason="client refunded 2026-05-01")
    cb_row = await engine.repo.get_commission(cb)

    assert cb_row.entry_type == "clawback"
    assert cb_row.net_amount_idr == Decimal("-980000")
    assert cb_row.related_commission_id == orig
    assert cb_row.status == "clawback_pending"


# ---------------------------------------------------------------------------
# 7. clawback() auto-waives when amount < auto-writeoff threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clawback_auto_writeoff_threshold(engine, partner_factory, admin, db_conn):
    # Set threshold to 1M IDR
    await db_conn.execute(
        "UPDATE system_settings SET value = '1000000' "
        "WHERE key = 'partner_clawback_auto_writeoff_idr'"
    )
    p = await partner_factory()
    orig = await engine.repo.insert_commission(
        partner_id=p.id,
        entry_type="accrual",
        base_amount_idr=Decimal("5000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("500000"),
        net_amount_idr=Decimal("500000"),
        status="paid",
        idempotency_key="manual-wo",
    )
    cb = await engine.clawback(orig, actor=admin, reason="tiny")
    row = await engine.repo.get_commission(cb)
    assert row.status == "waived"  # auto-writeoff


# ---------------------------------------------------------------------------
# 8. approve() offsets oldest pending clawback and reduces net
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_offsets_oldest_pending_clawback(
    engine, partner_factory, admin, db_conn
):
    p = await partner_factory(tax_withholding_category="exempt")

    # 1) Existing pending clawback: -300k
    cb = await engine.repo.insert_commission(
        partner_id=p.id,
        entry_type="clawback",
        base_amount_idr=Decimal("3000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("-300000"),
        net_amount_idr=Decimal("-300000"),
        status="clawback_pending",
        idempotency_key="cb-1",
    )

    # 2) New accrual: 500k eligible now.
    # withholding_category must be 'exempt' (matching the partner) so that
    # approve() is not blocked by the 'tbd' gate.
    new = await engine.repo.insert_commission(
        partner_id=p.id,
        entry_type="accrual",
        base_amount_idr=Decimal("5000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("500000"),
        net_amount_idr=Decimal("500000"),
        withholding_category="exempt",
        status="accrued",
        idempotency_key="new-1",
    )
    await db_conn.execute(
        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' "
        "WHERE id = $1",
        new,
    )

    await engine.approve(new, actor=admin)

    cb_row = await engine.repo.get_commission(cb)
    new_row = await engine.repo.get_commission(new)

    assert cb_row.status == "offset_applied"
    assert new_row.status == "approved"
    assert new_row.net_amount_idr == Decimal("200000")  # 500k - 300k
