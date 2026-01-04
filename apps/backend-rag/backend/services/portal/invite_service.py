"""
Client Portal Invite Service

Handles client invitation flow:
1. Team sends invite to client email
2. Client clicks link, validates token
3. Client creates PIN to complete registration
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import bcrypt

from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Constants
INVITE_TOKEN_LENGTH = 64
INVITE_EXPIRY_HOURS = 72  # 3 days


class InviteService:
    """Service for managing client portal invitations."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def create_invitation(
        self,
        client_id: int,
        email: str,
        created_by: str,
    ) -> dict[str, Any]:
        """
        Create a new invitation for a client.

        Args:
            client_id: ID of the client in clients table
            email: Client's email address
            created_by: Email of team member sending invite

        Returns:
            Dict with invitation details including token
        """
        # Generate secure token
        token = secrets.token_urlsafe(INVITE_TOKEN_LENGTH)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)

        async with self.pool.acquire() as conn:
            # Check if client exists
            client = await conn.fetchrow(
                "SELECT id, full_name, email FROM clients WHERE id = $1",
                client_id,
            )
            if not client:
                raise ValueError(f"Client with ID {client_id} not found")

            # Check for existing unused invitation
            existing = await conn.fetchrow(
                """
                SELECT id FROM client_invitations
                WHERE client_id = $1 AND used_at IS NULL AND expires_at > NOW()
                """,
                client_id,
            )
            if existing:
                # Invalidate existing invitation
                await conn.execute(
                    "UPDATE client_invitations SET expires_at = NOW() WHERE id = $1",
                    existing["id"],
                )

            # Create new invitation
            invitation = await conn.fetchrow(
                """
                INSERT INTO client_invitations (client_id, email, token, expires_at, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, token, expires_at, created_at
                """,
                client_id,
                email,
                token,
                expires_at,
                created_by,
            )

            logger.info(f"Created invitation for client {client_id} ({email}) by {created_by}")

            return {
                "invitation_id": invitation["id"],
                "client_id": client_id,
                "client_name": client["full_name"],
                "email": email,
                "token": token,
                "expires_at": invitation["expires_at"].isoformat(),
                "invite_url": f"/portal/register?token={token}",
            }

    async def validate_token(self, token: str) -> dict[str, Any] | None:
        """
        Validate an invitation token.

        Args:
            token: Invitation token from URL

        Returns:
            Dict with invitation details if valid, None otherwise
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT i.id, i.client_id, i.email, i.expires_at, i.used_at,
                       c.full_name as client_name
                FROM client_invitations i
                JOIN clients c ON c.id = i.client_id
                WHERE i.token = $1
                """,
                token,
            )

            if not result:
                logger.warning(f"Invalid invitation token: {token[:8]}...")
                return None

            if result["used_at"] is not None:
                logger.warning(f"Token already used: {token[:8]}...")
                return {"error": "already_used", "message": "This invitation has already been used"}

            if result["expires_at"] < datetime.now(timezone.utc):
                logger.warning(f"Token expired: {token[:8]}...")
                return {"error": "expired", "message": "This invitation has expired"}

            return {
                "valid": True,
                "invitation_id": result["id"],
                "client_id": result["client_id"],
                "client_name": result["client_name"],
                "email": result["email"],
            }

    async def complete_registration(
        self,
        token: str,
        pin: str,
    ) -> dict[str, Any]:
        """
        Complete client registration by setting PIN.

        Args:
            token: Invitation token
            pin: Client's chosen PIN (4-6 digits)

        Returns:
            Dict with success status and user info
        """
        # Validate PIN format
        if not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
            raise ValueError("PIN must be 4-6 digits")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Get and validate invitation
                invitation = await conn.fetchrow(
                    """
                    SELECT i.id, i.client_id, i.email, i.expires_at, i.used_at,
                           c.full_name as client_name
                    FROM client_invitations i
                    JOIN clients c ON c.id = i.client_id
                    WHERE i.token = $1
                    FOR UPDATE
                    """,
                    token,
                )

                if not invitation:
                    raise ValueError("Invalid invitation token")

                if invitation["used_at"] is not None:
                    raise ValueError("Invitation already used")

                if invitation["expires_at"] < datetime.now(timezone.utc):
                    raise ValueError("Invitation expired")

                # Hash PIN
                pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

                # Check if team_member already exists for this client
                existing_user = await conn.fetchrow(
                    """
                    SELECT id FROM team_members
                    WHERE linked_client_id = $1
                    """,
                    invitation["client_id"],
                )

                if existing_user:
                    # Update existing user
                    await conn.execute(
                        """
                        UPDATE team_members
                        SET pin_hash = $1, active = true, portal_access = true
                        WHERE id = $2
                        """,
                        pin_hash,
                        existing_user["id"],
                    )
                    user_id = existing_user["id"]
                else:
                    # Create new team_member with role='client'
                    # Note: team_members has both 'name' (required) and 'full_name' columns
                    user = await conn.fetchrow(
                        """
                        INSERT INTO team_members (
                            name, email, full_name, role, pin_hash, active,
                            linked_client_id, portal_access
                        )
                        VALUES ($1, $2, $3, 'client', $4, true, $5, true)
                        RETURNING id
                        """,
                        invitation["client_name"],  # name (required)
                        invitation["email"],
                        invitation["client_name"],  # full_name
                        pin_hash,
                        invitation["client_id"],
                    )
                    user_id = user["id"]

                # Mark invitation as used
                await conn.execute(
                    """
                    UPDATE client_invitations
                    SET used_at = NOW()
                    WHERE id = $1
                    """,
                    invitation["id"],
                )

                # Create default preferences
                await conn.execute(
                    """
                    INSERT INTO client_preferences (client_id)
                    VALUES ($1)
                    ON CONFLICT (client_id) DO NOTHING
                    """,
                    invitation["client_id"],
                )

                logger.info(
                    f"Client registration completed: {invitation['email']} (client_id={invitation['client_id']})"
                )

                return {
                    "success": True,
                    "user_id": user_id,
                    "client_id": invitation["client_id"],
                    "email": invitation["email"],
                    "name": invitation["client_name"],
                }

    async def get_client_invitations(
        self,
        client_id: int,
    ) -> list[dict[str, Any]]:
        """Get all invitations for a client."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, email, expires_at, used_at, created_by, created_at
                FROM client_invitations
                WHERE client_id = $1
                ORDER BY created_at DESC
                """,
                client_id,
            )

            return [
                {
                    "id": row["id"],
                    "email": row["email"],
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                    "used_at": row["used_at"].isoformat() if row["used_at"] else None,
                    "created_by": row["created_by"],
                    "created_at": row["created_at"].isoformat(),
                    "status": "used"
                    if row["used_at"]
                    else (
                        "expired" if row["expires_at"] < datetime.now(timezone.utc) else "pending"
                    ),
                }
                for row in rows
            ]

    async def resend_invitation(
        self,
        client_id: int,
        created_by: str,
    ) -> dict[str, Any]:
        """Resend invitation to a client (creates new token)."""
        async with self.pool.acquire() as conn:
            # Get client email
            client = await conn.fetchrow(
                "SELECT email FROM clients WHERE id = $1",
                client_id,
            )
            if not client or not client["email"]:
                raise ValueError("Client not found or has no email")

            return await self.create_invitation(
                client_id=client_id,
                email=client["email"],
                created_by=created_by,
            )
