"""
LKPM (Investment Activity Report) Router.

Endpoints for generating, validating, and managing quarterly LKPM reports.
All calculations are deterministic — no AI on numbers.
"""

import logging
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.models.lkpm import (
    LKPMClientConfig,
    LKPMClientSubmission,
)
from backend.app.utils.crm_utils import is_crm_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lkpm", tags=["lkpm"])


def _safe_lkpm_failure(
    operation: str,
    error: Exception,
    client_message: str,
) -> HTTPException:
    """Create a correlation-safe 500 without logging exception contents."""
    error_ref = uuid4().hex
    logger.error(
        "LKPM operation failed operation=%s error_ref=%s error_type=%s",
        operation,
        error_ref,
        type(error).__name__,
    )
    return HTTPException(
        status_code=500,
        detail=f"{client_message}. Reference: {error_ref}",
    )


# Allowed tax team emails that can be assigned to an LKPM report.
# Kept in sync with crm_clients.TAX_CONSULTANT_VALUES and the DB CHECK
# constraint from migration 093. Adding a new consultant requires updating
# all three (Python model + CRM router + DB migration).
LKPM_ASSIGNEES: set[str] = {
    "veronika.tax@balizero.com",
    "kadek.tax@balizero.com",
    "dewaayu.tax@balizero.com",
    "angel.tax@balizero.com",
    "faisha.tax@balizero.com",
    # Krisna is the Executive Consultant who owns 4 PTs in the PDF Q1 2026
    # handover ("Handle BY: Krisna"). He doesn't have a .tax@ sub-alias,
    # so we whitelist his main inbox.
    "krisna@balizero.com",
}


class LKPMAssignBody(BaseModel):
    """Request body for PUT /lkpm/reports/{id}/assign."""

    lkpm_assigned_to: str | None = None

    @field_validator("lkpm_assigned_to")
    @classmethod
    def _validate_assignee(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if v not in LKPM_ASSIGNEES:
            raise ValueError(
                f"lkpm_assigned_to must be one of {sorted(LKPM_ASSIGNEES)} or null, got '{v}'",
            )
        return v


def _get_service(db_pool: asyncpg.Pool) -> Any:
    """Lazy import to avoid circular deps at startup."""
    from backend.services.compliance.lkpm_service import LKPMService

    return LKPMService(db_pool)


def _require_user_context(current_user: Any) -> dict[str, Any]:
    """Return a verified JWT principal instead of trusting a scalar dependency result."""
    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Invalid authentication context")
    return current_user


def _is_lkpm_staff(user: dict[str, Any]) -> bool:
    """Limit cross-client LKPM operations to CRM admins and the tax team."""
    email = str(user.get("email") or "").strip().lower()
    return is_crm_admin(user) or email in LKPM_ASSIGNEES


def _require_lkpm_staff(current_user: Any, *, conceal_target: bool = True) -> dict[str, Any]:
    """Authorize a workspace LKPM actor before any target-specific lookup.

    Portal clients receive the same 404 for every caller-supplied identifier so
    the endpoint cannot be used as an object-existence oracle.
    """
    user = _require_user_context(current_user)
    if _is_lkpm_staff(user):
        return user
    if conceal_target and str(user.get("role") or "").lower() == "client":
        raise HTTPException(status_code=404, detail="LKPM target not found")
    raise HTTPException(status_code=403, detail="Not authorized for LKPM staff operation")


_CLIENT_RECEIPT_FIELDS = (
    "id",
    "lkpm_report_id",
    "nomor_laporan",
    "nomor_kegiatan_usaha",
    "kbli_code",
    "kegiatan_usaha_desc",
    "stage",
    "oss_status",
    "lokasi",
    "tanggal_diterima",
    "nama_perusahaan_oss",
    "file_name",
    "quarter",
    "year",
    "client_id",
    "company_id",
    "company_name",
)


def _client_safe_receipt(item: dict[str, Any]) -> dict[str, Any]:
    """Allowlist the portal receipt contract and replace Drive data with a proxy URL."""
    projected = {key: item.get(key) for key in _CLIENT_RECEIPT_FIELDS if key in item}
    has_download = bool(item.get("file_drive_id") or item.get("file_drive_url"))
    projected["download_url"] = (
        f"/api/v1/lkpm/receipts/{item['id']}/download" if has_download else None
    )
    return projected


# ------------------------------------------------------------------
# Client Config
# ------------------------------------------------------------------


@router.post("/config", response_model=dict)
async def save_client_config(
    config: LKPMClientConfig,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Save or update LKPM client configuration (investment plan, Jurnal keys)."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    try:
        config_id = await service.save_client_config(config)
        return {"success": True, "config_id": config_id}
    except Exception as e:
        raise _safe_lkpm_failure(
            "save_client_config",
            e,
            "LKPM configuration temporarily unavailable",
        ) from e


# ------------------------------------------------------------------
# Data Submission
# ------------------------------------------------------------------


@router.post("/submit-data", response_model=dict)
async def submit_data(
    submission: LKPMClientSubmission,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Submit LKPM data for a portal client or a verified CRM admin."""
    from backend.services.compliance.lkpm_service import LKPMDraftLockedError

    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Invalid authentication context")

    is_admin = is_crm_admin(current_user)
    role = (current_user.get("role") or "").lower()
    if role != "client" and not is_admin:
        raise HTTPException(status_code=403, detail="This endpoint is only accessible to clients")

    service = _get_service(db_pool)
    try:
        if is_admin:
            draft = await service.submit_form_data_for_admin(submission)
        else:
            user_id = current_user.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found in token")
            authenticated_client_id = await service.resolve_portal_client_id(str(user_id))
            if authenticated_client_id is None:
                raise HTTPException(
                    status_code=403, detail="Client account is not active or linked"
                )
            draft = await service.submit_form_data_for_client(
                submission,
                authenticated_client_id=authenticated_client_id,
            )
        return {
            "success": True,
            "draft_id": draft.id,
            "quarter": draft.quarter,
            "year": draft.year,
            "realized_total": draft.realized.grand_total,
        }
    except LookupError as e:
        raise HTTPException(status_code=404, detail="LKPM submission target not found") from e
    except LKPMDraftLockedError as e:
        raise HTTPException(
            status_code=409,
            detail="This LKPM report is locked after approval or OSS submission",
        ) from e
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid LKPM submission data") from e
    except Exception as e:
        raise _safe_lkpm_failure(
            "submit_data",
            e,
            "LKPM submission temporarily unavailable",
        ) from e


@router.post("/sync-jurnal/{client_id}", response_model=dict)
async def sync_jurnal(
    client_id: int,
    quarter: str,
    year: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Pull data from Jurnal.id and create/update LKPM draft."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    try:
        draft = await service.sync_jurnal(client_id, quarter, year)
        return {
            "success": True,
            "draft_id": draft.id,
            "realized_total": draft.realized.grand_total,
            "ai_categorized_count": draft.ai_categorized_count,
            "data_source": draft.data_source.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid LKPM synchronization request") from e
    except Exception as e:
        raise _safe_lkpm_failure(
            "sync_jurnal",
            e,
            "LKPM synchronization temporarily unavailable",
        ) from e


# ------------------------------------------------------------------
# Draft Management
# ------------------------------------------------------------------


@router.get("/draft/{client_id}/{quarter}", response_model=dict)
async def get_draft(
    client_id: int,
    quarter: str,
    request: Request,
    year: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get LKPM draft for a client/quarter.

    Resolution rules for ``client_id``:
      * ``client_id > 0`` — staff may select it; clients may only use their
        server-resolved own id.
      * ``client_id = 0`` + ``role='client'`` — resolve from the JWT user id
        and active portal linkage (shareholders don't know their numeric id).
      * ``client_id = 0`` + superuser (zero@balizero.com) + ``?as_client=<id>``
        — override to the requested id (admin impersonation, also honored as
        the new ``/draft/0/...`` convention everywhere).
    """
    user = _require_user_context(current_user)
    service = _get_service(db_pool)
    role = str(user.get("role") or "").lower()

    if role == "client":
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=404, detail="Draft not found")
        authenticated_client_id = await service.resolve_portal_client_id(str(user_id))
        if authenticated_client_id is None or client_id not in {0, authenticated_client_id}:
            raise HTTPException(status_code=404, detail="Draft not found")
        client_id = authenticated_client_id
    elif _is_lkpm_staff(user):
        if client_id == 0:
            from backend.app.routers.portal import _superuser_emails

            email = str(user.get("email") or "").lower()
            if email not in _superuser_emails():
                raise HTTPException(status_code=422, detail="Use an explicit client id")
            as_client_raw = request.query_params.get("as_client")
            if not as_client_raw:
                raise HTTPException(
                    status_code=422,
                    detail="Superuser: pass ?as_client=<id> to select a client",
                )
            try:
                client_id = int(as_client_raw)
            except ValueError as e:
                raise HTTPException(status_code=400, detail="as_client must be int") from e
    else:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft = await service.get_draft(client_id, quarter, year)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"success": True, "draft": draft.model_dump()}


@router.post("/validate/{draft_id}", response_model=dict)
async def validate_draft(
    draft_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Validate an LKPM draft."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    try:
        result = await service.validate_draft(draft_id)
        return {
            "success": True,
            "is_valid": result.is_valid,
            "red_count": result.red_count,
            "yellow_count": result.yellow_count,
            "green_count": result.green_count,
            "alerts": [a.model_dump() for a in result.alerts],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail="LKPM draft not found") from e
    except Exception as e:
        raise _safe_lkpm_failure(
            "validate_draft",
            e,
            "LKPM validation temporarily unavailable",
        ) from e


# ------------------------------------------------------------------
# Ready Pack
# ------------------------------------------------------------------


@router.get("/ready-pack/{draft_id}", response_model=dict)
async def get_ready_pack(
    draft_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Generate Ready Pack for OSS copy-paste."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    try:
        pack = await service.get_ready_pack(draft_id)

        # Generate HTML
        from backend.services.compliance.lkpm_ready_pack import generate_ready_pack_html

        html = generate_ready_pack_html(pack)
        pack.html_content = html

        return {
            "success": True,
            "ready_pack": pack.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail="LKPM draft not found") from e
    except Exception as e:
        raise _safe_lkpm_failure(
            "get_ready_pack",
            e,
            "LKPM ready pack temporarily unavailable",
        ) from e


# ------------------------------------------------------------------
# Approval & Submission
# ------------------------------------------------------------------


@router.post("/approve/{draft_id}", response_model=dict)
async def approve_draft(
    draft_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Approve an owned LKPM draft, with the existing CRM-admin override."""
    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Invalid authentication context")

    service = _get_service(db_pool)
    is_admin = is_crm_admin(current_user)
    authenticated_client_id: int | None = None

    if not is_admin:
        if (current_user.get("role") or "").lower() != "client":
            raise HTTPException(status_code=404, detail="LKPM draft not found")
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        authenticated_client_id = await service.resolve_portal_client_id(str(user_id))
        if authenticated_client_id is None:
            raise HTTPException(status_code=404, detail="LKPM draft not found")

    try:
        return await service.approve_draft_for_actor(
            draft_id,
            authenticated_client_id=authenticated_client_id,
            is_admin=is_admin,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail="LKPM draft not found") from e
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_lkpm_failure(
            "approve_draft",
            e,
            "LKPM approval temporarily unavailable",
        ) from e


@router.post("/mark-submitted/{draft_id}", response_model=dict)
async def mark_submitted(
    draft_id: int,
    submitted_by: str | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Team marks LKPM as submitted to OSS."""
    actor = _require_lkpm_staff(current_user)
    actor_email = str(actor.get("email") or "").strip().lower()
    service = _get_service(db_pool)
    try:
        # Keep the legacy query parameter for compatibility, but never trust it
        # for audit attribution: the authenticated principal owns the mutation.
        _ = submitted_by
        return await service.mark_submitted(draft_id, actor_email)
    except LookupError as e:
        raise HTTPException(status_code=404, detail="LKPM draft not found") from e
    except Exception as e:
        raise _safe_lkpm_failure(
            "mark_submitted",
            e,
            "LKPM submission status temporarily unavailable",
        ) from e


@router.post("/upload-receipt/{draft_id}", response_model=dict)
async def upload_receipt(
    draft_id: int,
    receipt_number: str,
    receipt_file_url: str | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Upload OSS receipt for a submitted LKPM."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    try:
        return await service.upload_receipt(draft_id, receipt_number, receipt_file_url)
    except LookupError as e:
        raise HTTPException(status_code=404, detail="LKPM draft not found") from e
    except Exception as e:
        raise _safe_lkpm_failure(
            "upload_receipt",
            e,
            "LKPM receipt upload temporarily unavailable",
        ) from e


# ------------------------------------------------------------------
# Portal: Shareholder History
# ------------------------------------------------------------------


@router.get("/history/me", response_model=dict)
async def get_my_history(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get LKPM reports for the authenticated portal client (all shareholder companies)."""
    from backend.app.routers.portal import get_current_client

    client = await get_current_client(request, db_pool)
    service = _get_service(db_pool)
    try:
        items = await service.get_history_for_portal_client(client["client_id"])
        return {
            "success": True,
            "client_id": client["client_id"],
            "count": len(items),
            "items": [item.model_dump() for item in items],
        }
    except Exception as e:
        raise _safe_lkpm_failure(
            "get_my_history",
            e,
            "LKPM history temporarily unavailable",
        ) from e


@router.get("/receipts/me", response_model=dict)
async def get_my_receipts(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Portal: OSS tanda terima for every company where the authenticated client
    is a shareholder (via client_company_links). Mirrors /history/me but at
    the receipt granularity.
    """
    from backend.app.routers.portal import get_current_client

    client = await get_current_client(request, db_pool)
    service = _get_service(db_pool)
    try:
        raw_items = await service.get_receipts_for_portal_client(client["client_id"])
        items = [_client_safe_receipt(item) for item in raw_items]
        return {
            "success": True,
            "client_id": client["client_id"],
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        raise _safe_lkpm_failure(
            "get_my_receipts",
            e,
            "LKPM receipts temporarily unavailable",
        ) from e


@router.get("/receipts/{receipt_id}/download")
async def download_my_receipt(
    receipt_id: int,
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Download a tenant-owned LKPM receipt through the client-safe proxy."""
    from backend.app.routers.portal import get_current_client

    client = await get_current_client(request, db_pool)
    service = _get_service(db_pool)
    try:
        receipt = await service.download_receipt_for_portal_client(
            client["client_id"],
            receipt_id,
        )
        if receipt is None:
            raise HTTPException(status_code=404, detail="Receipt not found or not downloadable")

        file_name = receipt["file_name"]
        return Response(
            content=receipt["content"],
            media_type=receipt["mime_type"],
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _safe_lkpm_failure(
            "download_my_receipt",
            e,
            "LKPM receipt download temporarily unavailable",
        ) from e


# Order matters: /receipts/by-client/{id} must precede /receipts/{id}, otherwise
# FastAPI binds "by-client" as the int path param of get_receipts_for_report.
@router.get("/receipts/by-client/{client_id}", response_model=dict)
async def get_receipts_by_client(
    client_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Workspace TaxTab: OSS tanda terima across every company where the client
    is a shareholder (via client_company_links). Staff-authenticated; the
    portal equivalent is GET /receipts/me.
    """
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    try:
        items = await service.get_receipts_for_client(client_id)
        return {
            "success": True,
            "client_id": client_id,
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        raise _safe_lkpm_failure(
            "get_receipts_by_client",
            e,
            "LKPM receipts temporarily unavailable",
        ) from e


@router.get("/receipts/{lkpm_report_id}", response_model=dict)
async def get_receipts_for_report(
    lkpm_report_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Workspace: OSS tanda terima attached to a single lkpm_reports row."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    try:
        items = await service.get_receipts_for_report(lkpm_report_id)
        return {
            "success": True,
            "lkpm_report_id": lkpm_report_id,
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        raise _safe_lkpm_failure(
            "get_receipts_for_report",
            e,
            "LKPM receipts temporarily unavailable",
        ) from e


# ------------------------------------------------------------------
# Batch & Queries
# ------------------------------------------------------------------


@router.get("/batch/{quarter}", response_model=dict)
async def get_batch(
    quarter: str,
    year: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get all LKPM reports for a quarter (team batch view)."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    items = await service.get_batch(quarter, year)
    return {
        "success": True,
        "quarter": quarter,
        "year": year,
        "count": len(items),
        "items": [item.model_dump() for item in items],
    }


@router.get("/alerts", response_model=dict)
async def get_alerts(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get active validation alerts across all clients."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    alerts = await service.get_alerts()
    return {"success": True, "alerts": alerts}


@router.get("/history/{client_id}", response_model=dict)
async def get_history(
    client_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get LKPM report history for a client."""
    _require_lkpm_staff(current_user)
    service = _get_service(db_pool)
    items = await service.get_history(client_id)
    return {
        "success": True,
        "client_id": client_id,
        "count": len(items),
        "items": [item.model_dump() for item in items],
    }


@router.get("/deadlines", response_model=dict)
async def get_deadlines(
    days_ahead: int = 30,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get upcoming LKPM deadlines."""
    service = _get_service(db_pool)
    deadlines = service.get_deadlines(days_ahead)
    return {
        "success": True,
        "deadlines": [d.model_dump() for d in deadlines],
    }


# ------------------------------------------------------------------
# Assignment & OSS credentials (Q1 2026 rollout)
# ------------------------------------------------------------------


@router.put("/reports/{draft_id}/assign", response_model=dict)
async def assign_lkpm_report(
    draft_id: int,
    body: LKPMAssignBody = Body(...),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Assign (or unassign) an LKPM report to a tax consultant.

    RBAC: any CRM admin OR any of the 5 tax consultants in LKPM_ASSIGNEES.
    The tax team is collaborative — Veronika/Kadek/Dewa Ayu/Angel/Faisha
    can re-route reports between themselves without going through an admin.
    Users outside both groups get 403.

    Body:
        lkpm_assigned_to: one of LKPM_ASSIGNEES or null to clear.
    """
    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Invalid authentication context")

    user_email = (current_user.get("email") or "").lower()
    is_admin = is_crm_admin(current_user)
    is_tax_consultant = user_email in LKPM_ASSIGNEES

    if not (is_admin or is_tax_consultant):
        raise HTTPException(
            status_code=403,
            detail="Only CRM admins or tax consultants can assign LKPM reports",
        )

    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, client_id, quarter, year, lkpm_assigned_to FROM lkpm_reports WHERE id = $1",
            draft_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"LKPM draft {draft_id} not found")

        await conn.execute(
            """
            UPDATE lkpm_reports
            SET lkpm_assigned_to = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            body.lkpm_assigned_to,
            draft_id,
        )

    logger.info(
        f"LKPM assign: draft_id={draft_id} -> {body.lkpm_assigned_to} "
        f"(by={current_user.get('email') if isinstance(current_user, dict) else 'unknown'})",
    )
    return {
        "success": True,
        "draft_id": draft_id,
        "lkpm_assigned_to": body.lkpm_assigned_to,
    }


@router.get("/credentials/{client_id}", response_model=dict)
async def get_oss_credentials(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Return OSS plaintext credentials for a company.

    User explicitly requested plaintext storage + plaintext retrieval; the
    team accesses credentials from the workspace and the client from their
    portal. No Fernet encryption, no per-access audit row.

    RBAC (any of):
      - admin
      - the tax consultant currently assigned to ANY Q1/2026 report of that client
    """
    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Invalid authentication context")

    user_email = (current_user.get("email") or "").lower()
    is_admin = is_crm_admin(current_user)
    is_tax_consultant = user_email in LKPM_ASSIGNEES

    # The tax team is collaborative: any of the 5 tax consultants can read
    # credentials for any PMA, regardless of who is assigned to a specific
    # report. Avoids the catch-22 where consultants couldn't read until an
    # admin assigned them. Admins also pass.
    if not (is_admin or is_tax_consultant):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view OSS credentials",
        )

    async with db_pool.acquire() as conn:
        cfg = await conn.fetchrow(
            """
            SELECT oss_username, oss_password, oss_creds_updated_at, oss_creds_updated_by, company_name
            FROM lkpm_client_config
            WHERE client_id = $1
            """,
            client_id,
        )
        if not cfg:
            raise HTTPException(
                status_code=404, detail=f"LKPM config for client_id={client_id} not found"
            )

    return {
        "success": True,
        "client_id": client_id,
        "company_name": cfg["company_name"],
        "oss_username": cfg["oss_username"],
        "oss_password": cfg["oss_password"],
        "oss_creds_updated_at": cfg["oss_creds_updated_at"].isoformat()
        if cfg["oss_creds_updated_at"]
        else None,
        "oss_creds_updated_by": cfg["oss_creds_updated_by"],
    }


# ------------------------------------------------------------------
# Ready-Pack Automation — POST /ready-pack/{client_id}  (Task 6)
# ------------------------------------------------------------------


class ReadyPackBody(BaseModel):
    """Request body for POST /lkpm/ready-pack/{client_id}."""

    period: str  # e.g. "Q1 2026"
    send_email: bool = True
    dry_run: bool = False


@router.post("/ready-pack/{client_id}", response_model=dict)
async def generate_ready_pack_pdf(
    client_id: int,
    body: ReadyPackBody = Body(...),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Generate a LKPM ready-pack (PDF + XLSX), upload to Google Drive,
    and optionally email the client via Brevo.

    RBAC:
      - Admin: full access.
      - Team (non-admin): only if lkpm_reports.lkpm_assigned_to = user email
        AND lkpm_assigned_to IS NOT NULL. Null-assigned reports are blocked.

    Body:
      period: "Q1 2026" (required — returns 400 if missing/blank).
      send_email: default True.
      dry_run: skip Drive + email, return hashes only.

    Returns 422 if LKPM completeness validation fails.
    Returns 403 if team member is not the report assignee.
    """
    from backend.services.compliance.exceptions import LkpmValidationError
    from backend.services.compliance.lkpm_ready_pack import LkpmReadyPack

    current_user = _require_lkpm_staff(current_user)

    period = (body.period or "").strip()
    if not period:
        raise HTTPException(status_code=400, detail="period is required")

    user_email: str = (current_user.get("email") or "").lower()
    is_admin: bool = is_crm_admin(current_user)

    # ── RBAC: team-level scoping ──────────────────────────────────────
    if not is_admin:
        # Resolve quarter/year for lookup
        parts = period.split()
        if len(parts) != 2 or parts[0] not in {"Q1", "Q2", "Q3", "Q4"}:
            raise HTTPException(
                status_code=400,
                detail="period must be 'Q1|Q2|Q3|Q4 YYYY'",
            )
        try:
            year = int(parts[1])
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Year in period must be an integer"
            ) from exc

        async with db_pool.acquire() as conn:
            assigned_to = await conn.fetchval(
                """
                SELECT lkpm_assigned_to
                FROM lkpm_reports
                WHERE client_id = $1 AND quarter = $2 AND year = $3
                LIMIT 1
                """,
                client_id,
                parts[0],
                year,
            )

        # Null assigned_to → 403 (Task 4 pattern: null-deny for team)
        if assigned_to is None or assigned_to.lower() != user_email:
            raise HTTPException(
                status_code=403,
                detail="Not authorised: report is not assigned to you",
            )

    # ── Lazy-import integration services (graceful degradation) ──────
    drive_service = None
    brevo_service = None

    try:
        from backend.services.integrations.google_drive_service import (
            GoogleDriveService,
        )

        drive_service = GoogleDriveService(db_pool)
    except (ImportError, Exception):
        logger.warning("lkpm ready-pack: GoogleDriveService unavailable — Drive upload skipped")

    # Brevo is invoked via LkpmReadyPack._send_brevo_direct (no class needed)

    # ── Generate ──────────────────────────────────────────────────────
    try:
        pack = LkpmReadyPack(db_pool=db_pool, drive=drive_service, brevo=brevo_service)
        result = await pack.generate(
            client_id=client_id,
            period=period,
            send_email=body.send_email,
            dry_run=body.dry_run,
        )
        return {"success": True, **result}
    except LkpmValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="LKPM ready pack is incomplete",
        ) from exc
    except Exception as exc:
        raise _safe_lkpm_failure(
            "generate_oss_ready_pack",
            exc,
            "LKPM ready pack temporarily unavailable",
        ) from exc
