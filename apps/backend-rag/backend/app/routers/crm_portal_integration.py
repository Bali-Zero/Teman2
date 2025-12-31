"""
ZANTARA CRM - Portal Integration Router

Team-side endpoints for Portal interaction:
- Check client portal status
- Send portal invites from CRM
- Preview client's portal view
- Get unread messages count
- Send messages to clients

This creates the "intradinamici" connection between Team and Portal.

Created: 2025-12-30
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr

from app.dependencies import get_current_user, get_database_pool
from app.utils.logging_utils import get_logger
from services.portal import InviteService, PortalService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/portal", tags=["crm-portal-integration"])


# ================================================
# PYDANTIC MODELS
# ================================================


class PortalStatusResponse(BaseModel):
    """Portal status for a client"""

    has_portal_access: bool
    portal_user_id: int | None = None
    portal_email: str | None = None
    last_login: str | None = None
    pending_invite: bool = False
    invite_expires_at: str | None = None


class SendInviteRequest(BaseModel):
    """Request to send portal invite"""

    email: EmailStr | None = None  # Optional - uses client email if not provided


class TeamMessageRequest(BaseModel):
    """Request to send message to client"""

    content: str
    subject: str | None = None
    practice_id: int | None = None


class UnreadCountResponse(BaseModel):
    """Unread messages count"""

    total_unread: int
    by_client: list[dict[str, Any]]


# ================================================
# HELPER FUNCTIONS
# ================================================


def require_team_auth(current_user: dict = Depends(get_current_user)) -> dict:
    """Ensure user is team member, not client"""
    if current_user.get("role") == "client":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only accessible to team members",
        )
    return current_user


def get_invite_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> InviteService:
    """Dependency injection for InviteService"""
    return InviteService(db_pool)


def get_portal_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> PortalService:
    """Dependency injection for PortalService"""
    return PortalService(db_pool)


# ================================================
# PORTAL STATUS ENDPOINTS
# ================================================


@router.get("/clients/{client_id}/status")
async def get_portal_status(
    client_id: int,
    current_user: dict = Depends(require_team_auth),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Check portal status for a client.

    Returns:
    - Whether client has portal access
    - Portal user details if exists
    - Pending invitation status
    """
    async with db_pool.acquire() as conn:
        # Check for portal user
        portal_user = await conn.fetchrow(
            """
            SELECT tm.id, tm.email, tm.created_at as last_login
            FROM team_members tm
            WHERE tm.linked_client_id = $1
              AND tm.role = 'client'
              AND tm.active = true
              AND tm.portal_access = true
            """,
            client_id,
        )

        # Check for pending invitation
        pending_invite = await conn.fetchrow(
            """
            SELECT expires_at
            FROM client_invitations
            WHERE client_id = $1
              AND used_at IS NULL
              AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            client_id,
        )

        if portal_user:
            return {
                "success": True,
                "data": {
                    "has_portal_access": True,
                    "portal_user_id": portal_user["id"],
                    "portal_email": portal_user["email"],
                    "last_login": portal_user["last_login"].isoformat() if portal_user["last_login"] else None,
                    "pending_invite": False,
                    "invite_expires_at": None,
                },
            }
        elif pending_invite:
            return {
                "success": True,
                "data": {
                    "has_portal_access": False,
                    "portal_user_id": None,
                    "portal_email": None,
                    "last_login": None,
                    "pending_invite": True,
                    "invite_expires_at": pending_invite["expires_at"].isoformat(),
                },
            }
        else:
            return {
                "success": True,
                "data": {
                    "has_portal_access": False,
                    "portal_user_id": None,
                    "portal_email": None,
                    "last_login": None,
                    "pending_invite": False,
                    "invite_expires_at": None,
                },
            }


# ================================================
# INVITE ENDPOINTS
# ================================================


@router.post("/clients/{client_id}/invite")
async def send_portal_invite(
    client_id: int,
    request: SendInviteRequest | None = None,
    current_user: dict = Depends(require_team_auth),
    invite_service: InviteService = Depends(get_invite_service),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Send portal invitation to a client from CRM.

    If email not provided, uses client's email from the clients table.
    """
    try:
        # Get client email if not provided
        email = request.email if request else None

        if not email:
            async with db_pool.acquire() as conn:
                client = await conn.fetchrow(
                    "SELECT email FROM clients WHERE id = $1",
                    client_id,
                )
                if not client or not client["email"]:
                    raise HTTPException(
                        status_code=400,
                        detail="Client has no email address. Please provide one.",
                    )
                email = client["email"]

        result = await invite_service.create_invitation(
            client_id=client_id,
            email=email,
            created_by=current_user.get("email", "system"),
        )

        logger.info(
            f"Portal invite sent for client {client_id} by {current_user.get('email')}"
        )

        return {
            "success": True,
            "message": f"Invitation sent to {email}",
            "data": result,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send portal invite: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send invitation",
        ) from e


# ================================================
# PREVIEW ENDPOINT
# ================================================


@router.get("/clients/{client_id}/preview")
async def get_portal_preview(
    client_id: int,
    current_user: dict = Depends(require_team_auth),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get client's portal view data (for "View as Client" feature).

    Returns the same data the client would see in their portal dashboard.
    """
    try:
        dashboard = await portal_service.get_dashboard(client_id)
        visa = await portal_service.get_visa_status(client_id)
        companies = await portal_service.get_companies(client_id)
        taxes = await portal_service.get_tax_overview(client_id)

        return {
            "success": True,
            "data": {
                "dashboard": dashboard,
                "visa": visa,
                "companies": companies,
                "taxes": taxes,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get portal preview for client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load portal preview",
        ) from e


# ================================================
# MESSAGES ENDPOINTS (Team side)
# ================================================


@router.get("/messages/unread-count")
async def get_unread_messages_count(
    current_user: dict = Depends(require_team_auth),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get count of unread messages from all clients.

    For header notification badge.
    """
    async with db_pool.acquire() as conn:
        # Total unread
        total = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM portal_messages
            WHERE direction = 'client_to_team'
              AND read_at IS NULL
            """,
        )

        # By client
        by_client = await conn.fetch(
            """
            SELECT
                pm.client_id,
                c.full_name as client_name,
                COUNT(*) as unread_count
            FROM portal_messages pm
            JOIN clients c ON c.id = pm.client_id
            WHERE pm.direction = 'client_to_team'
              AND pm.read_at IS NULL
            GROUP BY pm.client_id, c.full_name
            ORDER BY unread_count DESC
            LIMIT 10
            """,
        )

        return {
            "success": True,
            "data": {
                "total_unread": total or 0,
                "by_client": [
                    {
                        "client_id": row["client_id"],
                        "client_name": row["client_name"],
                        "unread_count": row["unread_count"],
                    }
                    for row in by_client
                ],
            },
        }


@router.get("/clients/{client_id}/messages")
async def get_client_messages(
    client_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_team_auth),
    portal_service: PortalService = Depends(get_portal_service),
) -> dict[str, Any]:
    """
    Get message thread for a client (team view).

    Same messages as client sees, but from team perspective.
    """
    try:
        data = await portal_service.get_messages(client_id, limit=limit, offset=offset)
        return {
            "success": True,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Failed to get messages for client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load messages",
        ) from e


@router.post("/clients/{client_id}/messages")
async def send_message_to_client(
    client_id: int,
    request: TeamMessageRequest,
    current_user: dict = Depends(require_team_auth),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Send a message to a client (team → client).
    """
    try:
        async with db_pool.acquire() as conn:
            message = await conn.fetchrow(
                """
                INSERT INTO portal_messages
                    (client_id, practice_id, subject, direction, content, sent_by)
                VALUES ($1, $2, $3, 'team_to_client', $4, $5)
                RETURNING id, subject, content, sent_by, created_at
                """,
                client_id,
                request.practice_id,
                request.subject,
                request.content,
                current_user.get("email", "team"),
            )

            logger.info(
                f"Team message sent to client {client_id} by {current_user.get('email')}"
            )

            return {
                "success": True,
                "message": "Message sent",
                "data": {
                    "id": message["id"],
                    "subject": message["subject"],
                    "content": message["content"],
                    "sent_by": message["sent_by"],
                    "created_at": message["created_at"].isoformat(),
                },
            }
    except Exception as e:
        logger.error(f"Failed to send message to client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send message",
        ) from e


@router.post("/clients/{client_id}/messages/{message_id}/read")
async def mark_client_message_read(
    client_id: int,
    message_id: int,
    current_user: dict = Depends(require_team_auth),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Mark a client message as read (team reading client's message).
    """
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE portal_messages
                SET read_at = NOW()
                WHERE id = $1
                  AND client_id = $2
                  AND direction = 'client_to_team'
                  AND read_at IS NULL
                """,
                message_id,
                client_id,
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
# ACTIVITY ENDPOINT
# ================================================


@router.get("/activity/recent")
async def get_recent_portal_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(require_team_auth),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get recent client portal activity.

    For dashboard widget showing:
    - New messages
    - Document uploads
    - Login activity
    """
    async with db_pool.acquire() as conn:
        # Recent messages from clients
        messages = await conn.fetch(
            """
            SELECT
                pm.id,
                'message' as activity_type,
                pm.client_id,
                c.full_name as client_name,
                pm.subject,
                LEFT(pm.content, 100) as preview,
                pm.created_at
            FROM portal_messages pm
            JOIN clients c ON c.id = pm.client_id
            WHERE pm.direction = 'client_to_team'
            ORDER BY pm.created_at DESC
            LIMIT $1
            """,
            limit,
        )

        return {
            "success": True,
            "data": {
                "activities": [
                    {
                        "id": row["id"],
                        "type": row["activity_type"],
                        "client_id": row["client_id"],
                        "client_name": row["client_name"],
                        "subject": row["subject"],
                        "preview": row["preview"],
                        "timestamp": row["created_at"].isoformat(),
                    }
                    for row in messages
                ],
            },
        }
