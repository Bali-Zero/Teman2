# tests/services/crm/partners/test_repository.py
"""
Repository integration tests.

Every test uses a real asyncpg connection (db_conn fixture from conftest.py)
that creates the partner tables fresh for each test run and drops them in
teardown.  No mocking — these are SQL-layer tests.
"""
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from backend.services.crm.partners.repository import PartnersRepository


@pytest.fixture
async def repo(db_conn):
    return PartnersRepository(db_conn)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

async def _make_commission(repo: PartnersRepository, partner_id, **kwargs) -> str:
    """Insert a minimal commission row."""
    defaults = dict(
        partner_id=partner_id,
        entry_type="accrual",
        base_amount_idr=Decimal("10000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("1000000"),
        net_amount_idr=Decimal("1000000"),
        idempotency_key=f"accrual:test:{uuid4()}",
    )
    defaults.update(kwargs)
    return await repo.insert_commission(**defaults)


# --------------------------------------------------------------------------
# 1. insert_partner defaults
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_partner_returns_id_and_defaults(repo):
    pid = await repo.insert_partner(
        full_name="Hotel Kama",
        email="referrals@hotelkama.id",
        entity_type="corporate_pt",
    )
    p = await repo.get_partner(pid)
    assert p.full_name == "Hotel Kama"
    assert p.onboarding_status == "pending_approval"
    assert p.default_commission_value == Decimal("10.0")
    assert p.default_commission_type == "percentage"
    assert p.tax_withholding_category == "tbd"
    assert p.payment_currency == "IDR"


# --------------------------------------------------------------------------
# 2. email unique violation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_unique_violation(repo):
    await repo.insert_partner(
        full_name="A", email="dupe@x.io", entity_type="individual"
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.insert_partner(
            full_name="B", email="dupe@x.io", entity_type="individual"
        )


# --------------------------------------------------------------------------
# 3. email collision with internal user
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_collision_with_internal_user_is_rejected(repo, db_conn):
    await db_conn.execute(
        "INSERT INTO users (id, email, role) VALUES (gen_random_uuid(), $1, 'team')",
        "zero@balizero.com",
    )
    with pytest.raises(ValueError, match="email is already a team/admin user"):
        await repo.insert_partner(
            full_name="Zero Partner",
            email="zero@balizero.com",
            entity_type="individual",
        )


# --------------------------------------------------------------------------
# 4. list_partners filter by assigned_to
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_partners_filters_by_assigned_to(repo, user_factory):
    u1 = await user_factory(role="team")
    u2 = await user_factory(role="team")
    p1 = await repo.insert_partner(full_name="P1", email="p1@x.io",
                                   entity_type="individual", assigned_to=u1)
    _ = await repo.insert_partner(full_name="P2", email="p2@x.io",
                                  entity_type="individual", assigned_to=u2)
    results = await repo.list_partners(assigned_to=u1)
    assert len(results) == 1
    assert results[0].id == p1


# --------------------------------------------------------------------------
# 5. commission insert and append-only delete blocked
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commission_insert_and_append_only_delete_blocked(repo):
    pid = await repo.insert_partner(
        full_name="Hotel", email="a@b.io", entity_type="individual"
    )
    cid = await repo.insert_commission(
        partner_id=pid,
        entry_type="accrual",
        base_amount_idr=Decimal("10000000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("1000000"),
        net_amount_idr=Decimal("1000000"),
        idempotency_key="accrual:proc-1:2026-04-20T00:00:00",
    )
    # Repository must refuse DELETE (append-only contract)
    with pytest.raises(RuntimeError, match="append-only"):
        await repo.delete_commission(cid)


# --------------------------------------------------------------------------
# 6. commission idempotency key unique
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commission_idempotency_key_unique(repo):
    pid = await repo.insert_partner(
        full_name="H", email="h@b.io", entity_type="individual"
    )
    await repo.insert_commission(
        partner_id=pid, entry_type="accrual",
        base_amount_idr=Decimal("1000"),
        commission_type_snapshot="percentage",
        commission_value_snapshot=Decimal("10.0"),
        gross_amount_idr=Decimal("100"),
        net_amount_idr=Decimal("100"),
        idempotency_key="same-key",
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.insert_commission(
            partner_id=pid, entry_type="accrual",
            base_amount_idr=Decimal("1000"),
            commission_type_snapshot="percentage",
            commission_value_snapshot=Decimal("10.0"),
            gross_amount_idr=Decimal("100"),
            net_amount_idr=Decimal("100"),
            idempotency_key="same-key",
        )


# --------------------------------------------------------------------------
# 7. update_partner whitelist rejects status column
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_partner_whitelist_rejects_status_column(repo):
    pid = await repo.insert_partner(
        full_name="Test", email="wp@x.io", entity_type="individual"
    )
    with pytest.raises(ValueError, match="Non-updatable fields"):
        await repo.update_partner(pid, onboarding_status="active")


# --------------------------------------------------------------------------
# 8. activate_partner transitions status
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_activate_partner_transitions_status(repo):
    pid = await repo.insert_partner(
        full_name="Active Hotel", email="active@h.io", entity_type="individual"
    )
    p = await repo.get_partner(pid)
    assert p.onboarding_status == "pending_approval"

    await repo.activate_partner(pid)
    p = await repo.get_partner(pid)
    assert p.onboarding_status == "active"

    # idempotent — calling again on already-active partner is a no-op (no row updated, no error)
    await repo.activate_partner(pid)
    p = await repo.get_partner(pid)
    assert p.onboarding_status == "active"


# --------------------------------------------------------------------------
# 9. deactivate_partner sets status and deactivated_at
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivate_partner_sets_status_and_timestamp(repo):
    pid = await repo.insert_partner(
        full_name="Deactivated Hotel", email="deact@h.io", entity_type="individual"
    )
    await repo.activate_partner(pid)
    await repo.deactivate_partner(pid)
    p = await repo.get_partner(pid)
    assert p.onboarding_status == "inactive"
    assert p.deactivated_at is not None


# --------------------------------------------------------------------------
# 10. reassign_partner changes assigned_to
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reassign_partner_changes_assigned_to(repo, user_factory):
    u1 = await user_factory(role="team")
    u2 = await user_factory(role="team")
    pid = await repo.insert_partner(
        full_name="Reassign Test", email="reassign@h.io",
        entity_type="individual", assigned_to=u1,
    )
    p = await repo.get_partner(pid)
    assert p.assigned_to == u1

    await repo.reassign_partner(pid, u2)
    p = await repo.get_partner(pid)
    assert p.assigned_to == u2


# --------------------------------------------------------------------------
# 11. orphan_partners_of_user
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_partners_of_user(repo, user_factory):
    u = await user_factory(role="team")
    # Insert two partners assigned to user u, plus one not assigned
    await repo.insert_partner(full_name="Op1", email="op1@h.io",
                              entity_type="individual", assigned_to=u)
    await repo.insert_partner(full_name="Op2", email="op2@h.io",
                              entity_type="individual", assigned_to=u)
    await repo.insert_partner(full_name="Op3", email="op3@h.io",
                              entity_type="individual")

    count = await repo.orphan_partners_of_user(u)
    assert count == 2

    # All partners of u should now have assigned_to = NULL
    results = await repo.list_partners(assigned_to=u)
    assert len(results) == 0

    # The unassigned one is still there
    orphaned = await repo.list_partners(orphaned=True)
    # At least the two we just orphaned are present
    orphaned_emails = {p.email for p in orphaned}
    assert "op1@h.io" in orphaned_emails
    assert "op2@h.io" in orphaned_emails


# --------------------------------------------------------------------------
# 12. referral unique process_id violation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_referral_unique_process_id_violation(repo, process_factory):
    pid = await repo.insert_partner(
        full_name="Referral Hotel", email="ref@h.io", entity_type="individual"
    )
    process_id = await process_factory()
    await repo.insert_referral(partner_id=pid, process_id=process_id)
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.insert_referral(partner_id=pid, process_id=process_id)


# --------------------------------------------------------------------------
# 13. update_commission_status allows accrued → approved
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_commission_status_allows_accrued_to_approved(repo, user_factory):
    pid = await repo.insert_partner(
        full_name="Approve Test", email="approve@h.io", entity_type="individual"
    )
    approver = await user_factory(role="admin")
    cid = await _make_commission(repo, pid)

    await repo.update_commission_status(cid, "approved", approved_by=approver)

    c = await repo.get_commission(cid)
    assert c.status == "approved"
    assert c.approved_at is not None
    assert c.approved_by == approver


# --------------------------------------------------------------------------
# 14. update_commission_status rejects invalid transition (accrued → paid)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_commission_status_rejects_invalid_transition(repo):
    pid = await repo.insert_partner(
        full_name="Bad Transition", email="bad@h.io", entity_type="individual"
    )
    cid = await _make_commission(repo, pid)

    # accrued → paid is not allowed (must go through 'approved' first)
    with pytest.raises(ValueError, match="Disallowed transition"):
        await repo.update_commission_status(cid, "paid")


# --------------------------------------------------------------------------
# 15. audit log insert and list (newest-first ordering)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_insert_and_list(repo, user_factory):
    pid = await repo.insert_partner(
        full_name="Audit Test", email="audit@h.io", entity_type="individual"
    )
    actor = await user_factory(role="admin")

    await repo.insert_audit(
        partner_id=pid,
        action="created",
        actor_user_id=actor,
        before=None,
        after={"full_name": "Audit Test"},
        reason="Initial creation",
    )
    await repo.insert_audit(
        partner_id=pid,
        action="activated",
        actor_user_id=actor,
        before={"onboarding_status": "pending_approval"},
        after={"onboarding_status": "active"},
        reason="Manual activation",
    )

    entries = await repo.list_audit_for_partner(pid)
    assert len(entries) == 2
    # Newest first
    assert entries[0].action == "activated"
    assert entries[1].action == "created"
    # JSON round-trip
    assert entries[0].before_json == {"onboarding_status": "pending_approval"}
    assert entries[1].after_json == {"full_name": "Audit Test"}
