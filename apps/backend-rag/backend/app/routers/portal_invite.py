"""
ZANTARA Client Portal - Invitation Flow Router

Handles client invitation and registration:
1. Team sends invite → client receives email with link
2. Client clicks link → validates token
3. Client sets PIN → registration complete

Created: 2025-12-30
"""

from html import escape
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.services.internal_email import send_internal_email
from backend.app.utils.crm_utils import verify_client_access
from backend.app.utils.logging_utils import get_logger
from backend.app.utils.service_accounts import is_human_team_member
from backend.services.portal import InviteService

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


def build_invite_email_html(
    client_name: str, invite_url: str, consultant_name: str | None = None
) -> str:
    """Build the brand-compliant HTML email for a client portal invitation.

    Follows the `email-template` brand surface (600px table layout, HTML 4.01
    Transitional doctype, inline CSS only, no `<style>` block, no web fonts,
    no emoji) — see
    `/Users/balizero/.agents/skills/bali-zero-brand/surfaces/email-template.md`
    and section 11 of the 2026-09 portal launch kit spec.
    """
    safe_client_name = escape(client_name, quote=True) if client_name else ""
    safe_invite_url = escape(invite_url, quote=True)
    greeting = f"Hello {safe_client_name}," if safe_client_name else "Hello there,"

    consultant_line = ""
    if consultant_name:
        safe_consultant_name = escape(consultant_name, quote=True)
        consultant_line = f"""
<p style="margin: 0 0 20px 0; font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.5; color: #1A1A1A;">Your consultant: {safe_consultant_name}</p>"""

    return f"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Welcome to Bali Zero Client Portal</title>
</head>
<body style="margin: 0; padding: 0; background-color: #FFFFFF;">
<span style="display: none; visibility: hidden; mso-hide: all; font-size: 1px; line-height: 1px; max-height: 0; max-width: 0; opacity: 0; overflow: hidden;">One link, 72 hours, your documents in one place.</span>
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center">
<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px;">
<tr>
<td style="background-color: #363A3E; padding: 0 24px;" height="80">
<table width="100%" cellpadding="0" cellspacing="0" border="0" height="80">
<tr>
<td width="48" valign="middle">
<img src="https://balizero.com/assets/logo/balizero-logo-circle.png" alt="Bali Zero" width="40" height="40" style="display: block; border: 0;">
</td>
<td valign="middle" style="padding-left: 12px; font-family: Arial, Helvetica, sans-serif;">
<span style="color: #FFFFFF; font-size: 18px; font-weight: 700;">Bali Zero</span><br>
<span style="color: #9CA3AF; font-size: 12px;">Client Portal</span>
</td>
</tr>
</table>
</td>
</tr>
<tr>
<td style="background-color: #FFFFFF; padding: 40px 32px;">
<h1 style="margin: 0 0 24px 0; font-family: Arial, Helvetica, sans-serif; font-size: 28px; font-weight: 700; color: #1A1A1A; letter-spacing: 0.02em;">Your Bali Zero Portal Is Ready</h1>
<p style="margin: 0 0 16px 0; font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.5; color: #1A1A1A;">{greeting}</p>
<p style="margin: 0 0 28px 0; font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.5; color: #1A1A1A;">Your Bali Zero client portal holds your documents, case status and messages with your team in one place, so passport scans and contracts no longer travel on WhatsApp.</p>
<h2 style="margin: 0 0 16px 0; font-family: Arial, Helvetica, sans-serif; font-size: 18px; font-weight: 700; color: #1A1A1A;">What Happens Next</h2>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 0 0 28px 0;">
<tr>
<td style="font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.5; color: #1A1A1A; padding: 0 0 12px 0;">1. Open the link below.</td>
</tr>
<tr>
<td style="font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.5; color: #1A1A1A; padding: 0 0 12px 0;">2. Choose a 4 to 6 digit PIN.</td>
</tr>
<tr>
<td style="font-family: Arial, Helvetica, sans-serif; font-size: 16px; line-height: 1.5; color: #1A1A1A;">3. Sign in at my.balizero.com with your email and PIN, or use a magic link. No password to remember.</td>
</tr>
</table>
<table cellpadding="0" cellspacing="0" border="0" style="margin: 0 0 12px 0;">
<tr>
<td style="background-color: #F4C430; border-radius: 4px;" align="center">
<a href="{safe_invite_url}" style="display: inline-block; padding: 14px 32px; font-family: Arial, Helvetica, sans-serif; font-size: 16px; font-weight: 700; color: #363A3E; text-decoration: none; border-radius: 4px;">Activate My Portal</a>
</td>
</tr>
</table>
<p style="margin: 0 0 28px 0; font-family: Arial, Helvetica, sans-serif; font-size: 13px; line-height: 1.5; color: #6B7280;">Or copy this link into your browser: <a href="{safe_invite_url}" style="color: #6B7280;">{safe_invite_url}</a></p>{consultant_line}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #363A3E; border-left: 4px solid #F4C430;">
<tr>
<td style="padding: 16px 20px; font-family: Arial, Helvetica, sans-serif; font-size: 13px; line-height: 1.5; color: #FFFFFF;">This link is valid for 72 hours and can be used once. Nobody at Bali Zero will ever ask for your PIN. If you did not expect this email, ignore it.</td>
</tr>
</table>
</td>
</tr>
<tr>
<td style="background-color: #FFFFFF; padding: 24px 32px; border-top: 1px solid #E5E7EB;">
<p style="margin: 0; font-family: Arial, Helvetica, sans-serif; font-size: 13px; line-height: 1.5; color: #6B7280;">Bali Zero &middot; Jl. Raya Anyar No. 2, Kerobokan Kelod, Kuta Utara, Badung, Bali 80361 &middot; zantara@balizero.com &middot; +62 821 3454 721 &middot; my.balizero.com</p>
</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>
"""


async def send_portal_invite_email(
    *,
    to: str,
    client_name: str,
    invite_url: str,
    db_pool: asyncpg.Pool,
    client_id: int,
    consultant_name: str | None = None,
) -> None:
    """Send a client portal invite through the canonical Brevo adapter."""
    await send_internal_email(
        to=to,
        subject="Welcome to Bali Zero Client Portal",
        body=build_invite_email_html(
            client_name=client_name,
            invite_url=invite_url,
            consultant_name=consultant_name,
        ),
        log_context=f"portal invite client={client_id}",
        raise_on_failure=True,
        email_type="welcome",
        pool=db_pool,
        client_id=client_id,
    )


def _invitation_public_view(result: dict[str, Any]) -> dict[str, Any]:
    """Strip the raw invite credential from a service result before it goes in a response.

    `token` and any URL that embeds it (`invite_url`) are the credential that
    completes registration and takes over — or reactivates — a client's portal
    account (`POST /api/portal/invite/complete` is public, unauthenticated).
    The only legitimate channel for either value is the Brevo email built by
    `send_portal_invite_email`. This view is applied at the ROUTER boundary,
    never inside `InviteService`, because `send_invitation` still needs the
    raw token/URL to build that email before stripping the HTTP response.
    """
    return {key: value for key, value in result.items() if key not in {"token", "invite_url"}}


# ================================================
# TEAM-SIDE ENDPOINTS (Require team auth)
# ================================================


@router.post("/send")
async def send_invitation(
    request: SendInviteRequest,
    current_user: dict = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Send invitation to a client (team member action).

    Requires team authentication. Creates invite token and sends email via Brevo.
    """
    # Verify team member role — neither a client nor a service account. This
    # mints a live Brevo invitation email, so "not a client" is the wrong test.
    if not is_human_team_member(current_user.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Clients cannot send invitations",
        )

    # Client-level access check: a human team role alone is not enough — the
    # caller must be assigned to (or admin over) THIS client. write=True also
    # denies machine principals by construction (a service-account email
    # matches neither assigned_to nor created_by). Runs before the try block
    # below so verify_client_access's HTTPException(403/404) is never
    # swallowed by the generic `except Exception` inside it.
    async with db_pool.acquire() as conn:
        await verify_client_access(
            request.client_id, current_user, conn, allow_assigned=True, write=True
        )

    try:
        result = await invite_service.create_invitation(
            client_id=request.client_id,
            email=request.email,
            created_by=current_user.get("email", "system"),
        )

        # Build full invite URL
        # No rstrip here on purpose: the trailing slash is normalised on the
        # SETTING itself, so this router and the GARUDA outbox handler — the
        # other consumer of the same value — cannot disagree about it.
        base_url = settings.frontend_portal_url
        full_invite_url = f"{base_url}{result['invite_url']}"

        # Try to send email via the canonical Brevo adapter.
        email_sent = False
        email_error = None
        try:
            await send_portal_invite_email(
                to=str(request.email),
                client_name=result["client_name"],
                invite_url=full_invite_url,
                db_pool=db_pool,
                client_id=request.client_id,
            )
            email_sent = True
            logger.info(f"Invitation email sent to {request.email}")
        except Exception as email_err:
            email_error = str(email_err)
            logger.warning("Failed to send invitation email: %s", email_err)

        logger.info(
            f"Invitation created for client {request.client_id} by {current_user.get('email')}",
        )

        return {
            "success": True,
            "message": "Invitation created"
            + (" and email sent" if email_sent else " (email not sent - check email service)"),
            "email_sent": email_sent,
            "email_error": email_error if not email_sent else None,
            # `full_invite_url` (built above, purely for the Brevo email) is
            # deliberately NOT included here — it embeds the same raw token as
            # `invite_url` and would defeat the point of stripping it.
            "data": _invitation_public_view(result),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to create invitation: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to create invitation",
        ) from e


@router.get("/client/{client_id}")
async def get_client_invitations(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get all invitations for a client (team member action).

    Returns invitation history with status (pending/used/expired).
    """
    if not is_human_team_member(current_user.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Clients cannot view invitation history",
        )

    # See send_invitation for the rationale — same client-level gate, run
    # before the try block so its HTTPException is never rewritten to a 500.
    async with db_pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)

    try:
        invitations = await invite_service.get_client_invitations(client_id)
        return {
            "success": True,
            "data": invitations,
        }
    except Exception as e:
        logger.error("Failed to get invitations for client %s: %s", client_id, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve invitations",
        ) from e


@router.post("/resend/{client_id}")
async def resend_invitation(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    invite_service: InviteService = Depends(get_invite_service),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Resend invitation to a client (creates new token).
    """
    if not is_human_team_member(current_user.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Clients cannot resend invitations",
        )

    # See send_invitation for the rationale — same client-level gate, run
    # before the try block so its HTTPException is never rewritten to a 500.
    async with db_pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True, write=True)

    try:
        result = await invite_service.resend_invitation(
            client_id=client_id,
            created_by=current_user.get("email", "system"),
        )

        logger.info(f"Invitation resent for client {client_id} by {current_user.get('email')}")

        return {
            "success": True,
            "message": "Invitation resent successfully",
            "data": _invitation_public_view(result),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to resend invitation: %s", e)
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
        logger.error("Token validation failed: %s", e)
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
        logger.error("Registration failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Registration failed. Please try again or contact support.",
        ) from e
