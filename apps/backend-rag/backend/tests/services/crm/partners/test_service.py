# tests/services/crm/partners/test_service.py
import pytest
from decimal import Decimal
from fastapi import HTTPException

import uuid
from uuid import uuid4
from backend.services.crm.partners.service import (
    PartnersService,
    ConflictError,
    verify_partner_access,
)


@pytest.fixture
async def svc(db_conn):
    return PartnersService(db_conn)


@pytest.mark.asyncio
async def test_create_partner_writes_audit_log(svc, user_factory):
    team = await user_factory(role="team")
    pid = await svc.create_partner(
        full_name="H",
        email="h@x.io",
        entity_type="individual",
        assigned_to=team,
        created_by=team,
    )
    audit = await svc.list_audit(pid)
    assert len(audit) == 1
    assert audit[0].action == "created"
    assert audit[0].actor_user_id == team


@pytest.mark.asyncio
async def test_activate_partner_requires_admin_and_audits(svc, user_factory):
    team = await user_factory(role="team")
    admin = await user_factory(role="admin")
    pid = await svc.create_partner(
        full_name="H",
        email="h2@x.io",
        entity_type="individual",
        created_by=team,
    )
    with pytest.raises(HTTPException) as exc:
        await svc.activate_partner(pid, actor_user=team)
    assert exc.value.status_code == 403

    await svc.activate_partner(pid, actor_user=admin)
    p = await svc.get_partner(pid, actor_user=admin)
    assert p.onboarding_status == "active"
    audit = await svc.list_audit(pid)
    assert any(a.action == "activated" for a in audit)


@pytest.mark.asyncio
async def test_verify_partner_access_admin_always_allowed(svc, user_factory, partner_factory):
    admin = await user_factory(role="admin")
    # partner_factory returns a UUID
    partner_id = await partner_factory(assigned_to=None)
    result = await verify_partner_access(svc, admin, partner_id)
    # admin can always access; result is a Partner with matching id
    assert result.id == partner_id


@pytest.mark.asyncio
async def test_verify_partner_access_team_must_own(svc, user_factory, partner_factory):
    u1 = await user_factory(role="team")
    u2 = await user_factory(role="team")
    # partner_factory returns a UUID
    partner_id = await partner_factory(assigned_to=u1)
    # u1 (owner) can access
    result = await verify_partner_access(svc, u1, partner_id)
    assert result.id == partner_id
    # u2 (non-owner) cannot
    with pytest.raises(HTTPException) as exc:
        await verify_partner_access(svc, u2, partner_id)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reassign_requires_reason_and_records_audit(svc, user_factory):
    admin = await user_factory(role="admin")
    u1 = await user_factory(role="team")
    u2 = await user_factory(role="team")
    pid = await svc.create_partner(
        full_name="H",
        email="h3@x.io",
        entity_type="individual",
        assigned_to=u1,
        created_by=admin,
    )
    with pytest.raises(ValueError, match="reason"):
        await svc.reassign_partner(pid, new_user_id=u2, actor_user=admin, reason=None)
    await svc.reassign_partner(
        pid, new_user_id=u2, actor_user=admin, reason="u1 left bali zero 2026-04"
    )
    audit = await svc.list_audit(pid)
    reassign = next(a for a in audit if a.action == "reassigned")
    assert reassign.reason == "u1 left bali zero 2026-04"


@pytest.mark.asyncio
async def test_orphan_partners_on_team_user_deactivation(svc, user_factory):
    admin = await user_factory(role="admin")
    u = await user_factory(role="team")
    p1 = await svc.create_partner(
        full_name="A",
        email="a@z.io",
        entity_type="individual",
        assigned_to=u,
        created_by=admin,
    )
    p2 = await svc.create_partner(
        full_name="B",
        email="b@z.io",
        entity_type="individual",
        assigned_to=u,
        created_by=admin,
    )
    n = await svc.orphan_partners_of_user(u, actor_user=admin)
    assert n == 2
    for pid in (p1, p2):
        p = await svc.get_partner(pid, actor_user=admin)
        assert p.assigned_to is None
        audit = await svc.list_audit(pid)
        assert any(a.action == "orphaned" for a in audit)


@pytest.mark.asyncio
async def test_update_partner_does_not_reset_welcome_email_sent(svc, user_factory):
    """update_partner must NOT touch welcome_email_sent_at."""
    admin = await user_factory(role="admin")
    pid = await svc.create_partner(
        full_name="WelcomeTest",
        email="wt@x.io",
        entity_type="individual",
        created_by=admin,
    )
    # Mark welcome sent
    await svc.mark_welcome_sent(pid)

    # Fetch and confirm welcome_email_sent_at is set
    p_before = await svc.get_partner(pid, actor_user=admin)
    assert p_before.welcome_email_sent_at is not None

    # Update some field
    await svc.update_partner(
        pid,
        actor_user=admin,
        actor_role="admin",
        full_name="WelcomeTest Updated",
    )

    # welcome_email_sent_at must still be set
    p_after = await svc.get_partner(pid, actor_user=admin)
    assert p_after.welcome_email_sent_at is not None
    assert p_after.welcome_email_sent_at == p_before.welcome_email_sent_at


@pytest.mark.asyncio
async def test_deactivate_partner_soft_delete_preserves_history(
    svc, user_factory, referral_factory, practice_factory
):
    """Deactivation keeps all referrals and commissions readable."""
    admin = await user_factory(role="admin")
    pid = await svc.create_partner(
        full_name="SoftDelete",
        email="sd@x.io",
        entity_type="individual",
        created_by=admin,
    )
    # Add a referral
    await referral_factory(partner_id=pid)

    # Deactivate
    await svc.deactivate_partner(pid, actor_user=admin)

    # Partner status is inactive
    p = await svc.get_partner(pid, actor_user=admin)
    assert p.onboarding_status == "inactive"

    # Referrals still readable
    referrals = await svc.repo.list_referrals_for_partner(pid)
    assert len(referrals) >= 1

    # Audit log has deactivated entry
    audit = await svc.list_audit(pid)
    assert any(a.action == "deactivated" for a in audit)


@pytest.mark.asyncio
async def test_create_rejects_partner_with_internal_email(svc, user_factory):
    """create_partner raises ConflictError (409) when email matches a team/admin user.

    CATA-5: user_factory uses @test.invalid domain so the row is cleaned up
    automatically by db_conn teardown.
    """
    conflict_email = "conflict-internal@test.invalid"
    admin = await user_factory(role="admin", email=conflict_email)
    with pytest.raises(ConflictError) as exc:
        await svc.create_partner(
            full_name="Conflict Test",
            email=conflict_email,
            entity_type="individual",
            created_by=admin,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_reassign_nonexistent_partner_raises_404(db_conn, user_factory):
    """reassign_partner raises HTTPException(404) when partner_id is unknown."""
    admin = await user_factory(role="admin")
    svc = PartnersService(db_conn)
    with pytest.raises(HTTPException) as exc:
        await svc.reassign_partner(
            uuid4(), new_user_id=None,
            actor_user=admin, reason="cleanup",
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_partner_rejects_partner_role_self_update(
    db_conn, user_factory, partner_factory,
):
    """update_partner rejects partner-role actor at service layer (spec §7.2)."""
    partner_id = await partner_factory()
    # Link a partner-role user to this partner
    # CATA-5: user_factory returns string ID; update team_members, not users
    partner_user = await user_factory(role="partner")
    await db_conn.execute(
        "UPDATE team_members SET partner_id = $2 WHERE id = $1",
        str(partner_user), uuid.UUID(int=partner_id.int),
    )
    svc = PartnersService(db_conn)
    with pytest.raises(HTTPException) as exc:
        await svc.update_partner(
            partner_id,
            actor_user=partner_user, actor_role="partner",
            full_name="New Name",
        )
    assert exc.value.status_code == 403
    assert "may not update" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_create_partner_blocks_entity_type_foreign(db_conn, user_factory):
    """CRIT-5: entity_type='foreign' must be rejected at service layer (NB-2 compliance).

    Paying commission to a foreign partner on a standard KITAS violates KITAS
    conditions against Indonesian-source income. Blocked until v1.1 splits into
    foreign_kitap / foreign_offshore variants.
    """
    admin = await user_factory(role="admin")
    svc = PartnersService(db_conn)
    with pytest.raises(ConflictError) as exc:
        await svc.create_partner(
            full_name="Hotel X",
            email="hotelx@foreign.io",
            entity_type="foreign",
            created_by=admin,
        )
    assert exc.value.status_code == 409
    assert "foreign" in exc.value.detail.lower()
