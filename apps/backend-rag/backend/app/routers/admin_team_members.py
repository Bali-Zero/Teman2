"""
Admin Team Members Router

Admin-only endpoints for managing team_members records that are NOT covered
by the existing team_activity / team / portal_invite routers.

Currently exposes:
- POST /api/admin/team-members/{user_id}/set-pin
  Set or rotate the bcrypt PIN hash for a team member. Required when
  onboarding a new non-client user (e.g. Subhi Darajat 2026-04-30) because
  the existing portal_invite flow only covers role='client'.

Security:
- Authenticated request via JWT (get_current_user)
- is_crm_admin gate (role admin/founder/CEO/board, or email in admin allowlist)
- Audit-logged via SecurityAuditService action='permission_change'
- Bcrypt cost=12 (matches existing invite_service.py and auth.py)
- PIN format: exactly 6 digits (matches portal client convention)
- Resets failed_attempts to 0 on successful PIN change
"""

import logging
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.security.audit_service import SecurityAuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/team-members", tags=["admin-team-members"])


# =============================================================================
# Auth
# =============================================================================


async def verify_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Verify current user is a CRM admin (role admin/founder/CEO/board or email allowlist)."""
    if not is_crm_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# =============================================================================
# Models
# =============================================================================


class SetPinRequest(BaseModel):
    """Request to set/rotate a team member's PIN."""

    new_pin: str = Field(
        ...,
        description="6-digit numeric PIN. Will be bcrypt-hashed before storage.",
        min_length=6,
        max_length=6,
    )

    @field_validator("new_pin")
    @classmethod
    def _pin_must_be_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("PIN must be exactly 6 digits (0-9)")
        return v


class SetPinResponse(BaseModel):
    """Response after a successful PIN change."""

    status: str = "ok"
    user_id: str
    email: str


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/{user_id}/set-pin", response_model=SetPinResponse)
async def set_pin(
    user_id: str,
    req: SetPinRequest,
    request: Request,
    admin: Annotated[dict, Depends(verify_admin)],
) -> SetPinResponse:
    """
    Set or rotate the PIN of a team member.

    Bcrypt-hashes the new PIN (cost=12) and stores it in team_members.pin_hash.
    Resets failed_attempts to 0. Logs the operation in security_audit_log
    (action='permission_change', success/failure).

    Returns 404 if user_id does not exist.
    Returns 403 if caller is not an admin.
    Returns 422 if PIN is not exactly 6 digits.
    """
    db_pool = get_database_pool(request)
    audit = SecurityAuditService()

    admin_email = (admin.get("email") or "").lower()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Bcrypt cost=12 to match invite_service.py and existing team_members rows.
    pin_hash = bcrypt.hashpw(req.new_pin.encode(), bcrypt.gensalt(rounds=12)).decode()

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # Lookup target to fail fast on missing user, AND to capture email
            # for the audit log.
            target = await conn.fetchrow(
                "SELECT id, email FROM team_members WHERE id = $1",
                user_id,
            )

            if not target:
                # Audit the failed attempt before raising — admin attempted
                # to rotate a PIN for a user that doesn't exist.
                await audit.log_event(
                    conn=conn,
                    action="permission_change",
                    user_email=admin_email,
                    resource_type="team_member.pin",
                    resource_id=user_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    success=False,
                    details={"reason": "user_not_found"},
                )
                raise HTTPException(status_code=404, detail="Team member not found")

            await conn.execute(
                """
                UPDATE team_members
                SET pin_hash = $1,
                    failed_attempts = 0,
                    updated_at = NOW()
                WHERE id = $2
                """,
                pin_hash,
                user_id,
            )

            await audit.log_event(
                conn=conn,
                action="permission_change",
                user_email=admin_email,
                resource_type="team_member.pin",
                resource_id=user_id,
                ip_address=client_ip,
                user_agent=user_agent,
                success=True,
                details={"target_email": target["email"]},
            )

    logger.info(
        "admin_team_members.set_pin success admin=%s target=%s",
        admin_email,
        target["email"],
    )

    return SetPinResponse(status="ok", user_id=user_id, email=target["email"])
