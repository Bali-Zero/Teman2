"""
Client Portal Magic-Link (passwordless) Login Service — FASE 6.

Flow:
1. Client requests a login link by email (`request_magic_link`).
2. We mint a single-use, 15-minute token, store ONLY its sha256 hash, and email
   the raw token as a link via Brevo (`from=zantara@balizero.com`).
3. Client clicks the link; `verify_magic_link` re-hashes the raw token, checks it
   is unused + unexpired, marks it used, and returns the registered portal user so
   the router can issue the same JWT + cookies as a PIN login.

Security posture:
- Raw token never stored (hash at rest — superscar #4 secret-in-the-clear).
- Single-use (`used_at`), short TTL, replay-proof (UNIQUE token_hash).
- Enumeration-safe: `request_magic_link` returns the SAME result whether or not
  the email maps to a registered portal client. The caller surfaces a generic
  "if the account exists, a link was sent" message.
- Rate-limited per email (max N live tokens / window) to blunt mailbox flooding.

Distinct from `InviteService` (registration / PIN-set, 72h, plaintext token).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Token: 32 bytes urlsafe ≈ 43 chars of entropy; sha256 → 64 hex chars at rest.
MAGIC_TOKEN_BYTES = 32
MAGIC_LINK_TTL_MINUTES = 15
# Anti-flood: at most this many UNUSED, still-valid tokens per email at once.
MAX_LIVE_TOKENS_PER_EMAIL = 3


def _hash_token(raw_token: str) -> str:
    """sha256 hex of the raw token (what we persist + match on)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class MagicLinkService:
    """Passwordless login for already-registered portal clients."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def request_magic_link(
        self,
        email: str,
        *,
        created_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Mint a magic-link token for `email` IF it is a registered portal client.

        Returns a dict that is identical in shape regardless of whether the email
        exists (enumeration-safe). When the email IS a portal client, the dict
        carries the raw `token` so the router can build + send the email; when it
        is not, `token` is None and no row is written.

        The caller MUST NOT leak the difference to the HTTP response body.
        """
        normalized = (email or "").strip().lower()
        if not normalized:
            return {"email": email, "token": None, "is_client": False}

        async with self.pool.acquire() as conn:
            # Only registered, active portal clients may receive a magic link.
            user = await conn.fetchrow(
                """
                SELECT id, email, full_name, role, portal_access, active
                FROM team_members
                WHERE LOWER(email) = $1
                  AND role = 'client'
                  AND active = true
                  AND portal_access = true
                """,
                normalized,
            )
            if not user:
                # Enumeration-safe: same external behaviour as the happy path.
                logger.info("Magic-link requested for non-portal email (no-op)")
                return {"email": email, "token": None, "is_client": False}

            # Anti-flood: count live (unused, unexpired) tokens for this email.
            live = await conn.fetchval(
                """
                SELECT count(*) FROM magic_link_tokens
                WHERE LOWER(email) = $1
                  AND used_at IS NULL
                  AND expires_at > NOW()
                """,
                normalized,
            )
            if live and live >= MAX_LIVE_TOKENS_PER_EMAIL:
                logger.warning("Magic-link rate limit hit for a portal client (suppressed)")
                # Still enumeration-safe: report success without minting more.
                return {
                    "email": user["email"],
                    "token": None,
                    "is_client": True,
                    "rate_limited": True,
                    "name": user["full_name"],
                }

            raw_token = secrets.token_urlsafe(MAGIC_TOKEN_BYTES)
            token_hash = _hash_token(raw_token)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_TTL_MINUTES)

            await conn.execute(
                """
                INSERT INTO magic_link_tokens (email, token_hash, expires_at, created_ip)
                VALUES ($1, $2, $3, $4)
                """,
                user["email"],
                token_hash,
                expires_at,
                created_ip,
            )

            logger.info("Magic-link minted for a portal client (ttl=%dm)", MAGIC_LINK_TTL_MINUTES)
            return {
                "email": user["email"],
                "token": raw_token,
                "is_client": True,
                "name": user["full_name"],
                "expires_at": expires_at.isoformat(),
            }

    async def verify_magic_link(self, raw_token: str) -> dict[str, Any] | None:
        """
        Validate + consume a magic-link token.

        Returns the registered portal user (id/email/name/role) on success, or
        None if the token is unknown, already used, or expired. The match + the
        single-use mark happen in one transaction with `FOR UPDATE` to prevent a
        double-spend race.
        """
        if not raw_token:
            return None
        token_hash = _hash_token(raw_token.strip())

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, email, expires_at, used_at
                    FROM magic_link_tokens
                    WHERE token_hash = $1
                    FOR UPDATE
                    """,
                    token_hash,
                )
                if not row:
                    logger.warning("Magic-link verify: unknown token")
                    return None
                if row["used_at"] is not None:
                    logger.warning("Magic-link verify: token already used")
                    return None
                if row["expires_at"] < datetime.now(timezone.utc):
                    logger.warning("Magic-link verify: token expired")
                    return None

                # Consume the token (single-use).
                await conn.execute(
                    "UPDATE magic_link_tokens SET used_at = NOW() WHERE id = $1",
                    row["id"],
                )

                # Resolve the live portal user (re-check active/portal_access at
                # verify time — access may have been revoked since the request).
                user = await conn.fetchrow(
                    """
                    SELECT id, email, COALESCE(full_name, name) AS name, role
                    FROM team_members
                    WHERE LOWER(email) = LOWER($1)
                      AND role = 'client'
                      AND active = true
                      AND portal_access = true
                    """,
                    row["email"],
                )
                if not user:
                    logger.warning("Magic-link verify: user no longer eligible")
                    return None

                logger.info("Magic-link consumed — portal login granted")
                return {
                    "id": str(user["id"]),
                    "email": user["email"],
                    "name": user["name"],
                    "role": user["role"],
                }
