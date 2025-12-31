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
from fastapi import APIRouter, Depends, HTTPException, Query, Request, File, UploadFile, Form
from pydantic import BaseModel

from app.dependencies import get_database_pool
from app.utils.logging_utils import get_logger
from services.portal import PortalService

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


async def get_current_client(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Get current authenticated client from JWT token.

    Requires:
    - Valid JWT token (from middleware)
    - role = 'client'
    - linked_client_id set

    Returns:
        dict with: client_id, user_id, email, name
    """
    # Get user from middleware
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = request.state.user

    # Check role is client
    if user.get("role") != "client":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only accessible to clients",
        )

    # Get linked_client_id from user record
    # Note: team_members.id is UUID (VARCHAR), not integer
    user_id = user.get("id") or user.get("user_id")
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
        data = await portal_service.get_dashboard(client["client_id"])
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
        data = await portal_service.get_visa_status(client["client_id"])
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
        companies = await portal_service.get_companies(client["client_id"])
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
        data = await portal_service.get_company_detail(client["client_id"], company_id)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail="Company not found or not accessible",
            )
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
        result = await portal_service.set_primary_company(client["client_id"], company_id)
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
        data = await portal_service.get_tax_overview(client["client_id"])
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
            detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )

    try:
        document = await portal_service.upload_document(
            client_id=client["client_id"],
            file_content=content,
            file_name=file.filename,
            document_type=document_type,
            mime_type=file.content_type,
            practice_id=practice_id,
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
        await portal_service.mark_message_read(client["client_id"], message_id)
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
        preferences = await portal_service.get_preferences(client["client_id"])
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
# PROFILE ENDPOINT
# ================================================


@router.get("/profile")
async def get_profile(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get client profile information.
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, full_name, email, phone, whatsapp, nationality,
                       passport_number, address, created_at
                FROM clients
                WHERE id = $1
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
                    "address": row["address"],
                    "member_since": row["created_at"].isoformat() if row["created_at"] else None,
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
