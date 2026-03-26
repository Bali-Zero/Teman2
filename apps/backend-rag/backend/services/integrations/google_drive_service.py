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
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import asyncpg
import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """
    Manages Google Drive OAuth 2.0 authentication and file operations.
    """

    # Required OAuth scopes - FULL ACCESS for CRUD operations
    SCOPES = [
        "https://www.googleapis.com/auth/drive",  # Full Drive access (read, write, delete)
    ]

    # System-wide OAuth user ID (token shared by all team members)
    SYSTEM_USER_ID = "SYSTEM"

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
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def _sanitize_drive_query_string(value: str) -> str:
        """
        Sanitize a string value for use inside a Google Drive API query.

        The Drive Files.list 'q' parameter uses a custom query language where
        string literals are delimited by single quotes.  An un-sanitized value
        can break out of that delimiter and inject arbitrary query clauses.

        Google's own documentation recommends escaping single quotes as \'
        and backslashes as \\ inside query string values.

        Args:
            value: Raw string (e.g., a user-supplied search term or folder name).

        Returns:
            Sanitized string safe to embed inside single-quoted Drive query.
        """
        # Order matters: escape backslash first, then single quote.
        return value.replace("\\", "\\\\").replace("'", "\\'")

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

        client = self._get_client()
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
            raise ValueError(
                f"Token exchange failed: {error_data.get('error_description', 'Unknown error')}"
            )

        token_data = response.json()

        # Calculate expiry time
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )

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
    ) -> None:
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

        client = self._get_client()
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

        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )

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
                client = self._get_client()
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

        client = self._get_client()
        response = await client.get(
            f"{self.API_BASE}/files",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            error = response.json()
            logger.error(f"[GDRIVE] List files failed: {error}")
            raise ValueError(
                f"Failed to list files: {error.get('error', {}).get('message', 'Unknown error')}"
            )

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

        client = self._get_client()
        response = await client.get(
            f"{self.API_BASE}/files/{file_id}",
            params={
                "fields": "id, name, mimeType, size, modifiedTime, iconLink, webViewLink, thumbnailLink, parents, permissions",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            error = response.json()
            raise ValueError(
                f"Failed to get file: {error.get('error', {}).get('message', 'Unknown error')}"
            )

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

        client = self._get_client()
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
        # Sanitize user-supplied query to prevent Drive query injection.
        safe_query = self._sanitize_drive_query_string(query)
        q_parts = [f"name contains '{safe_query}'", "trashed = false"]
        if self.root_folder_id:
            q_parts.append(f"'{self.root_folder_id}' in parents")

        params = {
            "q": " and ".join(q_parts),
            "fields": "files(id, name, mimeType, size, modifiedTime, iconLink, webViewLink, parents)",
            "pageSize": page_size,
        }

        client = self._get_client()
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
        # Sanitize before embedding in Drive query string.
        safe_user_name = self._sanitize_drive_query_string(user_name)

        # Search for folder with user's name in Members folders
        params = {
            "q": f"name = '{safe_user_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "fields": "files(id, name, parents)",
        }

        client = self._get_client()
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

    async def create_folder(
        self,
        user_id: str,
        name: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new folder in Google Drive.

        Args:
            user_id: User ID
            name: Folder name
            parent_id: Parent folder ID (optional, defaults to root)

        Returns:
            Folder metadata with id, name, webViewLink

        Raises:
            ValueError: If creation fails
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        # Build folder metadata
        folder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }

        # Add parent if specified
        if parent_id:
            folder_metadata["parents"] = [parent_id]

        client = self._get_client()
        response = await client.post(
            f"{self.API_BASE}/files",
            json=folder_metadata,
            params={"fields": "id, name, webViewLink, parents"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

        if response.status_code != 200:
            error = response.json()
            logger.error(f"[GDRIVE] Create folder failed: {error}")
            raise ValueError(
                f"Failed to create folder: {error.get('error', {}).get('message', 'Unknown error')}"
            )

        folder_data = response.json()
        logger.info(f"[GDRIVE] Created folder '{name}' with ID: {folder_data['id']}")
        return folder_data

    async def create_client_folder_async(
        self,
        client_id: int,
        client_name: str,
        client_type: str = "individual",
    ) -> dict[str, Any]:
        """
        Create standardized folder structure for a new client.

        Creates: {ID}_{ClientName}/ with subfolders
        - 00_Profile
        - 01_Immigration
        - 02_Company
        - 03_Tax
        - 04_Family
        - 99_Misc

        Args:
            client_id: Client database ID
            client_name: Client full name
            client_type: 'individual' or 'company'

        Returns:
            dict with folder_ids and urls
        """
        from backend.app.core.config import settings

        STANDARD_SUBFOLDERS = [
            "00_Profile",
            "01_Immigration",
            "02_Company",
            "02_Company/AKTA",
            "02_Company/NIB",
            "02_Company/NPWP",
            "02_Company/Profile Perseroan",
            "03_Tax",
            "03_Tax/SPT company",
            "03_Tax/SPT personal",
            "03_Tax/LKPM reports",
            "03_Tax/NPWP personal",
            "04_Family",
            "99_Misc",
        ]

        try:
            # Determine parent folder based on client type
            if client_type == "individual":
                parent_folder_id = getattr(settings, "gdrive_individuals_folder_id", None)
            elif client_type == "company":
                parent_folder_id = getattr(settings, "gdrive_companies_folder_id", None)
            else:
                parent_folder_id = getattr(settings, "google_drive_root_folder_id", None)

            # Fallback to root if no specific folder configured
            if not parent_folder_id:
                parent_folder_id = getattr(settings, "google_drive_root_folder_id", None)

            # Create root folder: "[ID]_[Name]"
            root_folder_name = f"{client_id}_{client_name}"
            root_folder = await self.create_folder(
                user_id=GoogleDriveService.SYSTEM_USER_ID,
                name=root_folder_name,
                parent_id=parent_folder_id,
            )

            root_folder_id = root_folder["id"]

            # Create subfolders (supports nested paths like "02_Company/AKTA")
            subfolders = {}
            folder_id_cache = {"": root_folder_id}
            for subfolder_path in STANDARD_SUBFOLDERS:
                try:
                    parts = subfolder_path.split("/")
                    if len(parts) == 1:
                        parent_id = root_folder_id
                        name = parts[0]
                    else:
                        parent_path = parts[0]
                        name = parts[1]
                        parent_id = folder_id_cache.get(parent_path, root_folder_id)

                    subfolder = await self.create_folder(
                        user_id=GoogleDriveService.SYSTEM_USER_ID,
                        name=name,
                        parent_id=parent_id,
                    )
                    subfolders[subfolder_path] = {
                        "id": subfolder["id"],
                        "url": subfolder.get("webViewLink", ""),
                    }
                    if len(parts) == 1:
                        folder_id_cache[name] = subfolder["id"]
                except Exception as e:
                    logger.error(f"[GDRIVE] Failed to create subfolder {subfolder_path}: {e}")
                    continue

            logger.info(
                f"[GDRIVE] Created client folder structure for {client_name}: {root_folder_id}"
            )

            return {
                "success": True,
                "root_folder_id": root_folder_id,
                "root_folder_url": root_folder.get("webViewLink", ""),
                "subfolders": subfolders,
            }

        except Exception as e:
            logger.error(f"[GDRIVE] Failed to create client folder for {client_name}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def list_folder_files(
        self,
        user_id: str,
        folder_id: str,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        List files in a specific folder with pagination and search.

        Args:
            user_id: User ID
            folder_id: Google Drive folder ID
            limit: Max number of files to return (default: 50, max: 200)
            offset: Offset for pagination
            search: Optional search query (searches in file name)

        Returns:
            {
                "files": [...],
                "total": 23,
                "limit": 50,
                "offset": 0
            }
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        # Build query
        query_parts = [f"'{folder_id}' in parents", "trashed = false"]
        if search:
            # Sanitize user-supplied search term to prevent Drive query injection.
            safe_search = self._sanitize_drive_query_string(search)
            query_parts.append(f"name contains '{safe_search}'")
        query = " and ".join(query_parts)

        # Calculate page token from offset (Drive API uses page tokens, not offset)
        # For simplicity, we'll fetch all and paginate in memory for now
        # TODO: Implement proper page token handling if needed

        params = {
            "q": query,
            "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, createdTime, webViewLink, thumbnailLink)",
            "orderBy": "folder, name",
            "pageSize": min(limit + offset, 200),  # Fetch enough to cover offset
        }

        client = self._get_client()
        response = await client.get(
            f"{self.API_BASE}/files",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            error = response.json()
            logger.error(f"[GDRIVE] List folder files failed: {error}")
            raise ValueError(
                f"Failed to list files: {error.get('error', {}).get('message', 'Unknown error')}"
            )

        data = response.json()
        files = data.get("files", [])

        # Apply offset and limit in memory
        paginated_files = files[offset : offset + limit]

        # Transform files to include proxy URLs
        transformed_files = []
        for file_info in paginated_files:
            file_id = file_info.get("id")
            transformed_files.append(
                {
                    "id": file_id,
                    "name": file_info.get("name"),
                    "mime_type": file_info.get("mimeType"),
                    "size_bytes": int(file_info.get("size", 0)) if file_info.get("size") else None,
                    "created_time": file_info.get("createdTime"),
                    "modified_time": file_info.get("modifiedTime"),
                    "thumbnail_url": f"/api/documents/thumbnail/{file_id}"
                    if file_info.get("thumbnailLink")
                    else None,
                    "download_url": f"/api/documents/proxy/{file_id}",
                    "is_folder": file_info.get("mimeType") == "application/vnd.google-apps.folder",
                }
            )

        return {
            "files": transformed_files,
            "total": len(files),  # Total available (may be more than returned)
            "limit": limit,
            "offset": offset,
            "has_more": len(files) > offset + limit,
        }

    async def get_folder_structure(
        self,
        user_id: str,
        root_folder_id: str,
    ) -> dict[str, Any]:
        """
        Get complete folder structure with file counts and statistics.

        Args:
            user_id: User ID
            root_folder_id: Root folder ID

        Returns:
            {
                "root_folder_id": "...",
                "folders": [
                    {
                        "name": "00_Profile",
                        "id": "...",
                        "file_count": 12,
                        "total_size_bytes": 5242880,
                        "last_modified": "2026-01-20T10:30:00Z"
                    },
                    ...
                ],
                "total_files": 47,
                "total_size_bytes": 131072000
            }
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        # List all subfolders in root
        params = {
            "q": f"'{root_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "fields": "files(id, name)",
            "orderBy": "name",
        }

        client = self._get_client()
        response = await client.get(
            f"{self.API_BASE}/files",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            error = response.json()
            logger.error(f"[GDRIVE] Get folder structure failed: {error}")
            raise ValueError(
                f"Failed to get folder structure: {error.get('error', {}).get('message', 'Unknown error')}"
            )

        data = response.json()
        subfolders = data.get("files", [])

        # For each subfolder, get file count and size
        folders_info = []
        total_files = 0
        total_size_bytes = 0

        for subfolder in subfolders:
            folder_id = subfolder["id"]
            folder_name = subfolder["name"]

            # List files in this subfolder (non-recursive, direct children only)
            files_params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "files(id, size)",
                "pageSize": 1000,  # Get all files for accurate count
            }

            files_response = await client.get(
                f"{self.API_BASE}/files",
                params=files_params,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if files_response.status_code == 200:
                files_data = files_response.json()
                files = files_data.get("files", [])
                file_count = len(
                    [f for f in files if f.get("mimeType") != "application/vnd.google-apps.folder"]
                )

                # Calculate total size
                folder_size = sum(
                    int(f.get("size", 0))
                    for f in files
                    if f.get("size") and f.get("mimeType") != "application/vnd.google-apps.folder"
                )

                # Get last modified time (most recent file)
                if files:
                    modified_times = [f.get("modifiedTime") for f in files if f.get("modifiedTime")]
                    last_modified = max(modified_times) if modified_times else None
                else:
                    last_modified = None

                folders_info.append(
                    {
                        "name": folder_name,
                        "id": folder_id,
                        "file_count": file_count,
                        "total_size_bytes": folder_size,
                        "last_modified": last_modified,
                    }
                )

                total_files += file_count
                total_size_bytes += folder_size

        return {
            "root_folder_id": root_folder_id,
            "folders": folders_info,
            "total_files": total_files,
            "total_size_bytes": total_size_bytes,
        }

    async def upload_file_to_folder(
        self,
        user_id: str,
        folder_id: str,
        file_content: bytes,
        file_name: str,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file directly to a Google Drive folder.

        Args:
            user_id: User ID
            folder_id: Google Drive folder ID
            file_content: File content as bytes
            file_name: Name of the file
            mime_type: MIME type (auto-detected if not provided)

        Returns:
            {
                "id": "1JKL...XYZ",
                "name": "passport_marco.pdf",
                "size_bytes": 2359296,
                "download_url": "/api/documents/proxy/1JKL...XYZ"
            }
        """
        access_token = await self.get_valid_token(user_id)
        if not access_token:
            raise ValueError("User not connected to Google Drive")

        # Auto-detect MIME type if not provided
        if not mime_type:
            import mimetypes

            mime_type, _ = mimetypes.guess_type(file_name)
            mime_type = mime_type or "application/octet-stream"

        # Create file metadata
        metadata = {
            "name": file_name,
            "parents": [folder_id],
        }

        # Upload file using multipart upload
        client = self._get_client()
        # First, create metadata
        metadata_response = await client.post(
            f"{self.API_BASE}/files",
            json=metadata,
            params={"fields": "id, name, size"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

        if metadata_response.status_code != 200:
            error = metadata_response.json()
            logger.error(f"[GDRIVE] Upload file metadata failed: {error}")
            raise ValueError(
                f"Failed to upload file: {error.get('error', {}).get('message', 'Unknown error')}"
            )

        file_id = metadata_response.json().get("id")
        if not file_id:
            raise ValueError("Failed to get file ID from upload")

        # Then upload file content
        upload_response = await client.patch(
            f"{self.API_BASE}/files/{file_id}",
            content=file_content,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": mime_type,
            },
        )

        if upload_response.status_code not in (200, 204):
            error = (
                upload_response.json()
                if upload_response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            logger.error(f"[GDRIVE] Upload file content failed: {error}")
            raise ValueError(
                f"Failed to upload file content: {error.get('error', {}).get('message', 'Unknown error')}"
            )

        # Get final file info
        file_info = metadata_response.json()
        size_bytes = int(file_info.get("size", 0)) if file_info.get("size") else len(file_content)

        logger.info(
            f"[GDRIVE] Uploaded file '{file_name}' ({size_bytes} bytes) to folder {folder_id}"
        )

        return {
            "id": file_id,
            "name": file_name,
            "size_bytes": size_bytes,
            "download_url": f"/api/documents/proxy/{file_id}",
        }

    async def get_folder_stats(
        self,
        user_id: str,
        root_folder_id: str,
    ) -> dict[str, Any]:
        """
        Get aggregated statistics for a folder structure.

        Args:
            user_id: User ID
            root_folder_id: Root folder ID

        Returns:
            {
                "total_files": 47,
                "total_size_bytes": 131072000,
                "total_size_mb": 125.0,
                "last_synced": "2026-01-20T12:30:00Z",
                "by_category": {
                    "00_Profile": {"files": 2, "size_mb": 5.2},
                    "01_Immigration": {"files": 23, "size_mb": 45.0},
                    ...
                }
            }
        """
        structure = await self.get_folder_structure(user_id, root_folder_id)

        # Group by category (folder name prefix)
        by_category = {}
        for folder in structure["folders"]:
            folder_name = folder["name"]
            by_category[folder_name] = {
                "files": folder["file_count"],
                "size_bytes": folder["total_size_bytes"],
                "size_mb": round(folder["total_size_bytes"] / 1024 / 1024, 2),
            }

        return {
            "total_files": structure["total_files"],
            "total_size_bytes": structure["total_size_bytes"],
            "total_size_mb": round(structure["total_size_bytes"] / 1024 / 1024, 2),
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "by_category": by_category,
        }


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
