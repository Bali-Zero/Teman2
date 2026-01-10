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

from app.core.config import settings
from app.core.constants import HttpTimeoutConstants

logger = logging.getLogger(__name__)


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
        "ZohoMail.attachments.READ",
        "ZohoMail.attachments.CREATE",
    ]

    # Refresh token before expiry (5 minutes buffer)
    TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)

    def __init__(self, db_pool: asyncpg.Pool):
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
        logger.debug(f"Starting OAuth code exchange for user {user_id}")

        if not self.client_id or not self.client_secret:
            logger.error("Zoho OAuth not configured - missing credentials")
            raise ValueError("Zoho OAuth not configured")

        try:
            async with httpx.AsyncClient(timeout=HttpTimeoutConstants.ZOHO_OAUTH_TIMEOUT) as client:
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
                        f"Zoho token exchange failed: {response.status_code} - {error_data.get('error', 'unknown')}"
                    )
                    raise ValueError(
                        f"Token exchange failed: {error_data.get('error', 'unknown error')}"
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
            raise ValueError(f"Network error during token exchange: {e}")

    async def _get_account_info(self, access_token: str) -> dict[str, str]:
        """
        Get Zoho account information using access token.

        Args:
            access_token: Valid Zoho access token

        Returns:
            Dict with account_id and email
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                        else str(first_item) if first_item else ""
                    )
                elif isinstance(primary_email, dict):
                    primary_email = str(primary_email.get("mailId", ""))
                else:
                    primary_email = str(primary_email) if primary_email else ""

            # Final validation
            if not primary_email or "@" not in primary_email:
                logger.error(f"Invalid email extracted from Zoho account: '{primary_email}'")
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
                """
                SELECT access_token, refresh_token, token_expires_at, account_id
                FROM zoho_email_tokens
                WHERE user_id = $1
                """,
                user_id,
            )

            if not row:
                raise ValueError("No Zoho account connected")

            expires_at = row["token_expires_at"]
            now = datetime.now(timezone.utc)

            # Check if token is expired or about to expire
            if expires_at <= now + self.TOKEN_EXPIRY_BUFFER:
                logger.info(f"Refreshing Zoho token for user {user_id}")
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
            raise ValueError("No refresh token available - reconnect required")

        async with httpx.AsyncClient(timeout=30.0) as client:
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
                error_data = response.json() if response.content else {}
                logger.error(f"Token refresh failed: {response.status_code} - {error_data}")
                raise ValueError("Failed to refresh token - reconnect required")

            token_data = response.json()

            if "error" in token_data:
                logger.error(f"Token refresh error: {token_data}")
                raise ValueError(f"Refresh error: {token_data.get('error')}")

            # Update stored token
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token_data.get("expires_in", 3600)
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

            logger.info(f"Zoho token refreshed for user {user_id}")
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
                "SELECT account_id FROM zoho_email_tokens WHERE user_id = $1",
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
                """
                SELECT account_id, email_address, token_expires_at, api_domain
                FROM zoho_email_tokens
                WHERE user_id = $1
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
            # Get refresh token to revoke
            row = await conn.fetchrow(
                "SELECT refresh_token FROM zoho_email_tokens WHERE user_id = $1",
                user_id,
            )

            if row and row["refresh_token"]:
                # Attempt to revoke token (optional, may fail)
                try:
                    async with httpx.AsyncClient(timeout=HttpTimeoutConstants.SHORT_TIMEOUT) as client:
                        await client.post(
                            f"{self.accounts_url}/oauth/v2/token/revoke",
                            params={"token": row["refresh_token"]},
                        )
                except Exception as e:
                    logger.warning(f"Failed to revoke Zoho token: {e}")

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

            logger.info(f"Zoho account disconnected for user {user_id}")
            return True
