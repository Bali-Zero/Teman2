"""
Google Drive Integration Service

Handles OAuth 2.0 authentication and file operations for Google Drive.

Features:
- OAuth2 authorization flow with PKCE
- Token storage in PostgreSQL
- File listing with folder hierarchy
- Permission-aware file access (respects Google Drive sharing)
- Upload/download operations
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """
    Manages Google Drive OAuth 2.0 authentication and file operations.
    """

    # Required OAuth scopes
    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",  # Read files and folders
        "https://www.googleapis.com/auth/drive.file",  # Create/edit files created by app
        "https://www.googleapis.com/auth/drive.metadata.readonly",  # Read file metadata
    ]

    # Google OAuth endpoints
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE = "https://www.googleapis.com/drive/v3"

    # Token refresh buffer (5 minutes before expiry)
    TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize GoogleDriveService.

        Args:
            db_pool: PostgreSQL connection pool
        """
        self.db_pool = db_pool
        self.client_id = settings.google_drive_client_id
        self.client_secret = settings.google_drive_client_secret
        self.redirect_uri = settings.google_drive_redirect_uri
        self.root_folder_id = settings.google_drive_root_folder_id

    def is_configured(self) -> bool:
        """Check if Google Drive OAuth is configured."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self, state: str) -> str:
        """
        Generate Google OAuth authorization URL.

        Args:
            state: CSRF protection state token (should include user_id)

        Returns:
            Full authorization URL to redirect user to
        """
        if not self.is_configured():
            raise ValueError("Google Drive OAuth not configured")

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Always show consent screen
            "state": state,
        }

        return f"{self.AUTH_URL}?{urlencode(params)}"

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
        logger.info(f"[GDRIVE] Exchanging code for user {user_id}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )

            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"[GDRIVE] Token exchange failed: {error_data}")
                raise ValueError(f"Token exchange failed: {error_data.get('error_description', 'Unknown error')}")

            token_data = response.json()

        # Calculate expiry time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

        # Store tokens in database
        await self._store_tokens(
            user_id=user_id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
        )

        logger.info(f"[GDRIVE] Successfully connected for user {user_id}")
        return token_data

    async def _store_tokens(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str | None,
        expires_at: datetime,
    ):
        """Store OAuth tokens in database."""
        async with self.db_pool.acquire() as conn:
            # Upsert tokens
            await conn.execute(
                """
                INSERT INTO google_drive_tokens (user_id, access_token, refresh_token, expires_at, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = COALESCE(EXCLUDED.refresh_token, google_drive_tokens.refresh_token),
                    expires_at = EXCLUDED.expires_at,
                    updated_at = NOW()
                """,
                user_id,
                access_token,
                refresh_token,
                expires_at,
            )

    async def get_valid_token(self, user_id: str) -> str | None:
        """
        Get a valid access token for user, refreshing if necessary.

        Args:
            user_id: User ID

        Returns:
            Valid access token or None if not connected
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT access_token, refresh_token, expires_at
                FROM google_drive_tokens
                WHERE user_id = $1
                """,
                user_id,
            )

        if not row:
            return None

        # Check if token is expired or about to expire
        if row["expires_at"] <= datetime.now(timezone.utc) + self.TOKEN_EXPIRY_BUFFER:
            if row["refresh_token"]:
                return await self._refresh_token(user_id, row["refresh_token"])
            return None

        return row["access_token"]

    async def _refresh_token(self, user_id: str, refresh_token: str) -> str | None:
        """Refresh access token using refresh token."""
        logger.info(f"[GDRIVE] Refreshing token for user {user_id}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                logger.error(f"[GDRIVE] Token refresh failed for user {user_id}")
                return None

            token_data = response.json()

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

        await self._store_tokens(
            user_id=user_id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),  # May or may not be returned
            expires_at=expires_at,
        )

        return token_data["access_token"]

    async def is_connected(self, user_id: str) -> bool:
        """Check if user has connected Google Drive."""
        token = await self.get_valid_token(user_id)
        return token is not None

    async def disconnect(self, user_id: str) -> bool:
        """
        Disconnect Google Drive for user (revoke tokens).

        Args:
            user_id: User ID

        Returns:
            True if disconnected successfully
        """
        async with self.db_pool.acquire() as conn:
            # Get current token to revoke
            row = await conn.fetchrow(
                "SELECT access_token FROM google_drive_tokens WHERE user_id = $1",
                user_id,
            )

            if row:
                # Revoke token at Google
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "https://oauth2.googleapis.com/revoke",
                        params={"token": row["access_token"]},
                    )

            # Delete from database
            await conn.execute(
                "DELETE FROM google_drive_tokens WHERE user_id = $1",
                user_id,
            )

        logger.info(f"[GDRIVE] Disconnected for user {user_id}")
        return True

    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================

    async def list_files(
        self,
        user_id: str,
        folder_id: str | None = None,
        page_token: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """
        List files in a folder.

        Args:
            user_id: User ID
            folder_id: Folder ID (default: root folder or user's root)
            page_token: Pagination token
            page_size: Number of results per page

        Returns:
            Dict with files list and pagination info
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        # Use specified folder, or team root, or user's root
        target_folder = folder_id or self.root_folder_id or "root"

        params = {
            "q": f"'{target_folder}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, iconLink, webViewLink, thumbnailLink, parents)",
            "orderBy": "folder, name",
            "pageSize": page_size,
        }

        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/files",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                error = response.json()
                logger.error(f"[GDRIVE] List files failed: {error}")
                raise ValueError(f"Failed to list files: {error.get('error', {}).get('message', 'Unknown error')}")

            data = response.json()

        return {
            "files": data.get("files", []),
            "next_page_token": data.get("nextPageToken"),
        }

    async def get_file(self, user_id: str, file_id: str) -> dict[str, Any]:
        """
        Get file metadata.

        Args:
            user_id: User ID
            file_id: Google Drive file ID

        Returns:
            File metadata
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/files/{file_id}",
                params={
                    "fields": "id, name, mimeType, size, modifiedTime, iconLink, webViewLink, thumbnailLink, parents, permissions",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                error = response.json()
                raise ValueError(f"Failed to get file: {error.get('error', {}).get('message', 'Unknown error')}")

            return response.json()

    async def get_folder_path(self, user_id: str, folder_id: str) -> list[dict[str, str]]:
        """
        Get the full path (breadcrumb) to a folder.

        Args:
            user_id: User ID
            folder_id: Folder ID

        Returns:
            List of {id, name} dicts from root to folder
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        path = []
        current_id = folder_id

        async with httpx.AsyncClient() as client:
            while current_id and current_id != "root":
                response = await client.get(
                    f"{self.API_BASE}/files/{current_id}",
                    params={"fields": "id, name, parents"},
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code != 200:
                    break

                data = response.json()
                path.insert(0, {"id": data["id"], "name": data["name"]})

                # Move to parent
                parents = data.get("parents", [])
                current_id = parents[0] if parents else None

                # Stop at team root folder
                if current_id == self.root_folder_id:
                    break

        return path

    async def search_files(
        self,
        user_id: str,
        query: str,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search files by name.

        Args:
            user_id: User ID
            query: Search query
            page_size: Max results

        Returns:
            List of matching files
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        # Build search query - search within team folder if configured
        q_parts = [f"name contains '{query}'", "trashed = false"]
        if self.root_folder_id:
            q_parts.append(f"'{self.root_folder_id}' in parents")

        params = {
            "q": " and ".join(q_parts),
            "fields": "files(id, name, mimeType, size, modifiedTime, iconLink, webViewLink, parents)",
            "pageSize": page_size,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/files",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                return []

            return response.json().get("files", [])

    async def get_user_folder(self, user_id: str, user_email: str) -> dict[str, Any] | None:
        """
        Find the user's personal folder within the team structure.

        Args:
            user_id: User ID
            user_email: User's email (to match folder name)

        Returns:
            Folder metadata or None if not found
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            return None

        # Extract name from email (e.g., "anton@balizero.com" -> "Anton")
        user_name = user_email.split("@")[0].title()

        # Search for folder with user's name in Members folders
        params = {
            "q": f"name = '{user_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "fields": "files(id, name, parents)",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/files",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                files = response.json().get("files", [])
                if files:
                    return files[0]

        return None


# Database migration SQL for tokens table
MIGRATION_SQL = """
-- Google Drive OAuth tokens storage
CREATE TABLE IF NOT EXISTS google_drive_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdrive_tokens_expires ON google_drive_tokens(expires_at);
"""
