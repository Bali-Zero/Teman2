"""
Zoho OAuth Service

Handles OAuth 2.0 authentication flow, token exchange, storage, and auto-refresh.

Features:
- Authorization URL generation with CSRF state
- Token exchange (authorization code -> access/refresh tokens)
- Automatic token refresh before expiry
- Secure token storage in PostgreSQL
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import httpx

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants

logger = logging.getLogger(__name__)


# One user can own SEVERAL rows in `zoho_email_tokens`: reconnecting through
# /admin/zoho/auth inserts a row rather than replacing one, and the live table
# carries duplicate pairs for a single mailbox. Every read below used to be a
# bare `WHERE user_id = $1` with no ORDER BY, so which row answered was
# undefined — and worse, two reads could answer from two DIFFERENT rows,
# pairing one row's account id with another row's access token.
#
# Not hypothetical: user 7dfe56b2 owns two rows for the same mailbox, and the
# unusable one answered. Its `account_id` holds an e-mail address instead of the
# numeric Zoho accountId, and its `api_domain` points at zohoapis.com instead of
# the Mail API host, so every request built from it 404s with
# URL_RULE_NOT_CONFIGURED — a failure that looks nothing like "you picked the
# wrong row".
#
# Zoho only accepts a numeric accountId in the URL path, so a well-formed row
# wins over a malformed one; recency breaks the next tie; `id` makes the order
# total, so the SAME row answers every read. COALESCE keeps a NULL account_id
# from sorting first (in Postgres, DESC means NULLS FIRST by default), which
# would have re-created the bug with a different unusable row.
_TOKEN_ROW_ORDER = (
    "ORDER BY (COALESCE(account_id, '') ~ '^[0-9]+$') DESC, "
    "updated_at DESC NULLS LAST, id DESC "
    "LIMIT 1"
)


class ZohoOAuthService:
    """
    Manages Zoho OAuth 2.0 authentication flow and token lifecycle.
    """

    # Required OAuth scopes for full email functionality
    SCOPES = [
        "ZohoMail.accounts.READ",
        "ZohoMail.messages.READ",
        "ZohoMail.messages.CREATE",
        "ZohoMail.messages.UPDATE",
        "ZohoMail.messages.DELETE",
        "ZohoMail.folders.READ",
        # Provisioning the mail loop's routing folders (_Visa, _Tax, ...) needs
        # more than READ: with READ alone `POST /folders` answers 401
        # INVALID_OAUTHSCOPE while listing the very same folders succeeds —
        # measured, not inferred. CREATE and not ALL on purpose: nothing in this
        # system has any business deleting a folder, and a grant is the wrong
        # place to be generous.
        "ZohoMail.folders.CREATE",
        "ZohoMail.attachments.READ",
        "ZohoMail.attachments.CREATE",
    ]

    # Refresh token before expiry (5 minutes buffer)
    TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        """
        Initialize ZohoOAuthService.

        Args:
            db_pool: PostgreSQL connection pool
        """
        self.db_pool = db_pool
        self.client_id = settings.zoho_client_id
        self.client_secret = settings.zoho_client_secret
        self.redirect_uri = settings.zoho_redirect_uri
        self.accounts_url = settings.zoho_accounts_url
        self.api_domain = settings.zoho_api_domain
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=HttpTimeoutConstants.ZOHO_OAUTH_TIMEOUT,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def get_authorization_url(self, state: str) -> str:
        """
        Generate Zoho OAuth authorization URL.

        Args:
            state: CSRF protection state token (should include user_id)

        Returns:
            Full authorization URL to redirect user to
        """
        if not self.client_id:
            raise ValueError("Zoho OAuth not configured: ZOHO_CLIENT_ID missing")

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(self.SCOPES),
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Always show consent screen
            "state": state,
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.accounts_url}/oauth/v2/auth?{query_string}"

    async def exchange_code(self, code: str, user_id: str) -> dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback
            user_id: User ID to associate tokens with

        Returns:
            Token response data

        Raises:
            ValueError: If token exchange fails
        """
        logger.debug("Starting OAuth code exchange for user %s", user_id)

        if not self.client_id or not self.client_secret:
            logger.error("Zoho OAuth not configured - missing credentials")
            raise ValueError("Zoho OAuth not configured")

        try:
            client = self._get_client()
            token_url = f"{self.accounts_url}/oauth/v2/token"

            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
            )

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                logger.error(
                    f"Zoho token exchange failed: {response.status_code} - {error_data.get('error', 'unknown')}",
                )
                raise ValueError(
                    f"Token exchange failed: {error_data.get('error', 'unknown error')}",
                )

            token_data = response.json()

            if "error" in token_data:
                logger.error(f"Zoho OAuth error: {token_data.get('error')}")
                raise ValueError(f"OAuth error: {token_data.get('error')}")

            # Get account information
            account_info = await self._get_account_info(token_data["access_token"])

            # Store tokens in database
            await self._store_tokens(
                user_id=user_id,
                account_id=account_info["account_id"],
                email_address=account_info["email"],
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", ""),
                expires_in=token_data.get("expires_in", 3600),
            )

            logger.info(f"Zoho OAuth connected for user {user_id}: {account_info['email']}")
            return token_data

        except httpx.RequestError as e:
            logger.error(f"Zoho OAuth network error: {type(e).__name__}: {e}")
            raise ValueError(f"Network error during token exchange: {e}") from e

    async def _get_account_info(self, access_token: str) -> dict[str, str]:
        """
        Get Zoho account information using access token.

        Args:
            access_token: Valid Zoho access token

        Returns:
            Dict with account_id and email
        """
        client = self._get_client()
        response = await client.get(
            f"{self.api_domain}/api/accounts",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        )

        if response.status_code != 200:
            logger.error(f"Failed to get Zoho account info: {response.status_code}")
            raise ValueError("Failed to get account information")

        data = response.json()
        accounts = data.get("data", [])

        if not accounts:
            raise ValueError("No Zoho Mail accounts found")

        # Use first account
        account = accounts[0]

        # Extract primary email from email list
        # Zoho returns email as list: [{"isPrimary": true, "mailId": "...", ...}]
        email_list = account.get("email", [])
        primary_email = ""

        if isinstance(email_list, list):
            for email_entry in email_list:
                if isinstance(email_entry, dict) and email_entry.get("isPrimary"):
                    primary_email = email_entry.get("mailId", "")
                    break
            # Fallback to first email if no primary found
            if not primary_email and email_list and isinstance(email_list[0], dict):
                primary_email = email_list[0].get("mailId", "")
        elif isinstance(email_list, str):
            primary_email = email_list

        # Also check for emailAddress field as fallback
        if not primary_email:
            primary_email = account.get("emailAddress", "")

        # Ensure email is always a string (edge case safeguard)
        if not isinstance(primary_email, str):
            logger.warning(f"Unexpected email type: {type(primary_email)}")
            if isinstance(primary_email, list) and primary_email:
                first_item = primary_email[0]
                primary_email = (
                    str(first_item.get("mailId", ""))
                    if isinstance(first_item, dict)
                    else str(first_item)
                    if first_item
                    else ""
                )
            elif isinstance(primary_email, dict):
                primary_email = str(primary_email.get("mailId", ""))
            else:
                primary_email = str(primary_email) if primary_email else ""

        # Final validation
        if not primary_email or "@" not in primary_email:
            logger.error("Invalid email extracted from Zoho account: '%s'", primary_email)
            raise ValueError("Could not extract valid email address from Zoho account")

        return {
            "account_id": str(account.get("accountId", "")),
            "email": primary_email,
        }

    async def _store_tokens(
        self,
        user_id: str,
        account_id: str,
        email_address: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        """
        Store OAuth tokens in database.

        Args:
            user_id: User ID
            account_id: Zoho account ID
            email_address: Email address
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiry in seconds
        """
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO zoho_email_tokens (
                    user_id, account_id, email_address, access_token, refresh_token,
                    token_expires_at, scopes, api_domain, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                ON CONFLICT (user_id, account_id) DO UPDATE SET
                    email_address = EXCLUDED.email_address,
                    access_token = EXCLUDED.access_token,
                    refresh_token = COALESCE(NULLIF(EXCLUDED.refresh_token, ''), zoho_email_tokens.refresh_token),
                    token_expires_at = EXCLUDED.token_expires_at,
                    updated_at = NOW()
                """,
                user_id,
                account_id,
                email_address,
                access_token,
                refresh_token,
                expires_at,
                self.SCOPES,
                self.api_domain,
            )

    async def get_valid_token(self, user_id: str) -> str:
        """
        Get a valid access token, refreshing if needed.

        Args:
            user_id: User ID

        Returns:
            Valid access token

        Raises:
            ValueError: If no token found or refresh fails
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT access_token, refresh_token, token_expires_at, account_id
                FROM zoho_email_tokens
                WHERE user_id = $1
                {_TOKEN_ROW_ORDER}
                """,
                user_id,
            )

            if not row:
                raise ValueError("No Zoho account connected")

            expires_at = row["token_expires_at"]
            now = datetime.now(timezone.utc)

            # If token is marked as permanently invalid (> 6 months ago), skip refresh attempt
            if expires_at <= now - timedelta(days=180):
                raise ValueError("Zoho token invalidated — reconnect required at /admin/zoho/auth")

            # Check if token is expired or about to expire
            if expires_at <= now + self.TOKEN_EXPIRY_BUFFER:
                logger.info("Refreshing Zoho token for user %s", user_id)
                return await self._refresh_token(
                    user_id=user_id,
                    account_id=row["account_id"],
                    refresh_token=row["refresh_token"],
                )

            return row["access_token"]

    async def _refresh_token(self, user_id: str, account_id: str, refresh_token: str) -> str:
        """
        Refresh an expired access token.

        Args:
            user_id: User ID
            account_id: Zoho account ID
            refresh_token: Refresh token

        Returns:
            New access token

        Raises:
            ValueError: If refresh fails
        """
        if not refresh_token:
            raise ValueError(
                "No refresh token stored — reconnect required at /admin/zoho/auth"
            )

        client = self._get_client()
        response = await client.post(
            f"{self.accounts_url}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            },
        )

        if response.status_code != 200:
            # A transport-level failure, NOT a statement about this user's grant.
            # 429, 502, 503 and a proxy hiccup all land here, and they are all
            # retryable. Saying "reconnect required" for them sends whoever reads
            # it to re-run the OAuth consent — which is the very act that created
            # the duplicate rows this file now has to order around. The wording is
            # load-bearing: `mail_loop.cli` decides between "retry tomorrow" and
            # "only a human can fix this" by looking for the consent endpoint in
            # the message, so a retryable fault must not name it.
            error_data = response.json() if response.content else {}
            logger.error(f"Token refresh failed: {response.status_code} - {error_data}")
            raise ValueError(
                f"Token refresh temporarily unavailable (HTTP {response.status_code}) — "
                "retryable, not a consent problem"
            )

        token_data = response.json()

        if "error" in token_data:
            # Zoho answers HTTP 200 with the error in the BODY, so the status code
            # above proves nothing. Read the reply.
            zoho_error = str(token_data.get("error") or "")
            logger.error("Token refresh error: %s", token_data)

            # `invalid_client` is a statement about the CALLER — our client id and
            # secret are wrong or missing on this host. It says nothing whatsoever
            # about the user's token, so recording it as a dead user token
            # invalidates a working grant for every OTHER consumer, including a
            # host that is correctly configured.
            #
            # Measured, not reasoned: on 2026-08-04 three production rows for
            # zero@balizero.com were stamped dead in a few minutes by a machine
            # that merely lacked ZOHO_CLIENT_ID. They had to be restored by hand.
            # A caller-side fault must never be written onto the user's row.
            if zoho_error == "invalid_client":
                raise ValueError(
                    "Zoho rejected OUR client credentials (invalid_client): "
                    "ZOHO_CLIENT_ID/ZOHO_CLIENT_SECRET are wrong or missing on "
                    "this host. The stored token was left untouched."
                )

            # Invalidate stored token so we stop retrying on every request
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE zoho_email_tokens
                    SET token_expires_at = NOW() - INTERVAL '1 year',
                        updated_at = NOW()
                    WHERE user_id = $1 AND account_id = $2
                    """,
                    user_id,
                    account_id,
                )
            raise ValueError(
                f"Zoho refused the refresh ({zoho_error}) — "
                "reconnect required at /admin/zoho/auth"
            )

        # Update stored token
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600),
        )

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE zoho_email_tokens
                SET access_token = $1, token_expires_at = $2, updated_at = NOW()
                WHERE user_id = $3 AND account_id = $4
                """,
                token_data["access_token"],
                expires_at,
                user_id,
                account_id,
            )

        logger.info("Zoho token refreshed for user %s", user_id)
        return token_data["access_token"]

    async def get_account_id(self, user_id: str) -> str:
        """
        Get stored Zoho account ID for user.

        Args:
            user_id: User ID

        Returns:
            Zoho account ID

        Raises:
            ValueError: If no account found
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT account_id FROM zoho_email_tokens WHERE user_id = $1 "
                f"{_TOKEN_ROW_ORDER}",
                user_id,
            )

            if not row:
                raise ValueError("No Zoho account connected")

            return row["account_id"]

    async def get_connection_status(self, user_id: str) -> dict[str, Any]:
        """
        Get Zoho connection status for user.

        Args:
            user_id: User ID

        Returns:
            Connection status dict
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT account_id, email_address, token_expires_at, api_domain
                FROM zoho_email_tokens
                WHERE user_id = $1
                {_TOKEN_ROW_ORDER}
                """,
                user_id,
            )

            if not row:
                return {
                    "connected": False,
                    "email": None,
                    "account_id": None,
                    "expires_at": None,
                }

            return {
                "connected": True,
                "email": row["email_address"],
                "account_id": row["account_id"],
                "expires_at": row["token_expires_at"].isoformat()
                if row["token_expires_at"]
                else None,
                "api_domain": row["api_domain"],
            }

    async def disconnect(self, user_id: str) -> bool:
        """
        Disconnect Zoho account and remove tokens.

        Args:
            user_id: User ID

        Returns:
            True if disconnected successfully
        """
        async with self.db_pool.acquire() as conn:
            # EVERY refresh token, not the first one an unordered query happened
            # to return: the DELETE below is already unconditional across all of
            # the user's rows, so revoking one of N left the other N-1 grants
            # live at Zoho AND unrevocable, because the only copy of each token
            # had just been deleted. Disconnect has to mean disconnected.
            rows = await conn.fetch(
                "SELECT refresh_token FROM zoho_email_tokens "
                "WHERE user_id = $1 AND refresh_token IS NOT NULL",
                user_id,
            )

            for row in rows:
                # Best-effort, as before: a revoke that fails must not stop the
                # local disconnect, or a Zoho outage would pin the user to an
                # account they asked to leave.
                try:
                    client = self._get_client()
                    await client.post(
                        f"{self.accounts_url}/oauth/v2/token/revoke",
                        params={"token": row["refresh_token"]},
                    )
                except Exception as e:
                    logger.warning("Failed to revoke Zoho token: %s", e)

            # Delete from database
            await conn.execute(
                "DELETE FROM zoho_email_tokens WHERE user_id = $1",
                user_id,
            )

            # Also clear email cache
            await conn.execute(
                "DELETE FROM zoho_email_cache WHERE user_id = $1",
                user_id,
            )

            logger.info("Zoho account disconnected for user %s", user_id)
            return True
