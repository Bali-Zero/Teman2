"""
ZANTARA Client Portal - Invitation Flow Router

Handles client invitation and registration:
1. Team sends invite → client receives email with link
2. Client clicks link → validates token
3. Client sets PIN → registration complete

Created: 2025-12-30
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from app.core.config import settings
from app.dependencies import get_current_user, get_database_pool
from app.utils.logging_utils import get_logger
from services.integrations.zoho_email_service import ZohoEmailService
from services.portal import InviteService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/invite", tags=["portal-invite"])


# ================================================
# PYDANTIC MODELS
# ================================================


class SendInviteRequest(BaseModel):
    """Request to send invitation to a client"""

    client_id: int
    email: EmailStr


class ValidateTokenResponse(BaseModel):
    """Response from token validation"""

    valid: bool = False
    error: str | None = None
    message: str | None = None
    client_name: str | None = None
    email: str | None = None
    invitation_id: int | None = None
    client_id: int | None = None


class CompleteRegistrationRequest(BaseModel):
    """Request to complete registration with PIN"""

    token: str
    pin: str

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        """Validate PIN is 4-6 digits"""
        if not v.isdigit():
            raise ValueError("PIN must contain only digits")
        if len(v) < 4 or len(v) > 6:
            raise ValueError("PIN must be 4-6 digits")
        return v


class RegistrationResponse(BaseModel):
    """Response from registration completion"""

    success: bool
    message: str
    user_id: str | None = None  # UUID string from team_members
    redirect_to: str | None = None


# ================================================
# HELPER FUNCTIONS
# ================================================


def get_invite_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> InviteService:
    """Dependency injection for InviteService"""
    return InviteService(db_pool)


def get_email_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> ZohoEmailService:
    """Dependency injection for ZohoEmailService"""
    return ZohoEmailService(db_pool)


def build_invite_email_html(client_name: str, invite_url: str) -> str:
    """Build HTML email for client invitation."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f8fafc;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <tr>
            <td>
                <div style="background-color: white; border-radius: 12px; padding: 40px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h1 style="color: #059669; font-size: 24px; margin: 0 0 20px 0;">
                        Welcome to Bali Zero Portal
                    </h1>
                    <p style="color: #334155; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                        Hello {client_name},
                    </p>
                    <p style="color: #334155; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                        You've been invited to access your client portal where you can:
                    </p>
                    <ul style="color: #475569; font-size: 14px; line-height: 1.8; margin: 0 0 30px 0; padding-left: 20px;">
                        <li>View your visa and immigration status</li>
                        <li>Track company licenses and compliance</li>
                        <li>Access and upload documents</li>
                        <li>Communicate with our team</li>
                    </ul>
                    <a href="{invite_url}" style="display: inline-block; background-color: #059669; color: white; padding: 14px 28px; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 8px;">
                        Activate Your Portal
                    </a>
                    <p style="color: #94a3b8; font-size: 13px; margin: 30px 0 0 0;">
                        This link expires in 72 hours. If you didn't expect this invitation, please ignore this email.
                    </p>
                </div>
                <p style="color: #94a3b8; font-size: 12px; text-align: center; margin: 20px 0 0 0;">
                    Bali Zero | Immigration & Corporate Services
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""


# ================================================
# TEAM-SIDE ENDPOINTS (Require team auth)
# ================================================


@router.post("/send")
async def send_invitation(
    request: SendInviteRequest,
    current_user: dict = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service),
    email_service: ZohoEmailService = Depends(get_email_service),
) -> dict[str, Any]:
    """
    Send invitation to a client (team member action).

    Requires team authentication. Creates invite token and sends email via Zoho.
    """
    # Verify team member role (not client)
    if current_user.get("role") == "client":
        raise HTTPException(
            status_code=403,
            detail="Clients cannot send invitations",
        )

    try:
        result = await invite_service.create_invitation(
            client_id=request.client_id,
            email=request.email,
            created_by=current_user.get("email", "system"),
        )

        # Build full invite URL
        base_url = getattr(settings, "frontend_url", "https://nuzantara-mouth.fly.dev")
        full_invite_url = f"{base_url}{result['invite_url']}"

        # Try to send email via Zoho (using current user's connected account)
        email_sent = False
        email_error = None
        try:
            user_email = current_user.get("email", "")
            if user_email:
                html_content = build_invite_email_html(
                    client_name=result["client_name"],
                    invite_url=full_invite_url,
                )
                await email_service.send_email(
                    user_id=user_email,
                    to=[request.email],
                    subject="Welcome to Bali Zero Client Portal",
                    content=html_content,
                    is_html=True,
                )
                email_sent = True
                logger.info(f"Invitation email sent to {request.email}")
        except Exception as email_err:
            email_error = str(email_err)
            logger.warning(f"Failed to send invitation email: {email_err}")

        logger.info(
            f"Invitation created for client {request.client_id} by {current_user.get('email')}"
        )

        return {
            "success": True,
            "message": "Invitation created"
            + (" and email sent" if email_sent else " (email not sent - check Zoho connection)"),
            "email_sent": email_sent,
            "email_error": email_error if not email_sent else None,
            "data": {
                **result,
                "full_invite_url": full_invite_url,
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to create invitation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create invitation",
        ) from e


@router.get("/client/{client_id}")
async def get_client_invitations(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service),
) -> dict[str, Any]:
    """
    Get all invitations for a client (team member action).

    Returns invitation history with status (pending/used/expired).
    """
    if current_user.get("role") == "client":
        raise HTTPException(
            status_code=403,
            detail="Clients cannot view invitation history",
        )

    try:
        invitations = await invite_service.get_client_invitations(client_id)
        return {
            "success": True,
            "data": invitations,
        }
    except Exception as e:
        logger.error(f"Failed to get invitations for client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve invitations",
        ) from e


@router.post("/resend/{client_id}")
async def resend_invitation(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service),
) -> dict[str, Any]:
    """
    Resend invitation to a client (creates new token).
    """
    if current_user.get("role") == "client":
        raise HTTPException(
            status_code=403,
            detail="Clients cannot resend invitations",
        )

    try:
        result = await invite_service.resend_invitation(
            client_id=client_id,
            created_by=current_user.get("email", "system"),
        )

        logger.info(f"Invitation resent for client {client_id} by {current_user.get('email')}")

        return {
            "success": True,
            "message": "Invitation resent successfully",
            "data": result,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to resend invitation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to resend invitation",
        ) from e


# ================================================
# PUBLIC ENDPOINTS (No auth required)
# ================================================


@router.get("/validate/{token}")
async def validate_token(
    token: str,
    invite_service: InviteService = Depends(get_invite_service),
) -> ValidateTokenResponse:
    """
    Validate invitation token (public endpoint).

    Called when client clicks invite link. Returns client info if valid.
    """
    try:
        result = await invite_service.validate_token(token)

        if result is None:
            return ValidateTokenResponse(
                valid=False,
                error="invalid_token",
                message="This invitation link is invalid",
            )

        if "error" in result:
            return ValidateTokenResponse(
                valid=False,
                error=result["error"],
                message=result["message"],
            )

        return ValidateTokenResponse(
            valid=True,
            client_name=result["client_name"],
            email=result["email"],
            invitation_id=result["invitation_id"],
            client_id=result["client_id"],
        )

    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        return ValidateTokenResponse(
            valid=False,
            error="server_error",
            message="An error occurred while validating the invitation",
        )


@router.post("/complete")
async def complete_registration(
    request: CompleteRegistrationRequest,
    invite_service: InviteService = Depends(get_invite_service),
) -> RegistrationResponse:
    """
    Complete client registration by setting PIN (public endpoint).

    Called after client validates token and sets their PIN.
    Creates user account and returns login redirect.
    """
    try:
        result = await invite_service.complete_registration(
            token=request.token,
            pin=request.pin,
        )

        logger.info(f"Client registration completed: {result['email']}")

        return RegistrationResponse(
            success=True,
            message="Registration successful! You can now log in.",
            user_id=result["user_id"],
            redirect_to="/login",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Registration failed. Please try again or contact support.",
        ) from e
