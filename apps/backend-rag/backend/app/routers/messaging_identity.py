"""
Messaging Identity Admin Router
Admin endpoints for managing phone/telegram → user mappings (team members + portal clients).

Enables:
- Creating associations (phone → user, telegram → user)
- Listing all mappings for a user
- Removing/deactivating mappings
- Viewing mapping statistics

Security:
- All endpoints require authentication
- Only users with role 'admin' or 'founder' can manage mappings
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user_email, get_database
from backend.services.integrations.messaging_identity_service import (
    get_messaging_identity_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/messaging-identity", tags=["Messaging Identity Admin"])


# Pydantic Models
class CreateMappingRequest(BaseModel):
    """Request to create new messaging identity mapping."""

    user_id: str = Field(..., description="UUID from user_profiles (team member or portal client)")
    channel: str = Field(..., description="Channel type: 'whatsapp' or 'telegram'")
    phone: str | None = Field(None, description="WhatsApp phone (for whatsapp channel)")
    telegram_chat_id: int | None = Field(
        None, description="Telegram chat ID (for telegram channel)",
    )
    display_name: str | None = Field(None, description="Display name from profile")
    verified: bool = Field(False, description="Whether association is verified")


class MappingResponse(BaseModel):
    """Response for a single mapping."""

    id: str
    user_id: str
    channel: str
    phone: str | None
    telegram_chat_id: int | None
    display_name: str | None
    verified: bool
    last_message_at: str | None


class DeactivateMappingRequest(BaseModel):
    """Request to deactivate a mapping."""

    phone: str | None = Field(None, description="WhatsApp phone")
    telegram_chat_id: int | None = Field(None, description="Telegram chat ID")


# Dependency: Check admin role
async def require_admin(
    email: Annotated[str, Depends(get_current_user_email)],
    request: Request,
) -> str:
    """
    Verify that the current user is an admin or founder.

    Args:
        email: User email from JWT
        request: FastAPI request

    Returns:
        User email if authorized

    Raises:
        HTTPException: If user is not authorized
    """
    db_pool = get_database(request)

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ta.role
                FROM team_access ta
                JOIN user_profiles up ON up.id = ta.user_id
                WHERE up.email = $1
                """,
                email,
            )

            if not row or row["role"] not in ("admin", "founder"):
                raise HTTPException(
                    status_code=403,
                    detail="Only admins and founders can manage messaging identity mappings",
                )

            return email

    except Exception as e:
        logger.error(f"Error checking admin role: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/mappings", status_code=201)
async def create_mapping(
    req: CreateMappingRequest,
    request: Request,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    """
    Create new messaging identity mapping.

    Admin only. Maps phone or telegram_chat_id to a user (team member or portal client).
    """
    db_pool = get_database(request)
    identity_service = get_messaging_identity_service(db_pool)

    success = await identity_service.create_mapping(
        user_id=req.user_id,
        channel=req.channel,
        phone=req.phone,
        telegram_chat_id=req.telegram_chat_id,
        display_name=req.display_name,
        verified=req.verified,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to create mapping (may already exist)")

    return {"status": "created", "message": "Mapping created successfully"}


@router.get("/mappings/{user_id}")
async def get_mappings_for_user(
    user_id: str,
    request: Request,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    """
    Get all messaging channel mappings for a user (team member or portal client).

    Admin only.
    """
    db_pool = get_database(request)
    identity_service = get_messaging_identity_service(db_pool)

    mappings = await identity_service.get_mappings_for_user(user_id)

    return {"user_id": user_id, "mappings": mappings, "count": len(mappings)}


@router.post("/mappings/deactivate")
async def deactivate_mapping(
    req: DeactivateMappingRequest,
    request: Request,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    """
    Deactivate (soft delete) a messaging identity mapping.

    Admin only.
    """
    db_pool = get_database(request)
    identity_service = get_messaging_identity_service(db_pool)

    success = await identity_service.deactivate_mapping(
        phone=req.phone,
        telegram_chat_id=req.telegram_chat_id,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to deactivate mapping")

    return {"status": "deactivated", "message": "Mapping deactivated successfully"}


@router.get("/mappings")
async def list_all_mappings(
    request: Request,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    """
    List all active messaging identity mappings.

    Admin only. Returns stats + recent mappings.
    """
    db_pool = get_database(request)

    try:
        async with db_pool.acquire() as conn:
            # Get stats
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE channel = 'whatsapp') as whatsapp_count,
                    COUNT(*) FILTER (WHERE channel = 'telegram') as telegram_count,
                    COUNT(*) FILTER (WHERE verified = TRUE) as verified_count,
                    COUNT(*) as total_count
                FROM messaging_users
                WHERE active = TRUE
                """,
            )

            # Get recent mappings (last 50)
            mappings = await conn.fetch(
                """
                SELECT
                    mu.id, mu.user_id, mu.channel, mu.phone,
                    mu.telegram_chat_id, mu.display_name, mu.verified,
                    mu.last_message_at, mu.created_at,
                    up.full_name as user_name, up.email as user_email
                FROM messaging_users mu
                LEFT JOIN user_profiles up ON up.id = mu.user_id
                WHERE mu.active = TRUE
                ORDER BY mu.created_at DESC
                LIMIT 50
                """,
            )

            return {
                "stats": dict(stats),
                "mappings": [dict(row) for row in mappings],
                "count": len(mappings),
            }

    except Exception as e:
        logger.error(f"Error listing mappings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/lookup/phone/{phone}")
async def lookup_by_phone(
    phone: str,
    request: Request,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    """
    Lookup user by phone number.

    Admin only. Returns mapping if exists (team member or portal client).
    """
    db_pool = get_database(request)
    identity_service = get_messaging_identity_service(db_pool)

    mapping = await identity_service.get_user_by_phone(phone)

    if not mapping:
        raise HTTPException(status_code=404, detail="No mapping found for this phone")

    return {"phone": phone, "mapping": mapping}


@router.get("/lookup/telegram/{chat_id}")
async def lookup_by_telegram(
    chat_id: int,
    request: Request,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict[str, Any]:
    """
    Lookup user by Telegram chat ID.

    Admin only. Returns mapping if exists (team member or portal client).
    """
    db_pool = get_database(request)
    identity_service = get_messaging_identity_service(db_pool)

    mapping = await identity_service.get_user_by_telegram(chat_id)

    if not mapping:
        raise HTTPException(status_code=404, detail="No mapping found for this Telegram chat ID")

    return {"telegram_chat_id": chat_id, "mapping": mapping}
