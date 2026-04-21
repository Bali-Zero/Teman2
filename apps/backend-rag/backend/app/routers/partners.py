"""
FastAPI router — CRM Partners module (v1).

21 endpoints covering partner lifecycle, referrals, commissions, self-serve
/me routes for partner-role users, and a finance CSV export.

SCAR 2026-03-26: every mutation handler does `except HTTPException: raise`
BEFORE the generic `except Exception`.

Pre-flight findings (2026-04-20):
- get_current_user returns dict[str, Any] with keys:
    email, user_id, role, permissions (list, not set)
  NOT an object — use user["role"], user["user_id"].
- No partner_id in user dict; /me endpoints query users.partner_id from DB.
- DB dep is get_database_pool (returns Pool); use `async with pool.acquire() as conn`.
- Finance permission: check "finance.mark_paid" in permissions list; admin alone
  is sufficient as v1 fallback (permissions not yet wired to JWT for all clients).
"""
from __future__ import annotations

import csv
import dataclasses
import io
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.crm.partners.commission_engine import CommissionEngine
from backend.services.crm.partners.service import (
    ConflictError,
    PartnersService,
    verify_partner_access_with_role,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/partners", tags=["partners"])


# ── Pydantic request models ──────────────────────────────────────────────────

class PartnerCreate(BaseModel):
    full_name: str
    email: EmailStr
    entity_type: Literal["individual", "corporate_pt", "corporate_cv", "foreign"]
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    preferred_language: str = "id"
    npwp: str | None = None
    nik: str | None = None
    tax_withholding_category: Literal["pph21", "pph23", "exempt", "tbd"] = "tbd"
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    payment_currency: str = "IDR"
    iban: str | None = None
    payment_notes: str | None = None
    default_commission_type: Literal["percentage", "flat"] = "percentage"
    default_commission_value: Decimal = Decimal("10.0")
    assigned_to: UUID | None = None
    pdp_consent_version: str | None = None
    terms_version: str | None = None


class PartnerUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    entity_type: Literal["individual", "corporate_pt", "corporate_cv", "foreign"] | None = None
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    preferred_language: str | None = None
    npwp: str | None = None
    nik: str | None = None
    tax_withholding_category: Literal["pph21", "pph23", "exempt", "tbd"] | None = None
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    payment_currency: str | None = None
    iban: str | None = None
    payment_notes: str | None = None
    default_commission_type: Literal["percentage", "flat"] | None = None
    default_commission_value: Decimal | None = None
    pdp_consent_version: str | None = None
    terms_version: str | None = None


class ReassignRequest(BaseModel):
    new_user_id: UUID | None
    reason: str


class BulkReassignRequest(BaseModel):
    partner_ids: list[UUID]
    new_user_id: UUID
    reason: str


class ReferralCreate(BaseModel):
    practice_id: UUID
    notes: str | None = None


class ReferralSwap(BaseModel):
    new_partner_id: UUID


class CommissionMarkPaidRequest(BaseModel):
    paid_via: str
    payment_reference: str
    payment_proof_url: str | None = None
    receipt_type: Literal["kwitansi", "invoice", "none"] | None = None
    receipt_file_url: str | None = None


class ClawbackRequest(BaseModel):
    reason: str
    amount_idr: Decimal | None = None


class WaiveRequest(BaseModel):
    reason: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_admin(user: dict[str, Any]) -> None:
    """Raise 403 if user is not admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")


def _require_team_or_admin(user: dict[str, Any]) -> None:
    """Raise 403 if user is not team or admin.

    CATA-2: list/create partner endpoints and CATA-3: referral creation
    must be blocked at the router for the 'partner' role (and any unknown
    role). Only team members and admins interact with partners on behalf of
    the business.
    """
    role = user.get("role")
    if role not in ("team", "admin"):
        raise HTTPException(status_code=403, detail="team or admin role required")


def _require_finance(user: dict[str, Any]) -> None:
    """Raise 403 if user lacks the explicit finance.mark_paid permission.

    CRIT-3: The previous admin-role fallback ('admin always has finance') was
    removed. finance.mark_paid is a separate, load-bearing permission that must
    be granted explicitly in the JWT token — even for admins.

    Spec: admin role grants CRM management; it does NOT automatically grant
    the ability to approve payments. The finance team holds finance.mark_paid.
    """
    perms = user.get("permissions") or []
    if "finance.mark_paid" not in perms:
        raise HTTPException(status_code=403, detail="finance.mark_paid permission required")


def _sterilize_client_for_partner(full_name: str) -> str:
    """'Mario Rossi' → 'Mario R.' — hide client surname from partner-role user."""
    parts = full_name.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def _sterilize_service_type_for_partner(raw: str | None) -> str:
    """Map a raw service_type to a generic category for partner visibility.

    CRIT-6 / UU PDP data minimization: partner should know a referral converted,
    not which specific visa class / investment threshold / tax service was
    purchased. Revealing "KITAS E33G" tells a partner the client's residency
    plan; "PT PMA Rp 10M" reveals investment scale.

    Mapping is additive — add new keywords when new service types land.
    """
    if not raw:
        return "Service"
    rl = raw.lower()
    if any(k in rl for k in ("kitas", "visa", "c1", "c2", "c7", "e33", "e23", "e28")):
        return "Visa / KITAS service"
    if "kitap" in rl:
        return "KITAP service"
    if any(k in rl for k in ("pma", "company", "pt ", "perusahaan")):
        return "Company setup"
    if any(k in rl for k in ("tax", "pajak", "pph", "npwp")):
        return "Tax service"
    if any(k in rl for k in ("property", "sertifikat")):
        return "Property service"
    return "Other service"


def _partner_to_dict(p: Any) -> dict[str, Any]:
    """Convert Partner dataclass or asyncpg Record to JSON-serialisable dict."""
    if dataclasses.is_dataclass(p) and not isinstance(p, type):
        return dataclasses.asdict(p)
    return dict(p)


# Fields that must NOT appear in list-endpoint responses.
# They contain banking PII / tax identifiers that are only needed in the
# detail endpoint, which enforces verify_partner_access_with_role.
_SENSITIVE_PARTNER_FIELDS: frozenset[str] = frozenset({
    "npwp",
    "nik",
    "fiscal_address",
    "bank_name",
    "bank_account_holder",
    "bank_account_number",
    "ewallet_type",
    "ewallet_number",
    "iban",
    "payment_notes",
    "payment_currency",
})


def _partner_to_list_dict(p: Any) -> dict[str, Any]:
    """Partner → dict for LIST endpoints. Strips banking/tax PII.

    Sensitive fields require going to the detail endpoint, which has
    explicit access control via verify_partner_access_with_role.
    """
    d = _partner_to_dict(p)
    for field in _SENSITIVE_PARTNER_FIELDS:
        d.pop(field, None)
    return d


# ── Partner CRUD ─────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_partner(
    body: PartnerCreate,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Create a new partner. Team members auto-assign to themselves."""
    _require_team_or_admin(user)  # CATA-2: partner role cannot create partner records
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            data = body.model_dump(exclude_none=True)
            assigned_to = data.pop("assigned_to", None)
            # Team role: always scope to self (ignore any supplied assigned_to)
            if user.get("role") == "team":
                assigned_to = UUID(str(user["user_id"]))
            elif assigned_to is None and user.get("role") == "admin":
                assigned_to = None  # explicit None allowed for admin
            pid = await svc.create_partner(
                assigned_to=assigned_to,
                created_by=UUID(str(user["user_id"])),
                **data,
            )
            partner = await svc.repo.get_partner(pid)
            return _partner_to_dict(partner)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.get("")
async def list_partners(
    assigned_to: UUID | None = None,
    onboarding_status: str | None = None,
    orphaned: bool = False,
    search: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List partners. Team members see only their own.

    CATA-2: partner role blocked at router. Response strips sensitive
    fields (NPWP, NIK, bank/IBAN/e-wallet details) — use the detail
    endpoint for full data (which enforces verify_partner_access_with_role).
    """
    _require_team_or_admin(user)  # CATA-2: partner role cannot list all partners
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        partners = await svc.list_partners(
            actor_user=UUID(str(user["user_id"])),
            actor_role=user.get("role", "team"),
            assigned_to=assigned_to,
            onboarding_status=onboarding_status,
            orphaned=orphaned,
            search=search,
        )
        return [_partner_to_list_dict(p) for p in partners]


@router.get("/me")
async def me(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Self-view for partner-role users. Returns their own partner record."""
    if user.get("role") != "partner":
        raise HTTPException(status_code=403, detail="partner role required")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1",
            UUID(str(user["user_id"])),
        )
        if not row or not row["partner_id"]:
            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
        svc = PartnersService(conn)
        partner = await svc.repo.get_partner(row["partner_id"])
        if partner is None:
            raise HTTPException(status_code=404, detail="partner record not found")
        return _partner_to_dict(partner)


@router.get("/me/referrals")
async def me_referrals(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List referrals for the calling partner user. Client data is sterilized."""
    if user.get("role") != "partner":
        raise HTTPException(status_code=403, detail="partner role required")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1",
            UUID(str(user["user_id"])),
        )
        if not row or not row["partner_id"]:
            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
        partner_id = row["partner_id"]
        rows = await conn.fetch(
            """
            SELECT pr.id, pr.practice_id, pr.referred_at,
                   p.status AS process_status, p.service_type,
                   c.full_name AS client_name
            FROM partner_referrals pr
            LEFT JOIN practices p ON p.id = pr.practice_id
            LEFT JOIN clients c ON c.id = p.client_id
            WHERE pr.partner_id = $1
            ORDER BY pr.referred_at DESC
            """,
            partner_id,
        )
    return [
        {
            "id": str(r["id"]),
            "practice_id": str(r["practice_id"]),
            # CRIT-6: UU PDP Art 16 data minimization — raw service_type (e.g.
            # "KITAS E33G") reveals visa category / residency plan about the
            # referred client. Partner has legitimate interest in conversion but
            # not in the specific class. Map to generic category.
            "service_type": _sterilize_service_type_for_partner(r["service_type"]),
            "process_status": r["process_status"],  # TODO(CRIT-6 v1.1): consider sterilizing this too
            "client_display": _sterilize_client_for_partner(r["client_name"] or ""),
            "referred_at": r["referred_at"].isoformat() if r["referred_at"] else None,
        }
        for r in rows
    ]


@router.get("/me/commissions")
async def me_commissions(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List commissions for the calling partner user."""
    if user.get("role") != "partner":
        raise HTTPException(status_code=403, detail="partner role required")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1",
            UUID(str(user["user_id"])),
        )
        if not row or not row["partner_id"]:
            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
        svc = PartnersService(conn)
        commissions = await svc.repo.list_commissions_for_partner(row["partner_id"])
        return [
            dataclasses.asdict(c) if dataclasses.is_dataclass(c) else dict(c)
            for c in commissions
        ]


@router.get("/finance/export")
async def finance_export(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Finance CSV export. Admin + finance permission required."""
    _require_admin(user)
    _require_finance(user)
    # Validate ISO format before hitting SQL — bad input → 400 not 500
    try:
        datetime.fromisoformat(from_)
        datetime.fromisoformat(to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid date format (expected ISO): {e}")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT pc.id, p.full_name, p.npwp, p.entity_type,
                       pc.entry_type, pc.gross_amount_idr, pc.withholding_category,
                       pc.withholding_amount_idr, pc.net_amount_idr, pc.status,
                       pc.paid_at, pc.paid_via, pc.payment_reference
                FROM partner_commissions pc
                JOIN partners p ON p.id = pc.partner_id
                WHERE pc.created_at >= $1::timestamptz
                  AND pc.created_at <  $2::timestamptz
                ORDER BY pc.created_at ASC
                """,
                from_, to,
            )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "commission_id", "partner", "npwp", "entity_type", "entry_type",
            "gross_idr", "withholding_category", "withholding_idr", "net_idr",
            "status", "paid_at", "paid_via", "payment_reference",
        ])
        for r in rows:
            writer.writerow([r[k] for k in r.keys()])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="partners-{from_}-to-{to}.csv"'
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("finance_export failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/{partner_id}")
async def get_partner(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Get a partner by ID. Scoped by role."""
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        partner = await verify_partner_access_with_role(
            svc,
            UUID(str(user["user_id"])),
            user.get("role"),
            partner_id,
        )
        return _partner_to_dict(partner)


@router.patch("/{partner_id}")
async def update_partner(
    partner_id: UUID,
    body: PartnerUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Update a partner. Team members can only update their own assigned partners."""
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            fields = body.model_dump(exclude_none=True, exclude_unset=True)
            await svc.update_partner(
                partner_id,
                actor_user=UUID(str(user["user_id"])),
                actor_role=user.get("role", "team"),
                **fields,
            )
            partner = await svc.repo.get_partner(partner_id)
            return _partner_to_dict(partner)
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/{partner_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_partner(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Activate a partner. Admin only.

    CRIT-2: welcome email is enqueued atomically inside the same transaction
    that activates the partner. The send happens via /outbox/flush or cron.
    """
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            async with conn.transaction():
                await svc.activate_partner(
                    partner_id, actor_user=UUID(str(user["user_id"]))
                )
                from backend.services.crm.partners.emails import enqueue_welcome
                await enqueue_welcome(
                    conn, partner_id, actor_user=UUID(str(user["user_id"]))
                )
            return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("activate_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/{partner_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_partner(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Deactivate a partner. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.deactivate_partner(partner_id, actor_user=UUID(str(user["user_id"])))
            return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("deactivate_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/{partner_id}/reassign", status_code=status.HTTP_204_NO_CONTENT)
async def reassign_partner(
    partner_id: UUID,
    body: ReassignRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Reassign a partner to a different team member. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.reassign_partner(
                partner_id,
                new_user_id=body.new_user_id,
                actor_user=UUID(str(user["user_id"])),
                reason=body.reason,
            )
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("reassign_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/bulk-reassign", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_reassign(
    body: BulkReassignRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Bulk-reassign multiple partners to a single user. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            for pid in body.partner_ids:
                await svc.reassign_partner(
                    pid,
                    new_user_id=body.new_user_id,
                    actor_user=UUID(str(user["user_id"])),
                    reason=body.reason,
                )
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("bulk_reassign failed")
        raise HTTPException(status_code=500, detail="internal error")


# ── Referrals ────────────────────────────────────────────────────────────────

@router.get("/{partner_id}/referrals")
async def list_referrals(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List referrals for a partner. Scoped by role."""
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        await verify_partner_access_with_role(
            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
        )
        refs = await svc.repo.list_referrals_for_partner(partner_id)
        return [
            dataclasses.asdict(r) if dataclasses.is_dataclass(r) else dict(r)
            for r in refs
        ]


@router.post("/{partner_id}/referrals", status_code=status.HTTP_201_CREATED)
async def create_referral(
    partner_id: UUID,
    body: ReferralCreate,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Record a referral for a partner. Team (owner) or admin.

    CATA-3: verify_partner_access_with_role allowed actor_role='partner'
    (if user.partner_id == partner_id). A partner could POST to their own
    /referrals with any practice_id and trigger commission accrual for
    practices they never referred. Fraud vector — blocked here.

    Access rules:
    - partner role: always blocked (403).
    - team role: must own this partner (assigned_to == user_id) AND must
      own the referenced practice's client (client.assigned_to == user_id
      or fallback: practice exists — soft guard, team-or-admin is primary).
    - admin role: unrestricted.
    """
    _require_team_or_admin(user)  # CATA-3: partner role cannot self-assign to referrals
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)

            # Access check: team member must own this partner.
            partner = await svc.repo.get_partner(partner_id)
            if partner is None:
                raise HTTPException(status_code=404, detail="partner not found")
            if user["role"] == "team" and partner.assigned_to != UUID(str(user["user_id"])):
                raise HTTPException(
                    status_code=403,
                    detail="team members may only create referrals for partners they own",
                )

            # Practice ownership check: team member must own the referenced practice's client.
            if user["role"] == "team":
                practice_row = await conn.fetchrow(
                    "SELECT id, client_id FROM practices WHERE id = $1",
                    body.practice_id,
                )
                if practice_row is None:
                    raise HTTPException(status_code=404, detail="practice not found")
                if practice_row["client_id"] is not None:
                    client_row = await conn.fetchrow(
                        "SELECT assigned_to FROM clients WHERE id = $1",
                        practice_row["client_id"],
                    )
                    if (
                        client_row is not None
                        and client_row["assigned_to"] is not None
                        and str(client_row["assigned_to"]) != str(user["user_id"])
                    ):
                        raise HTTPException(
                            status_code=403,
                            detail="team members may only attach referrals to practices they own",
                        )

            rid = await svc.repo.insert_referral(
                partner_id=partner_id,
                practice_id=body.practice_id,
                referred_by_user_id=UUID(str(user["user_id"])),
                notes=body.notes,
            )
            return {"id": str(rid), "partner_id": str(partner_id), "practice_id": str(body.practice_id)}
    except HTTPException:
        raise
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="practice already has a referral")
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="practice already has a referral")
        logger.exception("create_referral failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.patch("/referrals/{referral_id}", status_code=status.HTTP_204_NO_CONTENT)
async def swap_referral(
    referral_id: UUID,
    body: ReferralSwap,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Swap a referral to a different partner. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.repo.update_referral_partner(referral_id, body.new_partner_id)
            return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("swap_referral failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.delete("/referrals/{referral_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_referral(
    referral_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Delete a referral. Admin only. Blocked if commissions exist."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.repo.delete_referral(referral_id)
            return Response(status_code=204)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception:
        logger.exception("delete_referral failed")
        raise HTTPException(status_code=500, detail="internal error")


# ── Commissions ───────────────────────────────────────────────────────────────

@router.get("/{partner_id}/commissions")
async def list_commissions(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List commissions for a partner. Scoped by role."""
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        await verify_partner_access_with_role(
            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
        )
        commissions = await svc.repo.list_commissions_for_partner(partner_id)
        return [
            dataclasses.asdict(c) if dataclasses.is_dataclass(c) else dict(c)
            for c in commissions
        ]


@router.get("/{partner_id}/audit-log")
async def list_partner_audit_log(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List the audit log for a partner. Admin or team-owner only."""
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await verify_partner_access_with_role(svc, UUID(str(user["user_id"])), user.get("role"), partner_id)
            entries = await svc.list_audit(partner_id)
            return [_partner_to_dict(e) for e in entries]
    except HTTPException:
        raise
    except Exception:
        logger.exception("list_partner_audit_log failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_commission(
    commission_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Approve a commission. Admin + finance permission."""
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            await engine.approve(commission_id, actor=UUID(str(user["user_id"])))
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("approve_commission failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/mark-paid", status_code=status.HTTP_204_NO_CONTENT)
async def mark_paid_commission(
    commission_id: UUID,
    body: CommissionMarkPaidRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Mark a commission as paid. Admin + finance permission.

    CRIT-2: commission-earned email is enqueued atomically inside the same
    transaction that flips status to 'paid'. The send happens via /outbox/flush
    or cron — eliminating the window where a Brevo failure could leave the
    commission stuck in 'paid' with the email permanently lost (FSM blocks
    paid->paid retry).
    """
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            async with conn.transaction():
                await engine.mark_paid(
                    commission_id,
                    actor=UUID(str(user["user_id"])),
                    paid_via=body.paid_via,
                    payment_reference=body.payment_reference,
                    payment_proof_url=body.payment_proof_url,
                    receipt_type=body.receipt_type,
                    receipt_file_url=body.receipt_file_url,
                )
                from backend.services.crm.partners.emails import enqueue_commission_earned
                await enqueue_commission_earned(
                    conn, commission_id, actor_user=UUID(str(user["user_id"]))
                )
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("mark_paid_commission failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/outbox/flush")
async def flush_email_outbox(
    limit: int = 50,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Synchronously send pending outbox emails. Admin + finance only.

    v1: synchronous — suitable for manual retries and cron.
    v2 will replace with an async worker process.

    Returns: {'sent': N, 'retried': N, 'dlq': N}
    """
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            from backend.services.crm.partners.emails import flush_outbox
            return await flush_outbox(conn, limit=limit)
    except HTTPException:
        raise
    except Exception:
        logger.exception("flush_email_outbox failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/clawback", status_code=status.HTTP_201_CREATED)
async def clawback_commission(
    commission_id: UUID,
    body: ClawbackRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Initiate a clawback on a commission. Admin + finance permission. Returns new commission id."""
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            cid = await engine.clawback(
                commission_id,
                actor=UUID(str(user["user_id"])),
                reason=body.reason,
                amount_idr=body.amount_idr,
            )
            return {"id": str(cid)}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("clawback_commission failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/waive", status_code=status.HTTP_204_NO_CONTENT)
async def waive_commission(
    commission_id: UUID,
    body: WaiveRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Waive a clawback on a commission. Admin + finance permission."""
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            await engine.waive_clawback(
                commission_id,
                actor=UUID(str(user["user_id"])),
                reason=body.reason,
            )
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("waive_commission failed")
        raise HTTPException(status_code=500, detail="internal error")
