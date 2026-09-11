"""
Client Portal Invite Service

Handles client invitation flow:
1. Team sends invite to client email
2. Client clicks link, validates token
3. Client creates PIN to complete registration
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import bcrypt

from backend.app.utils.logging_utils import get_logger
from backend.services.common.cache import cache_invalidating
from backend.services.portal.portal_profile_service import PLACEHOLDER_PIN_HASH

logger = get_logger(__name__)

# Constants
INVITE_TOKEN_LENGTH = 64
INVITE_EXPIRY_HOURS = 72  # 3 days

# The path an invitation link points at, relative to `settings.frontend_portal_url`.
# A constant rather than an inline f-string because the ROUTER concatenates the two
# halves and the router's tests used to hand-write the other half — they asserted a
# `/portal/invite?token=` link that this service has not produced for a long time, so
# a test could stay green while the real link rotted (cross-family review, 2026-09-10).
INVITE_PATH_TEMPLATE = "/portal/register?token={token}"

# A stored invitation token is a sha256 hex digest: 64 lowercase hex chars.
# A RAW token is `secrets.token_urlsafe(64)` — ~86 base64url chars — so the
# two shapes can never be confused, which is what makes the legacy read path
# below safe (see `_LEGACY_PLAINTEXT_PREDICATE`).
_HASHED_TOKEN_RE = "^[0-9a-f]{64}$"


def _hash_token(raw_token: str) -> str:
    """sha256 hex of the raw token — what we persist and match on.

    Mirrors `magic_link_service._hash_token`, whose module docstring already
    contrasted itself against this service ("72h, plaintext token"). A raw
    `client_invitations.token` is a live, unused, 72h-valid registration
    credential: anyone who can read that table — a DB console, a future
    export endpoint, a logging accident — could redeem it without ever
    touching the client's mailbox (portal audit finding, authz F1).
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# Rows written BEFORE this change still hold a plaintext token, so the two
# read paths accept either. The predicate is not cosmetic: without it, the
# value stored in the row would itself be a working credential again — an
# attacker reading the table could submit the stored hash AS the token and
# the plaintext branch would match it. Restricting the plaintext branch to
# rows that do NOT look like a digest closes that door.
#
# Those legacy rows are not scrubbed here. Measured on production
# 2026-09-11: 245 invitation rows, ZERO of them live (`used_at IS NULL AND
# expires_at > NOW()`), so every plaintext token still on disk is already
# spent or expired and cannot be redeemed. Rewriting them is a one-line
# UPDATE against a hot-zone migration path (deterministic floor 3) for no
# change in exposure, so it is left as an operator-run follow-up:
#   UPDATE client_invitations
#      SET token = encode(sha256(token::bytea), 'hex')
#    WHERE token !~ '^[0-9a-f]{64}$';
# (verified equal to Python's sha256 for the same input). Once that has
# run, this branch matches nothing and can be deleted.
_LEGACY_PLAINTEXT_PREDICATE = (
    "(i.token = $1 OR (i.token = $2 AND i.token !~ '" + _HASHED_TOKEN_RE + "'))"
)


class InviteService:
    """Service for managing client portal invitations."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @cache_invalidating(
        [
            lambda self, client_id, *a, **k: f"zantara:portal_invitations:{client_id}:*",
            "zantara:portal_invitations:*",
        ]
    )
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
            # Check if client exists and is not archived — an archived client
            # must never be (re-)invited into an active portal account.
            client = await conn.fetchrow(
                "SELECT id, full_name, email FROM clients WHERE id = $1 AND deleted_at IS NULL",
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
                RETURNING id, expires_at, created_at
                """,
                client_id,
                email,
                _hash_token(token),
                expires_at,
                created_by,
            )

            # The address is deliberately NOT interpolated here. This line pre-dates
            # the outbox: it was written for the human-triggered
            # `/api/portal/invite/send` endpoint, where a staff member already had
            # the address on screen. It now also fires UNATTENDED on every paid
            # GARUDA order, which turns it into a steady stream of client PII into
            # a persisted log (SYMBIOSIS Law 2 / UU PDP) that no Sentry scrubber
            # touches — `_before_send` filters events, not log sinks. `client_id`
            # identifies the row for anyone debugging; the address adds nothing.
            logger.info("Created invitation for client %s by %s", client_id, created_by)

            return {
                "invitation_id": invitation["id"],
                "client_id": client_id,
                "client_name": client["full_name"],
                "email": email,
                "token": token,
                "expires_at": invitation["expires_at"].isoformat(),
                "invite_url": INVITE_PATH_TEMPLATE.format(token=token),
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
                JOIN clients c ON c.id = i.client_id AND c.deleted_at IS NULL
                WHERE """
                + _LEGACY_PLAINTEXT_PREDICATE,
                _hash_token(token),
                token,
            )

            if not result:
                # The DIGEST prefix, never the raw token's: a log line is
                # storage too, and these three used to print the first 8
                # characters of a live 72h credential.
                logger.warning("Invalid invitation token: %s...", _hash_token(token)[:8])
                return None

            if result["used_at"] is not None:
                logger.warning("Token already used: %s...", _hash_token(token)[:8])
                return {"error": "already_used", "message": "This invitation has already been used"}

            if result["expires_at"] < datetime.now(timezone.utc):
                logger.warning("Token expired: %s...", _hash_token(token)[:8])
                return {"error": "expired", "message": "This invitation has expired"}

            return {
                "valid": True,
                "invitation_id": result["id"],
                "client_id": result["client_id"],
                "client_name": result["client_name"],
                "email": result["email"],
            }

    @cache_invalidating(
        [
            "zantara:portal_invitations:*",
            "zantara:crm_clients:*",
        ]
    )
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
                    JOIN clients c ON c.id = i.client_id AND c.deleted_at IS NULL
                    WHERE """
                    + _LEGACY_PLAINTEXT_PREDICATE
                    + """
                    FOR UPDATE
                    """,
                    _hash_token(token),
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
                    SELECT id, active, pin_hash FROM team_members
                    WHERE linked_client_id = $1
                    ORDER BY (role = 'client') DESC, created_at
                    """,
                    invitation["client_id"],
                )

                if existing_user:
                    # Consuming an invitation is not proof the consumer controls
                    # the client's mailbox — it must never function as a
                    # password reset on a LIVE account.
                    #
                    # `active` alone cannot express "live": `create_client` calls
                    # `ensure_portal_profile`, which provisions EVERY CRM client as
                    # `active=true` carrying PLACEHOLDER_PIN_HASH. Gating on the
                    # flag therefore refuses the ordinary first-time registration
                    # — the very flow this guard exists to protect — while the
                    # takeover it targets keeps working on any account that
                    # happens to be inactive.
                    #
                    # The credential itself is the honest signal: a row still
                    # holding the placeholder has never been registered, so
                    # writing the first real PIN over it is onboarding, not
                    # takeover. Both other cases stay as before — a real PIN on
                    # an active row is refused, and a deactivated account may be
                    # re-onboarded.
                    already_registered = existing_user["pin_hash"] != PLACEHOLDER_PIN_HASH
                    if already_registered and existing_user["active"]:
                        raise ValueError("This client already has an active portal account")

                    # The login identity must be the address the invitation
                    # was SENT to, or registration succeeds and login fails.
                    #
                    # Measured 2026-09-11 (portal audit F1): `update_client`
                    # lets a consultant change `clients.email` freely, the
                    # re-invite correctly goes to the NEW address, the client
                    # sets a PIN through it — and then cannot sign in, because
                    # `auth.py`'s login matches `team_members.email` only and
                    # this UPDATE never touched it. `ensure_portal_profile`
                    # cannot repair it either: `email` IS its ON CONFLICT key.
                    # Nothing surfaced the failure to either side; the CRM
                    # panel kept reporting "Portal active — <dead address>".
                    invite_email = invitation["email"]
                    if invite_email:
                        # team_members.email is unique. A different row already
                        # holding it is a real identity collision, not something
                        # to overwrite silently — refuse and say so.
                        conflict = await conn.fetchval(
                            """
                            SELECT id FROM team_members
                            WHERE LOWER(email) = LOWER($1) AND id <> $2
                            LIMIT 1
                            """,
                            invite_email,
                            existing_user["id"],
                        )
                        if conflict:
                            raise ValueError(
                                "Another account already uses this email address"
                            )

                    # Update existing (never-registered or deactivated) user
                    await conn.execute(
                        """
                        UPDATE team_members
                        SET pin_hash = $1,
                            active = true,
                            portal_access = true,
                            email = COALESCE($3, email)
                        WHERE id = $2
                        """,
                        pin_hash,
                        existing_user["id"],
                        invite_email,
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
                    f"Client registration completed: {invitation['email']} (client_id={invitation['client_id']})",
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

    @cache_invalidating(
        [
            lambda self, client_id, *a, **k: f"zantara:portal_invitations:{client_id}:*",
            "zantara:portal_invitations:*",
        ]
    )
    async def resend_invitation(
        self,
        client_id: int,
        created_by: str,
    ) -> dict[str, Any]:
        """Resend invitation to a client (creates new token)."""
        async with self.pool.acquire() as conn:
            # Get client email — archived clients are excluded so an archived
            # client can't be re-invited via the resend path either.
            client = await conn.fetchrow(
                "SELECT email FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )
            if not client or not client["email"]:
                raise ValueError("Client not found or has no email")

            return await self.create_invitation(
                client_id=client_id,
                email=client["email"],
                created_by=created_by,
            )
