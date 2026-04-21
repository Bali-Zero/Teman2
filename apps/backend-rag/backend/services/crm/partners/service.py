# backend/services/crm/partners/service.py
# CATA-5: Production has NO `users` table. Team identity lives in
# team_members(id VARCHAR) with email-like string IDs. All user/actor
# identifier params use str (not UUID). Partner-entity IDs stay UUID.
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from backend.services.crm.partners.models import Partner, PartnerAuditLogEntry
from backend.services.crm.partners.repository import PartnersRepository

logger = logging.getLogger(__name__)


class ConflictError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail)


class PartnersService:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.repo = PartnersRepository(conn)

    async def create_partner(
        self,
        *,
        full_name: str,
        email: str,
        entity_type: str,
        # CATA-5: assigned_to and created_by are team_members.id (VARCHAR string IDs)
        assigned_to: str | None = None,
        created_by: str | None = None,
        **optional: Any,
    ) -> UUID:
        # NB-2 immigration compliance gate (CRIT-5):
        # entity_type='foreign' violates Indonesian KITAS conditions for most
        # foreign partners. Paying commission to a foreign partner on a standard
        # KITAS (E23/E33E/F/G) constitutes Indonesian-source income, which
        # breaches KITAS conditions — consequences: KITAS revocation + cekal
        # blacklist for the partner; complicity exposure for Bali Zero PT PMA.
        # Until the foreign_kitap/foreign_offshore split is designed, block at
        # service layer. Spec §Q4 + council synthesis 2026-04-21.
        if entity_type == "foreign":
            raise ConflictError(
                "entity_type='foreign' is temporarily disabled pending legal/tax review. "
                "See docs/superpowers/reviews/2026-04-21-partners-v1/04-nb2.md for context. "
                "v1.1 will split into foreign_kitap and foreign_offshore variants."
            )
        try:
            pid = await self.repo.insert_partner(
                full_name=full_name,
                email=email,
                entity_type=entity_type,
                assigned_to=assigned_to,
                created_by=created_by,
                **optional,
            )
        except ValueError as e:
            raise ConflictError(str(e))
        except asyncpg.UniqueViolationError:
            raise ConflictError(f"email already in use: {email!r}")
        after = {
            "full_name": full_name,
            "email": email,
            "assigned_to": str(assigned_to) if assigned_to else None,
        }
        await self.repo.insert_audit(
            partner_id=pid,
            action="created",
            actor_user_id=created_by,
            after=after,
        )
        return pid

    async def get_partner(self, partner_id: UUID, *, actor_user: str) -> Partner:
        return await verify_partner_access(self, actor_user, partner_id)

    async def list_partners(
        self,
        *,
        # CATA-5: actor_user is team_members.id (VARCHAR string ID)
        actor_user: str,
        actor_role: str,
        assigned_to: str | None = None,
        onboarding_status: str | None = None,
        orphaned: bool = False,
        search: str | None = None,
    ) -> list[Partner]:
        if actor_role == "team":
            assigned_to = actor_user  # force scope to own
        return await self.repo.list_partners(
            assigned_to=assigned_to,
            onboarding_status=onboarding_status,
            orphaned=orphaned,
            search=search,
        )

    async def update_partner(
        self,
        partner_id: UUID,
        *,
        # CATA-5: actor_user is team_members.id (VARCHAR string ID)
        actor_user: str,
        actor_role: str,
        **fields: Any,
    ) -> None:
        if actor_role == "partner":
            raise HTTPException(status_code=403, detail="partners may not update their own profile via this endpoint")
        current = await verify_partner_access_with_role(
            self, actor_user, actor_role, partner_id
        )
        before = {k: getattr(current, k) for k in fields if hasattr(current, k)}
        try:
            await self.repo.update_partner(partner_id, **fields)
        except ValueError as e:
            raise ConflictError(str(e))
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="updated",
            actor_user_id=actor_user,
            before=before,
            after=fields,
        )

    async def activate_partner(self, partner_id: UUID, *, actor_user: str) -> None:
        # CATA-5: actor_user is team_members.id (VARCHAR string ID)
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        await self.repo.activate_partner(partner_id)
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="activated",
            actor_user_id=actor_user,
        )

    async def deactivate_partner(self, partner_id: UUID, *, actor_user: str) -> None:
        # CATA-5: actor_user is team_members.id (VARCHAR string ID)
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        await self.repo.deactivate_partner(partner_id)
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="deactivated",
            actor_user_id=actor_user,
        )

    async def reassign_partner(
        self,
        partner_id: UUID,
        *,
        # CATA-5: new_user_id and actor_user are team_members.id (VARCHAR string IDs)
        new_user_id: str | None,
        actor_user: str,
        reason: str | None,
    ) -> None:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        if not reason:
            raise ValueError("reason is required for reassignment")
        current = await self.repo.get_partner(partner_id)
        if current is None:
            raise HTTPException(status_code=404, detail="partner not found")
        before = {"assigned_to": str(current.assigned_to) if current.assigned_to else None}
        after = {"assigned_to": str(new_user_id) if new_user_id else None}
        await self.repo.reassign_partner(partner_id, new_user_id)
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="reassigned",
            actor_user_id=actor_user,
            before=before,
            after=after,
            reason=reason,
        )

    async def orphan_partners_of_user(self, user_id: str, *, actor_user: str) -> int:
        # CATA-5: user_id and actor_user are team_members.id (VARCHAR string IDs)
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        affected = await self.repo.list_partners(assigned_to=user_id)
        n = await self.repo.orphan_partners_of_user(user_id)
        for p in affected:
            await self.repo.insert_audit(
                partner_id=p.id,
                action="orphaned",
                actor_user_id=actor_user,
                before={"assigned_to": str(user_id)},
                after={"assigned_to": None},
                reason=f"auto-orphan on deactivation of user {user_id}",
            )
        return n

    async def list_audit(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
        return await self.repo.list_audit_for_partner(partner_id)

    async def mark_welcome_sent(self, partner_id: UUID) -> None:
        await self.repo.mark_welcome_sent(partner_id)


async def _is_admin(conn: asyncpg.Connection, user_id: str) -> bool:
    # CATA-5: Query team_members, not users (production has no `users` table).
    # team_members.id is VARCHAR (email-like string, e.g. "zero@balizero.com").
    row = await conn.fetchrow("SELECT role FROM team_members WHERE id = $1", user_id)
    return bool(row) and row["role"] == "admin"


async def _get_role(conn: asyncpg.Connection, user_id: str) -> str | None:
    # CATA-5: Query team_members, not users.
    row = await conn.fetchrow("SELECT role FROM team_members WHERE id = $1", user_id)
    return row["role"] if row else None


async def verify_partner_access(
    svc: PartnersService, actor_user: str, partner_id: UUID
) -> Partner:
    # CATA-5: actor_user is team_members.id (VARCHAR string ID)
    role = await _get_role(svc.conn, actor_user)
    return await verify_partner_access_with_role(svc, actor_user, role, partner_id)


async def verify_partner_access_with_role(
    svc: PartnersService,
    actor_user: str,
    actor_role: str | None,
    partner_id: UUID,
) -> Partner:
    # CATA-5: actor_user is team_members.id (VARCHAR string ID)
    partner = await svc.repo.get_partner(partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="partner not found")
    if actor_role == "admin":
        return partner
    if actor_role == "team" and partner.assigned_to == actor_user:
        return partner
    if actor_role == "partner":
        # CATA-5: Check via team_members table (not users — doesn't exist in production).
        # team_members.partner_id was added by this migration (migration 119).
        row = await svc.conn.fetchrow(
            "SELECT partner_id FROM team_members WHERE id = $1", actor_user
        )
        if row and row["partner_id"] == partner_id:
            return partner
    raise HTTPException(status_code=403, detail="forbidden")
