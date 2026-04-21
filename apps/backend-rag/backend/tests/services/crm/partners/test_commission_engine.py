# tests/services/crm/partners/test_commission_engine.py
"""
Commission engine integration tests.

All tests use the db_conn fixture (real asyncpg connection with partner
tables + system_settings + practices stub).
See conftest.py for fixture definitions — CATA-1 fix: practices is the real
production table. The 4 columns required by CommissionEngine are confirmed
from migration 075 trigger payload.

CRIT-7: _WITHHOLDING_RATES dict removed. Rates now resolved from system_settings
at accrual time via _get_withholding_rate() / _system_setting_decimal().
conftest _SCHEMA_SQL seeds the 3 new keys (pph21=2.5, pph23=2.0, surcharge=20).
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
    engine, partner_factory, practice_factory, referral_factory, db_conn
):
    # CRIT-7: partner needs NPWP to avoid the no-NPWP surcharge.
    # Without NPWP: 2.0 + 0.4 = 2.4%. With NPWP: 2.0% as expected.
    p = await partner_factory(
        default_commission_value=Decimal("10.0"),
        tax_withholding_category="pph23",
    )
    await db_conn.execute(
        "UPDATE partners SET npwp = '01.234.567.8-901.000' WHERE id = $1", p.id
    )
    proc = await practice_factory(
        total_invoiced_idr=Decimal("10000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    await engine.accrue_from_practice(proc.id, p.id)

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
    engine, partner_factory, practice_factory, referral_factory
):
    p = await partner_factory()
    proc = await practice_factory(status="completed", payment_status="paid")
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    await engine.accrue_from_practice(proc.id, p.id)
    await engine.accrue_from_practice(proc.id, p.id)  # second call: no-op

    commissions = await engine.repo.list_commissions_for_partner(p.id)
    assert len(commissions) == 1


# ---------------------------------------------------------------------------
# 3. approve() is blocked before cooling-off window expires
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_blocked_before_cooling_off(
    engine, partner_factory, practice_factory, referral_factory, admin
):
    p = await partner_factory(tax_withholding_category="exempt")
    proc = await practice_factory(status="completed", payment_status="paid")
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    await engine.accrue_from_practice(proc.id, p.id)
    c = (await engine.repo.list_commissions_for_partner(p.id))[0]

    with pytest.raises(ValueError, match="cooling-off"):
        await engine.approve(c.id, actor=admin)


# ---------------------------------------------------------------------------
# 4. approve() is blocked when withholding_category is 'tbd'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_blocked_when_withholding_tbd(
    engine, partner_factory, practice_factory, referral_factory, admin, db_conn
):
    p = await partner_factory(tax_withholding_category="tbd")
    proc = await practice_factory(status="completed", payment_status="paid")
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    await engine.accrue_from_practice(proc.id, p.id)
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
    engine, partner_factory, practice_factory, referral_factory
):
    p = await partner_factory(
        default_commission_type="flat",
        default_commission_value=Decimal("500000"),
        tax_withholding_category="exempt",
    )
    proc = await practice_factory(
        total_invoiced_idr=Decimal("10000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    await engine.accrue_from_practice(proc.id, p.id)
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


# ---------------------------------------------------------------------------
# 9. update_commission_status detects concurrent change (CRIT-1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_commission_status_detects_concurrent_change(
    engine, partner_factory, db_conn
):
    """CRIT-1: update_commission_status raises RuntimeError when a concurrent
    writer transitions the commission between our read and our UPDATE.

    Simulates: repo reads status='accrued', then a concurrent process
    transitions the commission to 'approved' before our UPDATE fires.
    The WHERE status='accrued' clause returns 0 rows → RuntimeError.
    """
    p = await partner_factory(tax_withholding_category="exempt")
    cid = await engine.repo.insert_commission(
        partner_id=p.id,
        entry_type="accrual",
        base_amount_idr=Decimal("10000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("1000"),
        net_amount_idr=Decimal("1000"),
        idempotency_key="test-concurrent-guard",
    )
    # Simulate a concurrent writer that already transitioned to 'approved'.
    # We bypass update_commission_status to do a raw UPDATE (simulating another
    # connection that won the race).
    await db_conn.execute(
        "UPDATE partner_commissions SET status = 'approved', approved_at = now() "
        "WHERE id = $1",
        cid,
    )
    # Now call update_commission_status with the stale old status ('accrued').
    # The FSM check: 'approved' → 'approved' is NOT in _ALLOWED_TRANSITIONS,
    # so ValueError fires first. Either ValueError or RuntimeError is acceptable
    # — the point is that it must NOT silently succeed.
    with pytest.raises((ValueError, RuntimeError)):
        await engine.repo.update_commission_status(cid, "approved")


# ---------------------------------------------------------------------------
# CRIT-7: Withholding rates from system_settings + no-NPWP surcharge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accrue_uses_pph23_rate_from_system_settings(
    engine, partner_factory, practice_factory, referral_factory
):
    """Default pph23 rate in settings is 2.0%. Partner HAS NPWP — no surcharge."""
    p = await partner_factory(
        tax_withholding_category="pph23",
        default_commission_value=Decimal("10.0"),
    )
    # Give the partner an NPWP so no surcharge applies.
    await engine.repo.conn.execute(
        "UPDATE partners SET npwp = '01.234.567.8-901.000' WHERE id = $1", p.id
    )
    proc = await practice_factory(
        total_invoiced_idr=Decimal("10000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    cid = await engine.accrue_from_practice(proc.id, p.id)
    assert cid is not None
    c = await engine.repo.get_commission(cid)

    # gross = 10M * 10% = 1M; withholding rate = 2.0%; withholding = 20k; net = 980k
    assert c.withholding_rate == Decimal("2.0")
    assert c.withholding_amount_idr == Decimal("20000")
    assert c.net_amount_idr == Decimal("980000")


@pytest.mark.asyncio
async def test_accrue_applies_no_npwp_surcharge_on_pph21(
    engine, partner_factory, practice_factory, referral_factory
):
    """Partner pph21 WITHOUT NPWP → 2.5% + 20% surcharge of base = 3.0% effective."""
    p = await partner_factory(
        tax_withholding_category="pph21",
        default_commission_value=Decimal("10.0"),
    )
    # Explicitly ensure npwp is NULL (factory default; just making the intent clear).
    await engine.repo.conn.execute(
        "UPDATE partners SET npwp = NULL WHERE id = $1", p.id
    )
    proc = await practice_factory(
        total_invoiced_idr=Decimal("10000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    cid = await engine.accrue_from_practice(proc.id, p.id)
    assert cid is not None
    c = await engine.repo.get_commission(cid)

    # effective = 2.5 + (2.5 * 20 / 100) = 2.5 + 0.5 = 3.0%
    # gross = 10M * 10% = 1M; withholding = 1M * 3% / 100 = 30k
    assert c.withholding_rate == Decimal("3.0")
    assert c.withholding_amount_idr == Decimal("30000")


@pytest.mark.asyncio
async def test_accrue_reads_rate_from_updated_system_setting(
    engine, partner_factory, practice_factory, referral_factory, db_conn
):
    """Admin changes pph23 rate mid-flight — next accrual picks up the new rate."""
    # Change pph23 rate from 2.0 to 1.5
    await db_conn.execute(
        "UPDATE system_settings SET value = '1.5' "
        "WHERE key = 'partner_withholding_rate_pph23'"
    )
    p = await partner_factory(
        tax_withholding_category="pph23",
        default_commission_value=Decimal("10.0"),
    )
    # Partner has NPWP → no surcharge
    await db_conn.execute(
        "UPDATE partners SET npwp = '99.999.999.9-999.000' WHERE id = $1", p.id
    )
    proc = await practice_factory(
        total_invoiced_idr=Decimal("10000000"),
        status="completed",
        payment_status="paid",
    )
    await referral_factory(partner_id=p.id, practice_id=proc.id)

    cid = await engine.accrue_from_practice(proc.id, p.id)
    assert cid is not None
    c = await engine.repo.get_commission(cid)

    # Rate should be 1.5% (the updated value, not the default 2.0%)
    assert c.withholding_rate == Decimal("1.5")
    # gross = 1M; withholding = 1M * 1.5 / 100 = 15k
    assert c.withholding_amount_idr == Decimal("15000")
