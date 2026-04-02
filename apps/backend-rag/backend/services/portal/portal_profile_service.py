"""
Portal Profile Service — auto-creates team_members records for CRM clients.

When a client is created in the CRM, this service ensures a matching
team_members record exists with role='client' so the portal can display
their data without waiting for a manual invite.

The pin_hash is set to a placeholder. The client sets their real PIN
when invited via the existing invite flow.
"""

import asyncpg

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Placeholder bcrypt hash for "$NOLOGIN$" — login attempts will never match.
# The real pin_hash is set when the client completes registration via invite.
_PLACEHOLDER_PIN_HASH = "$2b$12$000000000000000000000uNOLOGIN.placeholder.hash.nevermatches"


class PortalProfileService:
    """Creates and manages portal profiles (team_members with role='client')."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def ensure_portal_profile(
        self,
        client_id: int,
        email: str | None,
        full_name: str,
    ) -> str | None:
        """
        Ensure a team_members record exists for this client.

        Returns the team_member id (UUID string) or None if skipped/failed.
        Non-blocking: DB errors are caught and logged, never raised.
        """
        if not email or not email.strip():
            logger.warning(
                f"Skipping portal profile for client {client_id}: no email",
            )
            return None

        email = email.strip().lower()

        try:
            async with self.pool.acquire() as conn:
                member_id = await conn.fetchval(
                    """
                    INSERT INTO team_members (
                        name, email, pin_hash, role,
                        linked_client_id, portal_access, active
                    )
                    VALUES ($1, $2, $3, 'client', $4, true, true)
                    ON CONFLICT (email) DO UPDATE
                        SET linked_client_id = EXCLUDED.linked_client_id,
                            portal_access = true,
                            name = EXCLUDED.name
                        WHERE team_members.role = 'client'
                    RETURNING id
                    """,
                    full_name,
                    email,
                    _PLACEHOLDER_PIN_HASH,
                    client_id,
                )

                logger.info(
                    f"Portal profile ensured for client {client_id} "
                    f"(email={email}, member_id={member_id})",
                )
                return member_id

        except Exception as e:
            logger.error(
                f"Failed to create portal profile for client {client_id}: {e}",
            )
            return None
