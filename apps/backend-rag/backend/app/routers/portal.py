"""
ZANTARA Client Portal - Main Router

Client-facing portal endpoints for:
- Dashboard overview
- Visa & Immigration status
- Company & Licenses
- Tax overview
- Documents
- Messages
- Settings/Preferences

All endpoints require client authentication (role='client').

Created: 2025-12-30
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.core.cache import invalidate_cache
from backend.services.portal import PortalService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal", tags=["portal"])


# ================================================
# PYDANTIC MODELS
# ================================================


class SendMessageRequest(BaseModel):
    """Request to send a message"""

    content: str
    subject: str | None = None
    practice_id: int | None = None


class UpdatePreferencesRequest(BaseModel):
    """Request to update preferences"""

    email_notifications: bool | None = None
    whatsapp_notifications: bool | None = None
    language: str | None = None
    timezone: str | None = None


class PortalResponse(BaseModel):
    """Standard portal response"""

    success: bool
    data: dict | list | None = None
    message: str | None = None


# ================================================
# CLIENT AUTHENTICATION DEPENDENCY
# ================================================


# Superusers that can impersonate any client via ?as_client=<id>.
# Sourced from settings.admin_emails_set (HIGH-7, audit 2026-04-18) — was
# previously hardcoded to {"zero@balizero.com"}. Using a getter so ADMIN_EMAILS
# env var changes propagate without a module reload.
def _superuser_emails() -> frozenset[str]:
    return settings.admin_emails_set


async def _log_impersonation(
    conn: asyncpg.Connection,
    actor_email: str,
    actor_user_id: str | None,
    target_client_id: int,
    path: str,
) -> None:
    """Best-effort audit log for a superuser viewing another client's data."""
    try:
        from backend.services.security.audit_service import SecurityAuditService

        await SecurityAuditService().log_event(
            conn=conn,
            action="portal_impersonation",
            user_email=actor_email,
            user_id=actor_user_id,
            resource_type="client",
            resource_id=str(target_client_id),
            success=True,
            details={"path": path},
        )
    except Exception as e:  # never fail the request because audit broke
        logger.warning(f"impersonation audit log failed: {e}")


async def get_current_client(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Get current authenticated client from JWT token.

    Requires:
    - Valid JWT token (from middleware)
    - role = 'client' (bypassed for superusers — see SUPERUSER_EMAILS)
    - linked_client_id set (bypassed for superusers using ?as_client=<id>)

    Superuser impersonation:
        When the JWT belongs to a SUPERUSER_EMAILS account, a query string
        ?as_client=<client_id> overrides the normal lookup and the handler
        operates as if the caller were that client. Each hit is audit-logged
        (security_audit_log action='portal_impersonation').

    Returns:
        dict with: client_id, user_id, email, name, impersonating (bool)
    """
    # Get user from middleware
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = request.state.user
    user_email = (user.get("email") or "").lower()
    user_id = user.get("id") or user.get("user_id")
    is_superuser = user_email in _superuser_emails()

    # ---- Superuser impersonation path ----
    if is_superuser:
        as_client_raw = request.query_params.get("as_client")
        if not as_client_raw:
            # Superuser without as_client → fall through to normal lookup so
            # zero@ can still see their own linked profile if any. If they
            # don't have one (most likely) we 422 with a helpful message.
            async with db_pool.acquire() as conn:
                own = await conn.fetchrow(
                    "SELECT id, email, full_name FROM clients WHERE LOWER(email) = LOWER($1)",
                    user_email,
                )
            if own:
                return {
                    "client_id": own["id"],
                    "user_id": str(user_id) if user_id else user_email,
                    "email": own["email"],
                    "name": own["full_name"],
                    "impersonating": False,
                }
            raise HTTPException(
                status_code=422,
                detail="Superuser: select a client via ?as_client=<id>",
            )

        try:
            as_client_id = int(as_client_raw)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail="as_client must be an integer",
            ) from e

        async with db_pool.acquire() as conn:
            target = await conn.fetchrow(
                "SELECT id, email, full_name FROM clients WHERE id = $1",
                as_client_id,
            )
            if not target:
                raise HTTPException(
                    status_code=404,
                    detail=f"Client {as_client_id} not found",
                )
            await _log_impersonation(
                conn=conn,
                actor_email=user_email,
                actor_user_id=str(user_id) if user_id else None,
                target_client_id=as_client_id,
                path=str(request.url.path),
            )

        return {
            "client_id": target["id"],
            "user_id": str(user_id) if user_id else user_email,
            "email": target["email"],
            "name": target["full_name"],
            "impersonating": True,
        }

    # ---- Normal client path ----
    # Check role is client
    if user.get("role") != "client":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only accessible to clients",
        )

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID not found in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, email, full_name, linked_client_id, portal_access
            FROM team_members
            WHERE id = $1 AND role = 'client' AND active = true
            """,
            str(user_id),  # UUID as string, not int
        )

        if not row:
            raise HTTPException(
                status_code=403,
                detail="Client account not found or inactive",
            )

        if not row["portal_access"]:
            raise HTTPException(
                status_code=403,
                detail="Portal access not enabled for this account",
            )

        if not row["linked_client_id"]:
            raise HTTPException(
                status_code=403,
                detail="Client profile not linked to account",
            )

        return {
            "client_id": row["linked_client_id"],
            "user_id": row["id"],
            "email": row["email"],
            "name": row["full_name"],
            "impersonating": False,
        }


def get_portal_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> PortalService:
    """Dependency injection for PortalService"""
    return PortalService(db_pool)


# ================================================
# DASHBOARD ENDPOINTS
# ================================================


@router.get("/dashboard")
async def get_dashboard(
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get client dashboard overview.

    Returns summary of:
    - Active visa status
    - Company status
    - Tax status
    - Pending documents
    - Unread messages
    - Required actions
    """
    try:
        data = await portal_service.get_dashboard(
            client["client_id"],
            current_user=client,
        )
        return {
            "success": True,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard",
        ) from e


# ================================================
# VISA & IMMIGRATION ENDPOINTS
# ================================================


@router.get("/visa")
async def get_visa_status(
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get visa and immigration status.

    Returns:
    - Current visa details
    - Visa history
    - Immigration documents
    - Renewal warnings
    """
    try:
        data = await portal_service.get_visa_status(
            client["client_id"],
            current_user=client,
        )
        return {
            "success": True,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Failed to get visa status for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load visa information",
        ) from e


# ================================================
# COMPANY ENDPOINTS
# ================================================


@router.get("/companies")
async def get_companies(
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get list of client's companies.

    For multi-company support - returns all linked companies.
    """
    try:
        companies = await portal_service.get_companies(
            client["client_id"],
            current_user=client,
        )
        return {
            "success": True,
            "data": companies,
        }
    except Exception as e:
        logger.error(f"Failed to get companies for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load companies",
        ) from e


@router.get("/company/{company_id}")
async def get_company_detail(
    company_id: int,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get detailed company information.

    Returns:
    - Company profile
    - License status
    - Compliance calendar
    - Related documents
    """
    try:
        data = await portal_service.get_company_detail(
            client["client_id"],
            company_id,
            current_user=client,
        )
        if data is None:
            raise HTTPException(
                status_code=404,
                detail="Company not found or not accessible",
            )
        # Map snake_case → camelCase for frontend PortalCompany type.
        # Defensive: `ownership` can be None when the link row was deleted;
        # `data.get("ownership", {})` returns None (not {}) in that case,
        # which would then crash on `.get("is_primary")`.
        ownership = data.get("ownership") or {}
        data["isPrimary"] = ownership.get("is_primary", False)
        data["aktaNo"] = data.pop("akta_no", None)
        data["aktaDate"] = data.pop("akta_date", None)
        data["skNumber"] = data.pop("sk_number", None)
        data["taxOffice"] = data.pop("tax_office", None)
        data["companyStatus"] = data.pop("company_status", None)
        data["investmentType"] = data.pop("investment_type", None)
        data["authorizedCapital"] = data.pop("authorized_capital", None)
        return {
            "success": True,
            "data": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get company {company_id} for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load company information",
        ) from e


@router.post("/company/{company_id}/select")
async def set_primary_company(
    company_id: int,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Set primary company for dashboard context.
    """
    try:
        result = await portal_service.set_primary_company(
            client["client_id"],
            company_id,
            current_user=client,
        )
        return {
            "success": True,
            "message": "Primary company updated",
            "data": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to set primary company: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update primary company",
        ) from e


# ================================================
# TAX ENDPOINTS
# ================================================


@router.get("/taxes")
async def get_tax_overview(
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get tax overview and calendar.

    Returns:
    - Tax obligations status
    - Upcoming deadlines
    - Tax history
    """
    try:
        data = await portal_service.get_tax_overview(
            client["client_id"],
            current_user=client,
        )
        return {
            "success": True,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Failed to get tax overview for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load tax information",
        ) from e


# ================================================
# DOCUMENT ENDPOINTS
# ================================================


@router.get("/documents")
async def get_documents(
    document_type: str | None = Query(None, description="Filter by document type"),
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get client's documents.

    Only returns client-visible documents.
    Optional filter by document type.
    """
    try:
        documents = await portal_service.get_documents(
            client["client_id"],
            document_type=document_type,
            current_user=client,
        )
        return {
            "success": True,
            "data": documents,
        }
    except Exception as e:
        logger.error(f"Failed to get documents for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load documents",
        ) from e


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    practice_id: int | None = Form(None),
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Upload a document for the client.

    Accepts multipart form data with:
    - file: The document file
    - document_type: Type of document (passport, nib, etc.)
    - practice_id: Optional practice to link to
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Check file size (max 10MB)
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")

    # Check allowed file types
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}
    file_ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}",
        )

    try:
        document = await portal_service.upload_document(
            client_id=client["client_id"],
            file_content=content,
            file_name=file.filename,
            document_type=document_type,
            mime_type=file.content_type,
            practice_id=practice_id,
            current_user=client,
        )
        return {
            "success": True,
            "message": "Document uploaded successfully",
            "data": document,
        }
    except Exception as e:
        logger.error(f"Failed to upload document for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to upload document",
        ) from e


# ================================================
# MESSAGE ENDPOINTS
# ================================================


@router.get("/messages")
async def get_messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get message thread (polling endpoint).

    Returns messages with pagination.
    Frontend polls this endpoint every 30s.
    """
    try:
        data = await portal_service.get_messages(
            client["client_id"],
            limit=limit,
            offset=offset,
            current_user=client,
        )
        return {
            "success": True,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Failed to get messages for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load messages",
        ) from e


@router.post("/messages")
async def send_message(
    request: SendMessageRequest,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Send a message to the team.
    """
    try:
        message = await portal_service.send_message(
            client_id=client["client_id"],
            content=request.content,
            subject=request.subject,
            practice_id=request.practice_id,
            current_user=client,
        )
        return {
            "success": True,
            "message": "Message sent",
            "data": message,
        }
    except Exception as e:
        logger.error(f"Failed to send message for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send message",
        ) from e


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Mark a message as read.
    """
    try:
        await portal_service.mark_message_read(
            client["client_id"],
            message_id,
            current_user=client,
        )
        return {
            "success": True,
            "message": "Message marked as read",
        }
    except Exception as e:
        logger.error(f"Failed to mark message {message_id} as read: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update message",
        ) from e


# ================================================
# SETTINGS ENDPOINTS
# ================================================


@router.get("/settings")
async def get_preferences(
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get client preferences/settings.
    """
    try:
        preferences = await portal_service.get_preferences(
            client["client_id"],
            current_user=client,
        )
        return {
            "success": True,
            "data": preferences,
        }
    except Exception as e:
        logger.error(f"Failed to get preferences for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load settings",
        ) from e


@router.patch("/settings")
async def update_preferences(
    request: UpdatePreferencesRequest,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Update client preferences/settings.
    """
    try:
        # Convert to dict, excluding None values
        updates = request.model_dump(exclude_none=True)
        if not updates:
            return {
                "success": True,
                "message": "No changes to apply",
            }

        preferences = await portal_service.update_preferences(
            client["client_id"],
            updates,
            current_user=client,
        )
        return {
            "success": True,
            "message": "Settings updated",
            "data": preferences,
        }
    except Exception as e:
        logger.error(f"Failed to update preferences for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update settings",
        ) from e


# ================================================
# TIMELINE ENDPOINT
# ================================================


@router.get("/timeline")
async def get_timeline(
    limit: int = Query(50, ge=1, le=100),
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get client activity timeline.

    Returns recent activity including:
    - Messages sent/received
    - Document uploads
    - Practice updates
    - Upcoming deadlines
    """
    try:
        data = await portal_service.get_timeline(
            client["client_id"],
            limit=limit,
            current_user=client,
        )
        return {
            "success": True,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Failed to get timeline for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load timeline",
        ) from e


# ================================================
# PROCESS / REQUIRED DOCUMENTS
# ================================================


@router.get("/process/required-documents")
async def get_required_documents(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Portal-scoped wrapper around the CRM "required documents per client"
    query. The workspace version (/api/crm/clients/client/{id}/...) is
    staff-only and 403s for plain client JWTs, which left /portal/process
    stuck in a loading spinner. Here the client id is derived from the
    caller's JWT (or ?as_client= for superusers) so shareholders can read
    their own process checklist without CRM RBAC.
    """
    client_id = client["client_id"]
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    prd.id, prd.practice_id, prd.document_type, prd.document_label,
                    prd.description, prd.is_required, prd.uploaded_by_client,
                    prd.status, prd.client_notes, prd.team_member_notes,
                    COALESCE(pt.name, p.practice_type_code) as process_name,
                    p.status as process_status
                FROM practice_required_documents prd
                JOIN practices p ON prd.practice_id = p.id
                LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.client_id = $1 AND p.status NOT IN ('completed', 'cancelled')
                ORDER BY prd.is_required DESC, prd.created_at DESC
                """,
                client_id,
            )
        items = [
            {
                "id": row["id"],
                "practice_id": row["practice_id"],
                "process_name": row["process_name"],
                "process_status": row["process_status"],
                "document_type": row["document_type"],
                "document_label": row["document_label"],
                "description": row["description"],
                "is_required": row["is_required"],
                "uploaded_by_client": row["uploaded_by_client"],
                "status": row["status"],
                "client_notes": row["client_notes"],
                "team_member_notes": row["team_member_notes"],
            }
            for row in rows
        ]
        return {"success": True, "data": items}
    except Exception as e:
        logger.error(
            f"Failed to get portal required documents for client {client_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to load process documents",
        ) from e


# ================================================
# PROFILE ENDPOINT
# ================================================


@router.get("/profile")
async def get_profile(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get client profile information.

    Returns complete profile including:
    - Personal info (name, email, phone, DOB, gender, nationality)
    - Passport info (number, expiry)
    - Address
    - Assigned team member
    - Member since date
    """
    try:
        async with db_pool.acquire() as conn:
            # Get client data with assigned team member
            row = await conn.fetchrow(
                """
                SELECT
                    c.id,
                    c.full_name,
                    c.email,
                    c.phone,
                    c.whatsapp,
                    c.nationality,
                    c.passport_number,
                    c.passport_expiry,
                    c.date_of_birth,
                    c.gender,
                    c.address,
                    c.created_at,
                    c.assigned_to,
                    tm.full_name as assigned_to_name,
                    tm.avatar as assigned_to_avatar
                FROM clients c
                LEFT JOIN team_members tm ON c.assigned_to = tm.email
                WHERE c.id = $1
                """,
                client["client_id"],
            )

            if not row:
                raise HTTPException(status_code=404, detail="Profile not found")

            return {
                "success": True,
                "data": {
                    "id": row["id"],
                    "full_name": row["full_name"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "whatsapp": row["whatsapp"],
                    "nationality": row["nationality"],
                    "passport_number": row["passport_number"],
                    "passport_expiry": row["passport_expiry"].isoformat()
                    if row["passport_expiry"]
                    else None,
                    "date_of_birth": row["date_of_birth"].isoformat()
                    if row["date_of_birth"]
                    else None,
                    "gender": row["gender"],
                    "address": row["address"],
                    "member_since": row["created_at"].isoformat() if row["created_at"] else None,
                    "assigned_to": {
                        "email": row["assigned_to"],
                        "name": row["assigned_to_name"] or row["assigned_to"],
                        "avatar_url": row["assigned_to_avatar"],
                    }
                    if row["assigned_to"]
                    else None,
                },
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load profile",
        ) from e


class UpdateProfileRequest(BaseModel):
    """Request to update client profile (only whitelisted fields)."""

    phone: str | None = None
    whatsapp: str | None = None
    address: str | None = None
    language: str | None = None


@router.patch("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    client: dict = Depends(get_current_client),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """Update client profile. Only phone, whatsapp, address, and language can be changed."""
    try:
        fields = {k: v for k, v in request.model_dump().items() if v is not None}
        result = await portal_service.update_profile(
            client["client_id"],
            fields,
            current_user=client,
        )
        if fields:
            await invalidate_cache("zantara:crm_clients_stats:*")
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to update profile for client {client['client_id']}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update profile",
        ) from e
