# backend/services/crm/partners/commission_engine.py
"""
CommissionEngine — pure-calculation + state-machine-transition layer.

Isolation contract: this module is the ONLY place that contains commission
business logic. It calls PartnersRepository directly and must not import
EventBus, FastAPI routers, or any other application-layer component (so it
can be tested with direct asyncpg connections and no side effects).

Business rules source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §4.4
Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 5

Append-only ledger exception (spec §Q9, plan Step 5.2):
  The partner_commissions table is append-only. The ONE documented exception
  is that approve() may reduce net_amount_idr on the incoming accrual row when
  offsetting a pending clawback. This is implemented via a raw UPDATE on that
  single column (search for "spec §Q9" in this file).

Pre-flight note (2026-04-20, outcome c — updated CATA-1):
  accrue_from_practice() reads from the `practices` table, which is the
  real production domain table (not a stub). Column names confirmed from
  migration 075 trigger and conftest stub DDL:
      status TEXT, payment_status TEXT,
      total_invoiced_idr NUMERIC(16,2), completed_at TIMESTAMPTZ, client_id.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.crm.partners.repository import PartnersRepository

logger = logging.getLogger(__name__)

# CRIT-7: Withholding rates are now stored in system_settings (not hardcoded).
# See _get_withholding_rate() and _system_setting_decimal() for the lookup.
# Keys in system_settings:
#   partner_withholding_rate_pph21          (default 2.5, percent)
#   partner_withholding_rate_pph23          (default 2.0, percent)
#   partner_withholding_no_npwp_surcharge   (default 20, percent of base rate)
# Rates are Decimal to avoid float rounding errors throughout all math.
# v1 default values — Asya to confirm with tax advisor after first 3 payouts.


class CommissionEngine:
    """Encapsulates all commission accrual, approval, payment, and clawback logic.

    Args:
        conn: A live asyncpg.Connection. The caller is responsible for
              lifecycle (open/close, transaction wrapping if needed).
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn
        self.repo = PartnersRepository(conn)

    # ── Accrual ─────────────────────────────────────────────────────────────

    async def accrue_from_practice(
        self,
        practice_id: int,
        partner_id: UUID | None = None,
    ) -> UUID | None:
        """Accrue a commission for a completed+paid practice.

        Reads the practice row, validates status/payment_status, resolves the
        referral and partner, computes gross/withholding/net with snapshot
        semantics, then inserts an 'accrued' commission row.

        Returns:
            The new commission UUID, or None if the practice is not yet eligible
            (not completed, not paid, no referral, or wrong partner_id).

        Idempotency:
            key = f"accrual:{practice_id}:{completed_at.isoformat()}"
            A second call for the same practice+completed_at is a no-op
            (ON CONFLICT DO NOTHING via UNIQUE index on idempotency_key).
        """
        # Step 1: fetch practice — must be completed AND paid.
        # NOTE: Column names confirmed from migration 075 trigger (practice_id, client_id,
        # status, payment_status) and conftest.py stub DDL (total_invoiced_idr, completed_at).
        proc = await self.conn.fetchrow(
            """
            SELECT id, status, payment_status, total_invoiced_idr, completed_at
            FROM practices WHERE id = $1
            """,
            practice_id,
        )
        if proc is None:
            logger.debug("accrue_from_practice: practice %s not found", practice_id)
            return None
        if proc["status"] != "completed" or proc["payment_status"] != "paid":
            logger.debug(
                "accrue_from_practice: practice %s not eligible (status=%s, payment_status=%s)",
                practice_id, proc["status"], proc["payment_status"],
            )
            return None

        # Step 2: resolve referral.
        referral = await self.repo.get_referral_by_practice(practice_id)
        if referral is None:
            logger.debug("accrue_from_practice: no referral for practice %s", practice_id)
            return None

        # Optional sanity-check: caller can assert which partner should receive the commission.
        if partner_id is not None and referral.partner_id != partner_id:
            logger.warning(
                "accrue_from_practice: partner_id mismatch "
                "(referral.partner_id=%s, caller said %s) — skipping",
                referral.partner_id, partner_id,
            )
            return None

        # Step 3: resolve partner for snapshot values.
        partner = await self.repo.get_partner(referral.partner_id)
        if partner is None:
            logger.warning(
                "accrue_from_practice: partner %s not found", referral.partner_id
            )
            return None

        # Step 4: compute amounts (all Decimal, no float).
        # base_amount_idr = practices.total_invoiced_idr (exact column name per stub DDL).
        base = Decimal(str(proc["total_invoiced_idr"]))

        if partner.default_commission_type == "percentage":
            gross = base * partner.default_commission_value / Decimal("100")
        else:
            # flat: commission_value is the fixed IDR amount regardless of base
            gross = partner.default_commission_value

        # CRIT-7: Resolve rate from system_settings (not hardcoded dict).
        # has_npwp is True only if the npwp field is set AND non-empty.
        has_npwp = bool(partner.npwp and partner.npwp.strip())
        rate = await self._get_withholding_rate(
            partner.tax_withholding_category,
            has_npwp=has_npwp,
        )
        # Withholding is quantized to whole IDR (no fractional rupiah).
        withholding = (gross * rate / Decimal("100")).quantize(Decimal("1"))
        net = gross - withholding

        # Step 5: resolve cooling-off days from system_settings.
        cooling_days = await self._system_setting_int("partner_accrual_cooling_off_days", 30)
        completed_at: datetime = proc["completed_at"] or datetime.now(timezone.utc)
        eligible = completed_at + timedelta(days=cooling_days)

        # Idempotency key: unique per practice + completed_at timestamp.
        # If completed_at changes (e.g. re-completion edge case), a new accrual fires.
        key = f"accrual:{practice_id}:{completed_at.isoformat()}"

        try:
            cid = await self.repo.insert_commission(
                partner_id=partner.id,
                entry_type="accrual",
                referral_id=referral.id,
                practice_id=practice_id,
                base_amount_idr=base,
                commission_type_snapshot=partner.default_commission_type,
                commission_value_snapshot=partner.default_commission_value,
                rule_source="partner_default",
                assigned_to_snapshot=partner.assigned_to,
                gross_amount_idr=gross,
                withholding_category=partner.tax_withholding_category,
                withholding_rate=rate,
                withholding_amount_idr=withholding,
                net_amount_idr=net,
                status="accrued",
                eligible_for_approval_at=eligible,
                idempotency_key=key,
            )
        except asyncpg.UniqueViolationError:
            logger.info(
                "accrue_from_practice: idempotency hit for key=%s — no-op", key
            )
            return None

        logger.info(
            "Accrued commission %s for partner %s (gross=%s, net=%s IDR)",
            cid, partner.id, gross, net,
        )
        return cid

    # ── Approve ─────────────────────────────────────────────────────────────

    async def approve(self, commission_id: UUID, *, actor: UUID) -> None:
        """Transition a commission from 'accrued' to 'approved'.

        Gates:
          - status must be 'accrued'
          - eligible_for_approval_at must be <= now() (cooling-off elapsed)
          - withholding_category must not be 'tbd'

        Offset logic (spec §4.4 rule 7):
          If the partner has any 'clawback_pending' commissions, the OLDEST
          one is paired with this accrual:
            - clawback transitions to 'offset_applied'
            - this accrual's net_amount_idr is reduced by abs(clawback.net)
          If the clawback magnitude exceeds the accrual's net, no offset is
          applied this round (partial offsets are v2 scope).

        Atomicity (CRIT-1, 2026-04-21):
          The offset block (net UPDATE + clawback status transition) and the
          approve transition are wrapped in a single async transaction. Crash
          safety: if any step fails, all writes roll back and the commission
          remains 'accrued'. Concurrent-change protection: update_commission_status
          now includes WHERE status = old_status in the UPDATE and raises
          RuntimeError on 0-row result (concurrent mutation detected).
        """
        c = await self.repo.get_commission(commission_id)
        if c is None:
            raise ValueError(f"Commission not found: {commission_id}")
        if c.status != "accrued":
            raise ValueError(
                f"cannot approve commission with status {c.status!r} "
                f"(must be 'accrued')"
            )
        now = datetime.now(timezone.utc)
        if c.eligible_for_approval_at > now:
            raise ValueError(
                f"Commission is still within the cooling-off window "
                f"(eligible at {c.eligible_for_approval_at.isoformat()})"
            )
        if c.withholding_category == "tbd":
            raise ValueError(
                "withholding category is tbd — set pph21|pph23|exempt first"
            )

        # CRIT-1: Wrap the offset + approve transition in a single transaction.
        # The previous implementation did two sequential UPDATEs without a
        # transaction — a crash between them left the ledger inconsistent
        # (accrual net reduced, clawback still 'clawback_pending'). Additionally,
        # concurrent approvals for the same partner could double-apply the same
        # oldest clawback row (update_commission_status uses read-check-write,
        # which is now guarded by a WHERE status = old_status clause in the repo).
        async with self.conn.transaction():
            pending = await self.repo.list_pending_clawbacks(c.partner_id)
            offset_applied_id: UUID | None = None
            if pending:
                oldest = pending[0]
                # offset_amount is positive (magnitude of the negative clawback).
                offset_amount = -oldest.net_amount_idr
                new_net = c.net_amount_idr - offset_amount

                if new_net <= 0:
                    # Clawback exceeds this accrual — defer to next approval cycle.
                    # Partial offsets require additional policy decisions (v2 scope).
                    logger.info(
                        "approve: clawback %s (magnitude %s) exceeds accrual %s net %s "
                        "— no offset this round",
                        oldest.id, offset_amount, c.id, c.net_amount_idr,
                    )
                else:
                    # ONE LEGAL LEDGER MUTATION (spec §Q9, plan Step 5.2):
                    # Reduce this accrual's net by the clawback magnitude before
                    # flipping the status to 'approved'. This is the only place
                    # where a pre-existing commission row's net_amount_idr is
                    # updated (all other commission writes go through insert_commission).
                    await self.conn.execute(
                        "UPDATE partner_commissions SET net_amount_idr = $2 WHERE id = $1",
                        c.id,
                        new_net,
                    )
                    await self.repo.update_commission_status(oldest.id, "offset_applied")
                    offset_applied_id = oldest.id
                    logger.info(
                        "approve: offset clawback %s against accrual %s "
                        "(net reduced %s → %s IDR)",
                        oldest.id, c.id, c.net_amount_idr, new_net,
                    )

            await self.repo.update_commission_status(
                commission_id, "approved", approved_by=actor
            )
            if offset_applied_id:
                logger.info(
                    "approve: commission %s approved with clawback %s offset",
                    commission_id, offset_applied_id,
                )
            else:
                logger.info("approve: commission %s approved (no clawback offset)", commission_id)

    # ── Mark paid ───────────────────────────────────────────────────────────

    async def mark_paid(
        self,
        commission_id: UUID,
        *,
        actor: UUID,
        paid_via: str,
        payment_reference: str,
        payment_proof_url: str | None = None,
        receipt_type: str | None = None,
        receipt_file_url: str | None = None,
    ) -> None:
        """Transition a commission from 'approved' to 'paid'."""
        await self.repo.update_commission_status(
            commission_id,
            "paid",
            paid_by=actor,
            paid_via=paid_via,
            payment_reference=payment_reference,
            payment_proof_url=payment_proof_url,
            receipt_type=receipt_type,
            receipt_file_url=receipt_file_url,
        )

    # ── Clawback ────────────────────────────────────────────────────────────

    async def clawback(
        self,
        original_commission_id: UUID,
        *,
        actor: UUID,
        reason: str,
        amount_idr: Decimal | None = None,
    ) -> UUID:
        """Issue a clawback against an approved or paid commission.

        Inserts a new 'clawback' entry_type row with negative amounts and
        status 'clawback_pending' (or 'waived' if the auto-writeoff threshold
        is configured and the amount is below it).

        Idempotency: NOT idempotent — each call inserts a new row. This is
        intentional: an operator may legitimately issue multiple partial
        clawbacks against the same original commission. The idempotency_key
        includes now().isoformat() to prevent accidental de-dup.

        Args:
            original_commission_id: The approved|paid commission to claw back.
            actor: The user UUID performing the operation.
            reason: Free-text justification (stored in clawback_reason).
            amount_idr: Override the clawback magnitude (positive IDR amount).
                        Defaults to the full net_amount_idr of the original.

        Returns:
            UUID of the newly created clawback row.
        """
        orig = await self.repo.get_commission(original_commission_id)
        if orig is None:
            raise ValueError(f"Commission not found: {original_commission_id}")
        if orig.status not in ("approved", "paid"):
            raise ValueError(
                f"Clawback only valid for approved|paid commissions, "
                f"got status {orig.status!r}"
            )

        # magnitude is the positive IDR amount to claw back
        magnitude = amount_idr if amount_idr is not None else orig.net_amount_idr
        gross_neg = -magnitude
        net_neg = -magnitude

        # Auto-writeoff: if the magnitude is below the threshold (and threshold > 0),
        # insert directly as 'waived' instead of 'clawback_pending'.
        threshold = await self._system_setting_int(
            "partner_clawback_auto_writeoff_idr", 0
        )
        auto_waive = threshold > 0 and abs(int(magnitude)) < threshold

        status = "waived" if auto_waive else "clawback_pending"

        # Key is NOT idempotent by design — see docstring above.
        key = f"clawback:{original_commission_id}:{datetime.now(timezone.utc).isoformat()}"

        cid = await self.repo.insert_commission(
            partner_id=orig.partner_id,
            entry_type="clawback",
            referral_id=orig.referral_id,
            practice_id=orig.practice_id,
            related_commission_id=orig.id,
            base_amount_idr=orig.base_amount_idr,
            commission_type_snapshot=orig.commission_type_snapshot,
            commission_value_snapshot=orig.commission_value_snapshot,
            assigned_to_snapshot=orig.assigned_to_snapshot,
            gross_amount_idr=gross_neg,
            withholding_category=orig.withholding_category,
            withholding_rate=orig.withholding_rate,
            withholding_amount_idr=Decimal("0"),
            net_amount_idr=net_neg,
            status=status,
            idempotency_key=key,
            clawback_reason=reason,
        )

        if auto_waive:
            logger.info(
                "clawback %s auto-waived (magnitude %s IDR < threshold %s IDR)",
                cid, magnitude, threshold,
            )
        else:
            logger.info(
                "clawback %s created (clawback_pending, magnitude %s IDR) "
                "against original %s",
                cid, magnitude, original_commission_id,
            )
        return cid

    # ── Waive clawback ──────────────────────────────────────────────────────

    async def waive_clawback(
        self,
        clawback_id: UUID,
        *,
        actor: UUID,
        reason: str,
    ) -> None:
        """Manually waive a 'clawback_pending' commission (operator decision)."""
        await self.repo.update_commission_status(
            clawback_id, "waived", waiver_reason=reason
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _system_setting_int(self, key: str, default: int) -> int:
        """Read an integer value from the system_settings table.

        Returns `default` if the key is absent or the value cannot be
        coerced to int (e.g. empty string, garbage data).
        """
        row = await self.conn.fetchrow(
            "SELECT value FROM system_settings WHERE key = $1", key
        )
        try:
            return int(row["value"]) if row else default
        except (ValueError, TypeError):
            return default

    async def _system_setting_decimal(self, key: str, default: Decimal) -> Decimal:
        """Read a Decimal value from the system_settings table.

        Returns `default` if the key is absent or the value cannot be
        coerced to Decimal (e.g. empty string, garbage data).
        """
        row = await self.conn.fetchrow(
            "SELECT value FROM system_settings WHERE key = $1", key
        )
        try:
            return Decimal(row["value"]) if row else default
        except (ValueError, TypeError):
            logger.warning(
                "system_settings key %r has unparseable value — using default %s",
                key, default,
            )
            return default

    async def _get_withholding_rate(
        self,
        category: str,
        *,
        has_npwp: bool,
    ) -> Decimal:
        """Resolve withholding rate for a commission accrual.

        CRIT-7: Rates are read from system_settings at accrual time so they
        can be adjusted without a code deploy (Asya changes the row, next
        accrual picks it up).

        Rules:
        - exempt: always 0 regardless of NPWP.
        - tbd: always 0 (and blocked at approve() regardless).
        - pph21 / pph23: base rate from system_settings.
          If the partner does NOT have an NPWP, add a surcharge:
            effective = base + (base * surcharge_percent / 100)
          This matches Indonesia's default PPh surcharge for taxpayers
          without NPWP (PPh 21 Pasal 21 ayat 5a, 20% additional).
        - Unknown categories: log a warning, return 0.
        """
        if category in ("exempt", "tbd"):
            return Decimal("0")

        if category == "pph21":
            base = await self._system_setting_decimal(
                "partner_withholding_rate_pph21", Decimal("2.5")
            )
        elif category == "pph23":
            base = await self._system_setting_decimal(
                "partner_withholding_rate_pph23", Decimal("2.0")
            )
        else:
            logger.warning(
                "CommissionEngine: unknown withholding category %r — using rate 0",
                category,
            )
            return Decimal("0")

        if not has_npwp:
            # Additive percentage-point surcharge (not multiplicative):
            #   effective = base + (base * surcharge_pct / 100)
            # e.g. base=2.5, surcharge=20 → 2.5 + 0.5 = 3.0%
            surcharge_pct = await self._system_setting_decimal(
                "partner_withholding_no_npwp_surcharge", Decimal("20")
            )
            return base + (base * surcharge_pct / Decimal("100"))

        return base
