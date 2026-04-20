# backend/services/crm/partners/repository.py
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.crm.partners.models import (
    Partner, PartnerReferral, PartnerCommission, PartnerAuditLogEntry,
    EntityType, CommissionType, CommissionStatus, CommissionEntryType,
    WithholdingCategory, RuleSource,
)

logger = logging.getLogger(__name__)

# Commission state machine.
# Source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3.3 + §4.4.
# v1 terminal states: paid, offset_applied, waived, repaid.
_ALLOWED_TRANSITIONS: dict[CommissionStatus, set[CommissionStatus]] = {
    "accrued": {"approved"},
    "approved": {"paid"},
    "paid": set(),
    "clawback_pending": {"offset_applied", "waived", "repaid"},
    "offset_applied": set(),
    "waived": set(),
    "repaid": set(),
}

_PARTNER_UPDATABLE_COLS = {
    "full_name", "work_role", "company_name", "office_address",
    "email", "phone", "preferred_language",
    "entity_type", "npwp", "nik", "tax_withholding_category", "fiscal_address",
    "bank_name", "bank_account_holder", "bank_account_number",
    "ewallet_type", "ewallet_number", "payment_currency", "iban", "payment_notes",
    "default_commission_type", "default_commission_value",
    "pdp_consent_at", "pdp_consent_version", "terms_accepted_at", "terms_version",
}
# NB: onboarding_status, assigned_to, welcome_email_sent_at are ONLY settable
# via their dedicated methods (activate_partner, reassign_partner, mark_welcome_sent).


class PartnersRepository:
    """SQL layer. No business logic, no audit writes, no event emission."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    # ── Partner CRUD ────────────────────────────────────────────────────

    async def insert_partner(
        self,
        *,
        full_name: str,
        email: str,
        entity_type: EntityType,
        assigned_to: UUID | None = None,
        created_by: UUID | None = None,
        **optional: Any,
    ) -> UUID:
        await self._assert_email_is_not_internal(email)
        cols = ["full_name", "email", "entity_type", "assigned_to", "created_by"]
        vals: list[Any] = [full_name, email, entity_type, assigned_to, created_by]
        for k, v in optional.items():
            if k not in _PARTNER_UPDATABLE_COLS:
                raise ValueError(f"Field {k!r} is not insertable via insert_partner")
            cols.append(k); vals.append(v)
        placeholders = ", ".join(f"${i+1}" for i in range(len(vals)))
        sql = f"INSERT INTO partners ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
        row = await self.conn.fetchrow(sql, *vals)
        logger.debug("insert_partner id=%s email=%s", row["id"], email)
        return row["id"]

    async def _assert_email_is_not_internal(self, email: str) -> None:
        """Reject partner emails that match an internal team/admin user.

        KNOWN RACE: This is a SELECT-then-INSERT pattern without a cross-table
        DB constraint. A concurrent INSERT into users with role in (team,admin)
        between this check and the partners INSERT would slip through. v2
        should add a SERIALIZABLE transaction wrapper or a cross-table unique
        trigger. For v1 the race window is narrow and acceptable (rare admin
        operation concurrent with partner onboarding).
        """
        row = await self.conn.fetchrow(
            "SELECT 1 FROM users WHERE email = $1 AND role IN ('team','admin')",
            email,
        )
        if row is not None:
            raise ValueError(f"email is already a team/admin user: {email!r}")

    async def get_partner(self, partner_id: UUID) -> Partner | None:
        row = await self.conn.fetchrow("SELECT * FROM partners WHERE id = $1", partner_id)
        return self._row_to_partner(row) if row else None

    async def list_partners(
        self,
        *,
        assigned_to: UUID | None = None,
        onboarding_status: str | None = None,
        orphaned: bool = False,
        search: str | None = None,
        limit: int = 200,
    ) -> list[Partner]:
        where, args = ["TRUE"], []
        if assigned_to is not None:
            args.append(assigned_to); where.append(f"assigned_to = ${len(args)}")
        if onboarding_status is not None:
            args.append(onboarding_status); where.append(f"onboarding_status = ${len(args)}")
        if orphaned:
            where.append("assigned_to IS NULL")
        if search:
            args.append(f"%{search}%")
            where.append(f"(full_name ILIKE ${len(args)} OR email ILIKE ${len(args)} OR company_name ILIKE ${len(args)})")
        args.append(limit)
        sql = f"SELECT * FROM partners WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ${len(args)}"
        rows = await self.conn.fetch(sql, *args)
        return [self._row_to_partner(r) for r in rows]

    async def update_partner(self, partner_id: UUID, **fields: Any) -> None:
        if not fields:
            raise ValueError("update_partner requires at least one field")
        bad = set(fields) - _PARTNER_UPDATABLE_COLS
        if bad:
            raise ValueError(f"Non-updatable fields: {bad}")
        if "email" in fields:
            await self._assert_email_is_not_internal(fields["email"])
        sets = [f"{k} = ${i+2}" for i, k in enumerate(fields)]
        sets.append(f"updated_at = now()")
        sql = f"UPDATE partners SET {', '.join(sets)} WHERE id = $1"
        await self.conn.execute(sql, partner_id, *fields.values())

    async def activate_partner(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET onboarding_status = 'active', updated_at = now() "
            "WHERE id = $1 AND onboarding_status = 'pending_approval'",
            partner_id,
        )

    async def deactivate_partner(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET onboarding_status = 'inactive', deactivated_at = now(), "
            "updated_at = now() WHERE id = $1",
            partner_id,
        )

    async def reassign_partner(self, partner_id: UUID, new_user_id: UUID | None) -> None:
        await self.conn.execute(
            "UPDATE partners SET assigned_to = $2, updated_at = now() WHERE id = $1",
            partner_id, new_user_id,
        )

    async def orphan_partners_of_user(self, user_id: UUID) -> int:
        result = await self.conn.execute(
            "UPDATE partners SET assigned_to = NULL, updated_at = now() WHERE assigned_to = $1",
            user_id,
        )
        # asyncpg returns "UPDATE <n>"
        return int(result.split()[-1])

    async def mark_welcome_sent(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET welcome_email_sent_at = now() "
            "WHERE id = $1 AND welcome_email_sent_at IS NULL",
            partner_id,
        )

    # ── Referrals ───────────────────────────────────────────────────────

    async def insert_referral(
        self, *, partner_id: UUID, process_id: UUID,
        referred_by_user_id: UUID | None = None,
        share_percent: Decimal = Decimal("100.00"),
        notes: str | None = None,
    ) -> UUID:
        row = await self.conn.fetchrow(
            """
            INSERT INTO partner_referrals
                (partner_id, process_id, share_percent, referred_by_user_id, notes)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            partner_id, process_id, share_percent, referred_by_user_id, notes,
        )
        return row["id"]

    async def get_referral_by_process(self, process_id: UUID) -> PartnerReferral | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM partner_referrals WHERE process_id = $1", process_id
        )
        return self._row_to_referral(row) if row else None

    async def list_referrals_for_partner(self, partner_id: UUID) -> list[PartnerReferral]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_referrals WHERE partner_id = $1 ORDER BY referred_at DESC",
            partner_id,
        )
        return [self._row_to_referral(r) for r in rows]

    async def update_referral_partner(self, referral_id: UUID, new_partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partner_referrals SET partner_id = $2 WHERE id = $1",
            referral_id, new_partner_id,
        )

    async def delete_referral(self, referral_id: UUID) -> None:
        # Referrals are deletable ONLY before any commission is accrued against them.
        row = await self.conn.fetchrow(
            "SELECT 1 FROM partner_commissions WHERE referral_id = $1 LIMIT 1",
            referral_id,
        )
        if row is not None:
            raise RuntimeError("Cannot delete referral with commissions recorded")
        try:
            await self.conn.execute("DELETE FROM partner_referrals WHERE id = $1", referral_id)
        except asyncpg.ForeignKeyViolationError as e:
            # Race: commission inserted between our SELECT and DELETE.
            raise RuntimeError("Cannot delete referral with commissions recorded") from e

    # ── Commissions (append-only) ───────────────────────────────────────

    async def insert_commission(
        self,
        *,
        partner_id: UUID,
        entry_type: CommissionEntryType,
        base_amount_idr: Decimal,
        commission_type_snapshot: CommissionType,
        commission_value_snapshot: Decimal,
        gross_amount_idr: Decimal,
        net_amount_idr: Decimal,
        idempotency_key: str,
        referral_id: UUID | None = None,
        process_id: UUID | None = None,
        related_commission_id: UUID | None = None,
        rule_source: RuleSource = "partner_default",
        assigned_to_snapshot: UUID | None = None,
        withholding_category: WithholdingCategory = "tbd",
        withholding_rate: Decimal = Decimal("0.0"),
        withholding_amount_idr: Decimal = Decimal("0.0"),
        status: CommissionStatus = "accrued",
        eligible_for_approval_at: Any = None,
        manual_override_reason: str | None = None,
        clawback_reason: str | None = None,
    ) -> UUID:
        row = await self.conn.fetchrow(
            """
            INSERT INTO partner_commissions (
                partner_id, entry_type, referral_id, process_id, related_commission_id,
                base_amount_idr, commission_type_snapshot, commission_value_snapshot,
                rule_source, assigned_to_snapshot,
                gross_amount_idr, withholding_category, withholding_rate,
                withholding_amount_idr, net_amount_idr,
                status, eligible_for_approval_at,
                manual_override_reason, clawback_reason, idempotency_key
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
                    COALESCE($17, now()),$18,$19,$20)
            RETURNING id
            """,
            partner_id, entry_type, referral_id, process_id, related_commission_id,
            base_amount_idr, commission_type_snapshot, commission_value_snapshot,
            rule_source, assigned_to_snapshot,
            gross_amount_idr, withholding_category, withholding_rate,
            withholding_amount_idr, net_amount_idr,
            status, eligible_for_approval_at,
            manual_override_reason, clawback_reason, idempotency_key,
        )
        logger.debug(
            "insert_commission id=%s partner=%s type=%s status=%s",
            row["id"], partner_id, entry_type, status,
        )
        return row["id"]

    async def get_commission(self, commission_id: UUID) -> PartnerCommission | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM partner_commissions WHERE id = $1", commission_id
        )
        return self._row_to_commission(row) if row else None

    async def list_commissions_for_partner(
        self, partner_id: UUID, *, status: CommissionStatus | None = None,
    ) -> list[PartnerCommission]:
        args: list[Any] = [partner_id]
        where = "partner_id = $1"
        if status is not None:
            args.append(status); where += f" AND status = ${len(args)}"
        sql = f"SELECT * FROM partner_commissions WHERE {where} ORDER BY created_at DESC"
        rows = await self.conn.fetch(sql, *args)
        return [self._row_to_commission(r) for r in rows]

    async def list_pending_clawbacks(self, partner_id: UUID) -> list[PartnerCommission]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_commissions WHERE partner_id = $1 AND status = 'clawback_pending' "
            "ORDER BY accrued_at ASC",
            partner_id,
        )
        return [self._row_to_commission(r) for r in rows]

    async def update_commission_status(
        self,
        commission_id: UUID,
        new_status: CommissionStatus,
        *,
        approved_by: UUID | None = None,
        paid_by: UUID | None = None,
        paid_via: str | None = None,
        payment_reference: str | None = None,
        payment_proof_url: str | None = None,
        receipt_type: str | None = None,
        receipt_file_url: str | None = None,
        waiver_reason: str | None = None,
    ) -> None:
        current = await self.get_commission(commission_id)
        if current is None:
            raise ValueError(f"Commission {commission_id} not found")
        if new_status not in _ALLOWED_TRANSITIONS.get(current.status, set()):
            raise ValueError(
                f"Disallowed transition: {current.status!r} -> {new_status!r}"
            )
        logger.debug(
            "update_commission_status id=%s %s->%s", commission_id, current.status, new_status
        )
        fragments, args = ["status = $2"], [commission_id, new_status]
        if new_status == "approved":
            fragments += ["approved_at = now()", f"approved_by = ${len(args)+1}"]; args.append(approved_by)
        if new_status == "paid":
            fragments += [
                "paid_at = now()",
                f"paid_by = ${len(args)+1}", f"paid_via = ${len(args)+2}",
                f"payment_reference = ${len(args)+3}", f"payment_proof_url = ${len(args)+4}",
                f"receipt_type = ${len(args)+5}", f"receipt_file_url = ${len(args)+6}",
            ]
            args += [paid_by, paid_via, payment_reference, payment_proof_url,
                     receipt_type, receipt_file_url]
        if new_status == "waived":
            fragments += [f"waiver_reason = ${len(args)+1}"]; args.append(waiver_reason)
        sql = f"UPDATE partner_commissions SET {', '.join(fragments)} WHERE id = $1"
        await self.conn.execute(sql, *args)

    async def mark_commission_email_sent(self, commission_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partner_commissions SET commission_email_sent_at = now() "
            "WHERE id = $1 AND commission_email_sent_at IS NULL",
            commission_id,
        )

    async def delete_commission(self, commission_id: UUID) -> None:
        raise RuntimeError("partner_commissions is append-only; delete is forbidden")

    # ── Audit log ───────────────────────────────────────────────────────

    async def insert_audit(
        self,
        *,
        partner_id: UUID,
        action: str,
        actor_user_id: UUID | None = None,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO partner_audit_log
                (partner_id, actor_user_id, action, before_json, after_json, reason)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            partner_id, actor_user_id, action,
            json.dumps(before) if before else None,
            json.dumps(after) if after else None,
            reason,
        )

    async def list_audit_for_partner(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_audit_log WHERE partner_id = $1 ORDER BY at DESC",
            partner_id,
        )
        return [
            PartnerAuditLogEntry(
                id=r["id"], partner_id=r["partner_id"],
                actor_user_id=r["actor_user_id"], action=r["action"],
                before_json=json.loads(r["before_json"]) if r["before_json"] else None,
                after_json=json.loads(r["after_json"]) if r["after_json"] else None,
                reason=r["reason"], at=r["at"],
            )
            for r in rows
        ]

    # ── Row mappers ─────────────────────────────────────────────────────

    @staticmethod
    def _row_to_partner(row: asyncpg.Record) -> Partner:
        return Partner(**dict(row))

    @staticmethod
    def _row_to_referral(row: asyncpg.Record) -> PartnerReferral:
        return PartnerReferral(**dict(row))

    @staticmethod
    def _row_to_commission(row: asyncpg.Record) -> PartnerCommission:
        return PartnerCommission(**dict(row))
