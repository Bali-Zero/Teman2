"""
Team Drive Service - Hybrid OAuth + Service Account Access

Provides Google Drive access for all team members.

AUTHENTICATION PRIORITY:
1. OAuth SYSTEM token (if available) → antonellosiano@gmail.com 30TB quota
2. Domain-Wide Delegation (if configured) → Workspace org quota
3. Service Account direct → 15GB limit

Team members authenticate via their Zoho credentials in Zantara, then access
Drive files through this service using the SYSTEM OAuth token.

OBSERVABILITY (Jan 2026):
- Prometheus metrics for all operations (duration, file size, errors)
- Structured audit logging for compliance (who, when, what, result)
- OAuth token refresh tracking
"""

import base64
import io
import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

import httpx
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

logger = logging.getLogger(__name__)

# =========================================================================
# Metrics & Audit Logging (Jan 2026)
# =========================================================================

try:
    from app.metrics import metrics_collector

    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    metrics_collector = None


class DriveAuditLogger:
    """
    Structured audit logging for Google Drive operations.

    Logs every operation with:
    - who: user_email (team member or SYSTEM)
    - when: ISO timestamp
    - what: operation, file_id, file_name, parent_id
    - result: success/error, duration_ms, file_size_bytes
    """

    def __init__(self):
        self.audit_logger = logging.getLogger("drive_audit")
        # Ensure audit logs go to a dedicated handler if configured
        if not self.audit_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s - DRIVE_AUDIT - %(message)s"))
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(logging.INFO)

    def log(
        self,
        operation: str,
        user_email: str,
        status: str,
        file_id: str | None = None,
        file_name: str | None = None,
        parent_id: str | None = None,
        duration_ms: float = 0,
        file_size_bytes: int = 0,
        error_message: str | None = None,
        extra: dict | None = None,
    ):
        """Log a structured audit entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "user_email": user_email,
            "status": status,
            "file_id": file_id,
            "file_name": file_name,
            "parent_id": parent_id,
            "duration_ms": round(duration_ms, 2),
            "file_size_bytes": file_size_bytes,
        }
        if error_message:
            entry["error"] = error_message
        if extra:
            entry.update(extra)

        # Log as JSON for easy parsing
        self.audit_logger.info(json.dumps(entry))

        # Also record metrics if enabled
        if METRICS_ENABLED and metrics_collector:
            try:
                metrics_collector.record_drive_operation(
                    operation=operation,
                    user_email=user_email,
                    status=status,
                    duration_seconds=duration_ms / 1000,
                    file_size_bytes=file_size_bytes,
                )
                if status == "error" and error_message:
                    error_type = self._classify_error(error_message)
                    metrics_collector.record_drive_error(error_type, operation)
            except Exception as e:
                logger.warning(f"[TEAM_DRIVE] Metrics recording failed: {e}")

    def _classify_error(self, error_message: str) -> str:
        """Classify error message into error types for metrics."""
        error_lower = error_message.lower()
        if "quota" in error_lower:
            return "quota_exceeded"
        elif "permission" in error_lower or "forbidden" in error_lower:
            return "permission_denied"
        elif "not found" in error_lower or "404" in error_lower:
            return "not_found"
        elif "rate" in error_lower or "limit" in error_lower:
            return "rate_limited"
        elif "token" in error_lower or "auth" in error_lower or "credential" in error_lower:
            return "auth_error"
        elif "timeout" in error_lower:
            return "timeout"
        elif "network" in error_lower or "connection" in error_lower:
            return "network_error"
        return "unknown"


# Global audit logger instance
audit_logger = DriveAuditLogger()


def drive_operation(operation_name: str):
    """
    Decorator for Drive operations that handles metrics and audit logging.

    Usage:
        @drive_operation("list_files")
        async def list_files(self, ...):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            user_email = self._connected_as or "unknown"

            # Extract file info from args/kwargs if available
            file_id = kwargs.get("file_id") or (args[0] if args else None)
            file_name = kwargs.get("filename") or kwargs.get("name")
            parent_id = kwargs.get("parent_folder_id") or kwargs.get("folder_id")

            try:
                result = await func(self, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # Extract file info from result if available
                if isinstance(result, dict):
                    file_id = file_id or result.get("id")
                    file_name = file_name or result.get("name")
                    file_size = result.get("size", 0)
                elif isinstance(result, tuple) and len(result) >= 2:
                    # download_file returns (bytes, filename, mimetype)
                    file_size = len(result[0]) if result[0] else 0
                    file_name = file_name or result[1]
                else:
                    file_size = 0

                audit_logger.log(
                    operation=operation_name,
                    user_email=user_email,
                    status="success",
                    file_id=str(file_id) if file_id else None,
                    file_name=file_name,
                    parent_id=str(parent_id) if parent_id else None,
                    duration_ms=duration_ms,
                    file_size_bytes=file_size,
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                audit_logger.log(
                    operation=operation_name,
                    user_email=user_email,
                    status="error",
                    file_id=str(file_id) if file_id else None,
                    file_name=file_name,
                    parent_id=str(parent_id) if parent_id else None,
                    duration_ms=duration_ms,
                    error_message=str(e),
                )

                raise

        return wrapper

    return decorator


# Path to service account credentials (local development)
CREDENTIALS_PATH = Path(__file__).parent.parent.parent.parent / "google_credentials.json"

# Environment variable for production (base64 encoded JSON)
CREDENTIALS_ENV_VAR = "GOOGLE_SERVICE_ACCOUNT_JSON"


class TeamDriveService:
    """
    Google Drive access for team members using hybrid OAuth + Service Account.

    AUTHENTICATION PRIORITY:
    1. OAuth SYSTEM token → antonellosiano@gmail.com's 30TB quota
    2. Domain-Wide Delegation → Workspace org quota
    3. Service Account direct → 15GB limit

    The Service Account (nuzantara-bot@nuzantara.iam.gserviceaccount.com) is
    used as fallback when OAuth is not available.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/drive",  # Full access for CRUD operations
    ]

    # System-wide OAuth user ID (shared by all team members)
    OAUTH_SYSTEM_USER_ID = "SYSTEM"

    # Optional: Transfer ownership of new files to this account (DEPRECATED - use OAuth instead)
    FILE_OWNER_EMAIL = os.environ.get("GOOGLE_DRIVE_FILE_OWNER", "")

    # MIME type mappings for Google Docs export
    EXPORT_MIMETYPES = {
        "application/vnd.google-apps.document": "application/pdf",
        "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.presentation": "application/pdf",
    }

    def __init__(self, db_pool=None, root_folder_id: str | None = None):
        """
        Initialize the Team Drive service.

        Args:
            db_pool: Optional asyncpg pool for OAuth token lookup.
                     If provided, will try OAuth SYSTEM token first.
            root_folder_id: Optional root folder ID to use as default parent.
                            If set, list_files(folder_id=None) will list this folder.
        """
        self._service = None
        self._credentials = None
        self._db_pool = db_pool
        self._root_folder_id = root_folder_id
        self._is_oauth_mode = False  # Track which auth mode is active
        self._connected_as = None  # Email of connected OAuth account

    def _get_credentials_path(self) -> str | None:
        """
        Get path to credentials file.

        Priority:
        1. Local file (google_credentials.json)
        2. Environment variable (base64 encoded JSON)
        """
        # Check local file first
        if CREDENTIALS_PATH.exists():
            return str(CREDENTIALS_PATH)

        # Check environment variable (base64 encoded)
        env_creds = os.environ.get(CREDENTIALS_ENV_VAR)
        if env_creds:
            try:
                # Decode base64 and write to temp file
                creds_json = base64.b64decode(env_creds).decode("utf-8")

                # Validate it's valid JSON
                json.loads(creds_json)

                # Write to temp file
                temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
                temp_file.write(creds_json)
                temp_file.close()

                logger.info("[TEAM_DRIVE] Using credentials from environment variable")
                return temp_file.name

            except Exception as e:
                logger.error(f"[TEAM_DRIVE] Failed to decode credentials from env: {e}")
                return None

        return None

    async def _get_oauth_token(self) -> dict | None:
        """
        Get OAuth SYSTEM token data from database if available.

        Returns:
            Dict with token data (access_token, refresh_token, client_id, client_secret)
            or None if not available
        """
        if not self._db_pool:
            return None

        try:
            from datetime import datetime, timedelta, timezone

            from app.core.config import settings

            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT access_token, refresh_token, expires_at
                    FROM google_drive_tokens
                    WHERE user_id = $1
                    """,
                    self.OAUTH_SYSTEM_USER_ID,
                )

            if not row:
                return None

            refresh_token = row["refresh_token"]

            # Check if token is expired
            token_expiry_buffer = timedelta(minutes=5)
            if row["expires_at"] <= datetime.now(timezone.utc) + token_expiry_buffer:
                # Token expired, try refresh
                if refresh_token:
                    new_access_token = await self._refresh_oauth_token(refresh_token)
                    if new_access_token:
                        return {
                            "access_token": new_access_token,
                            "refresh_token": refresh_token,
                            "client_id": settings.google_drive_client_id,
                            "client_secret": settings.google_drive_client_secret,
                        }
                return None

            return {
                "access_token": row["access_token"],
                "refresh_token": refresh_token,
                "client_id": settings.google_drive_client_id,
                "client_secret": settings.google_drive_client_secret,
            }

        except Exception as e:
            logger.warning(f"[TEAM_DRIVE] OAuth token lookup failed: {e}")
            return None

    async def _refresh_oauth_token(self, refresh_token: str) -> str | None:
        """Refresh OAuth token using refresh token."""
        from datetime import datetime, timedelta, timezone

        from app.core.config import settings

        client_id = settings.google_drive_client_id
        client_secret = settings.google_drive_client_secret

        if not client_id or not client_secret:
            logger.warning("[TEAM_DRIVE] OAuth credentials not configured for token refresh")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )

                if response.status_code != 200:
                    logger.error(f"[TEAM_DRIVE] OAuth token refresh failed: {response.text}")
                    return None

                token_data = response.json()

            # Store refreshed token
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token_data.get("expires_in", 3600)
            )

            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE google_drive_tokens
                    SET access_token = $1,
                        refresh_token = COALESCE($2, refresh_token),
                        expires_at = $3,
                        updated_at = NOW()
                    WHERE user_id = $4
                    """,
                    token_data["access_token"],
                    token_data.get("refresh_token"),
                    expires_at,
                    self.OAUTH_SYSTEM_USER_ID,
                )

            logger.info("[TEAM_DRIVE] ✅ OAuth token refreshed successfully")

            # Record successful refresh in metrics
            if METRICS_ENABLED and metrics_collector:
                metrics_collector.record_drive_oauth_refresh("success")
                metrics_collector.set_drive_oauth_expiry(token_data.get("expires_in", 3600))

            return token_data["access_token"]

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] OAuth token refresh error: {e}")
            # Record failed refresh in metrics
            if METRICS_ENABLED and metrics_collector:
                metrics_collector.record_drive_oauth_refresh("error")
            return None

    async def _get_service_async(self):
        """
        Get or create the Drive API service (async version with OAuth support).

        PRIORITY:
        1. OAuth SYSTEM token (30TB quota)
        2. Domain-Wide Delegation (Workspace quota)
        3. Service Account direct (15GB limit)
        """
        if self._service is not None:
            return self._service

        # Try OAuth SYSTEM token first (30TB quota)
        oauth_data = await self._get_oauth_token()
        if oauth_data:
            try:
                # Create credentials with ALL required fields for auto-refresh
                self._credentials = OAuthCredentials(
                    token=oauth_data["access_token"],
                    refresh_token=oauth_data.get("refresh_token"),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=oauth_data.get("client_id"),
                    client_secret=oauth_data.get("client_secret"),
                    scopes=self.SCOPES,
                )
                self._service = build("drive", "v3", credentials=self._credentials)

                # Get connected account info
                about = self._service.about().get(fields="user(emailAddress)").execute()
                self._connected_as = about.get("user", {}).get("emailAddress", "unknown")
                self._is_oauth_mode = True

                logger.info(
                    f"[TEAM_DRIVE] ✅ OAuth mode active as {self._connected_as} (30TB quota)"
                )
                return self._service

            except Exception as e:
                logger.warning(f"[TEAM_DRIVE] ⚠️ OAuth token invalid, falling back: {e}")
                self._service = None

        # Fallback to Service Account
        return self._get_service()

    def _get_service(self):
        """Get or create the Drive API service (sync, Service Account only)."""
        if self._service is None:
            creds_path = self._get_credentials_path()

            if not creds_path:
                raise FileNotFoundError(
                    "Google credentials not found. Either add google_credentials.json "
                    "to the backend-rag directory, or set GOOGLE_SERVICE_ACCOUNT_JSON "
                    "environment variable with base64-encoded credentials."
                )

            # QUOTA STRATEGY (Service Account fallback):
            # - Domain-Wide Delegation allows impersonating a Workspace user
            # - Files created use the impersonated user's organizational quota
            # - Direct Service Account has 15GB limit

            impersonate_user = os.environ.get("GOOGLE_DRIVE_IMPERSONATE_USER", "zero@balizero.com")

            # Try Domain-Wide Delegation first (for Workspace users)
            try:
                self._credentials = service_account.Credentials.from_service_account_file(
                    creds_path, scopes=self.SCOPES, subject=impersonate_user
                )
                # Test the credentials work by building service
                self._service = build("drive", "v3", credentials=self._credentials)
                # Verify by making a simple API call
                self._service.about().get(fields="user").execute()
                self._connected_as = impersonate_user
                logger.info(f"[TEAM_DRIVE] ✅ Domain-Wide Delegation active as {impersonate_user}")

            except Exception as e:
                # Fallback to direct Service Account (no impersonation)
                logger.warning(
                    f"[TEAM_DRIVE] ⚠️ Domain-Wide Delegation failed for {impersonate_user}: {e}"
                )
                logger.info(
                    "[TEAM_DRIVE] Falling back to Service Account direct (15GB quota limit)"
                )

                self._credentials = service_account.Credentials.from_service_account_file(
                    creds_path, scopes=self.SCOPES
                )
                self._service = build("drive", "v3", credentials=self._credentials)
                self._connected_as = "nuzantara-bot@nuzantara.iam.gserviceaccount.com"
                logger.info(
                    "[TEAM_DRIVE] ✅ Service initialized with Service Account (no impersonation)"
                )

        return self._service

    def get_connection_info(self) -> dict[str, Any]:
        """Get information about current connection mode."""
        return {
            "mode": "oauth" if self._is_oauth_mode else "service_account",
            "connected_as": self._connected_as,
            "is_oauth": self._is_oauth_mode,
        }

    def is_configured(self) -> bool:
        """Check if the service account credentials are available."""
        return CREDENTIALS_PATH.exists() or os.environ.get(CREDENTIALS_ENV_VAR) is not None

    @drive_operation("list_files")
    async def list_files(
        self,
        folder_id: str | None = None,
        page_size: int = 50,
        page_token: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        """
        List files in a folder or search across all shared files.

        Args:
            folder_id: Optional folder ID to list contents of. If None and
                      root_folder_id is configured, uses root_folder_id.
            page_size: Number of results per page (max 100)
            page_token: Token for pagination
            query: Optional search query

        Returns:
            Dict with 'files' list and optional 'next_page_token'
        """
        service = await self._get_service_async()

        # Use root_folder_id as default if no folder_id specified
        effective_folder_id = folder_id or self._root_folder_id

        # Build query
        q_parts = ["trashed = false"]
        if effective_folder_id:
            q_parts.append(f"'{effective_folder_id}' in parents")
        if query:
            q_parts.append(f"name contains '{query}'")

        params = {
            "q": " and ".join(q_parts),
            "pageSize": min(page_size, 100),
            "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, iconLink, webViewLink, thumbnailLink, parents)",
            "orderBy": "folder, name",
        }

        if page_token:
            params["pageToken"] = page_token

        try:
            results = service.files().list(**params).execute()

            files = []
            for f in results.get("files", []):
                files.append(
                    {
                        "id": f["id"],
                        "name": f["name"],
                        "type": "folder"
                        if f["mimeType"] == "application/vnd.google-apps.folder"
                        else "file",
                        "mimeType": f["mimeType"],
                        "size": int(f.get("size", 0)),
                        "modifiedTime": f.get("modifiedTime"),
                        "webViewLink": f.get("webViewLink"),
                        "thumbnailLink": f.get("thumbnailLink"),
                    }
                )

            return {
                "files": files,
                "next_page_token": results.get("nextPageToken"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error listing files: {e}")
            raise

    @drive_operation("get_metadata")
    async def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        """
        Get metadata for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dict
        """
        service = await self._get_service_async()

        try:
            file = (
                service.files()
                .get(
                    fileId=file_id,
                    fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink, parents, description",
                )
                .execute()
            )

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder"
                if file["mimeType"] == "application/vnd.google-apps.folder"
                else "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
                "description": file.get("description"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error getting file {file_id}: {e}")
            raise

    @drive_operation("download_file")
    async def download_file(self, file_id: str) -> tuple[bytes, str, str]:
        """
        Download a file's content.

        For Google Docs/Sheets/Slides, exports to PDF/XLSX.
        For regular files, downloads the content directly.

        Args:
            file_id: Google Drive file ID

        Returns:
            Tuple of (content_bytes, filename, mime_type)
        """
        service = await self._get_service_async()

        try:
            # Get file metadata first
            file = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()

            mime_type = file["mimeType"]
            filename = file["name"]

            # Check if it's a Google Docs type that needs export
            if mime_type in self.EXPORT_MIMETYPES:
                export_mime = self.EXPORT_MIMETYPES[mime_type]
                request = service.files().export_media(fileId=file_id, mimeType=export_mime)

                # Adjust filename extension
                if export_mime == "application/pdf":
                    filename = f"{filename}.pdf"
                elif "spreadsheet" in export_mime:
                    filename = f"{filename}.xlsx"

                mime_type = export_mime
            else:
                request = service.files().get_media(fileId=file_id)

            # Download content
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            content = buffer.getvalue()
            logger.info(f"[TEAM_DRIVE] Downloaded {filename} ({len(content)} bytes)")

            return content, filename, mime_type

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error downloading file {file_id}: {e}")
            raise

    @drive_operation("get_folder_path")
    async def get_folder_path(self, folder_id: str) -> list[dict[str, str]]:
        """
        Get the breadcrumb path to a folder.

        Args:
            folder_id: Folder ID

        Returns:
            List of {id, name} dicts from root to folder
        """
        service = await self._get_service_async()
        path = []
        current_id = folder_id

        try:
            while current_id:
                file = service.files().get(fileId=current_id, fields="id, name, parents").execute()

                path.insert(0, {"id": file["id"], "name": file["name"]})

                parents = file.get("parents", [])
                current_id = parents[0] if parents else None

                # Safety limit
                if len(path) > 20:
                    break

            return path

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error getting folder path: {e}")
            return path

    @drive_operation("search_files")
    async def search_files(
        self,
        query: str,
        file_type: str | None = None,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for files by name or content.

        Args:
            query: Search query
            file_type: Optional filter ('folder', 'document', 'spreadsheet', 'pdf', etc.)
            page_size: Max results

        Returns:
            List of matching files
        """
        service = await self._get_service_async()

        q_parts = [f"name contains '{query}'", "trashed = false"]

        if file_type:
            type_map = {
                "folder": "application/vnd.google-apps.folder",
                "document": "application/vnd.google-apps.document",
                "spreadsheet": "application/vnd.google-apps.spreadsheet",
                "presentation": "application/vnd.google-apps.presentation",
                "pdf": "application/pdf",
            }
            if file_type in type_map:
                q_parts.append(f"mimeType = '{type_map[file_type]}'")

        try:
            results = (
                service.files()
                .list(
                    q=" and ".join(q_parts),
                    pageSize=page_size,
                    fields="files(id, name, mimeType, size, modifiedTime, webViewLink, parents)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )

            return [
                {
                    "id": f["id"],
                    "name": f["name"],
                    "type": "folder"
                    if f["mimeType"] == "application/vnd.google-apps.folder"
                    else "file",
                    "mimeType": f["mimeType"],
                    "size": int(f.get("size", 0)),
                    "modifiedTime": f.get("modifiedTime"),
                    "webViewLink": f.get("webViewLink"),
                }
                for f in results.get("files", [])
            ]

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error searching files: {e}")
            return []

    # =========================================================================
    # Ownership Transfer (for quota management)
    # =========================================================================

    async def _transfer_ownership_if_configured(self, file_id: str, file_name: str) -> bool:
        """
        Transfer file ownership to FILE_OWNER_EMAIL if configured.

        This is useful when using a Service Account but wanting files
        to count against a user's quota (e.g., antonellosiano@gmail.com with 30TB).

        Returns True if ownership was transferred, False otherwise.
        """
        if not self.FILE_OWNER_EMAIL:
            return False

        service = await self._get_service_async()

        try:
            # Create a permission with ownership transfer
            # Note: transferOwnership only works if:
            # 1. The new owner is in the same domain (for Workspace)
            # 2. OR the file allows ownership transfer to anyone (personal accounts)
            # IMPORTANT: Google REQUIRES sendNotificationEmail=True for ownership transfers
            permission = (
                service.permissions()
                .create(
                    fileId=file_id,
                    body={
                        "type": "user",
                        "role": "owner",
                        "emailAddress": self.FILE_OWNER_EMAIL,
                    },
                    transferOwnership=True,
                    sendNotificationEmail=True,  # Required by Google for ownership transfers
                    fields="id, emailAddress, role",
                )
                .execute()
            )

            logger.info(
                f"[TEAM_DRIVE] ✅ Ownership of '{file_name}' transferred to {self.FILE_OWNER_EMAIL} "
                f"(quota now charged to their account)"
            )
            return True

        except Exception as e:
            # Ownership transfer can fail for various reasons:
            # - Different domains (Workspace restriction)
            # - Pending ownership request (Gmail may require acceptance)
            # - File type restrictions
            logger.warning(
                f"[TEAM_DRIVE] ⚠️ Ownership transfer failed for '{file_name}' to {self.FILE_OWNER_EMAIL}: {e}. "
                f"File created but quota charged to creator's account."
            )
            return False

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    @drive_operation("upload_file")
    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        parent_folder_id: str,
    ) -> dict[str, Any]:
        """
        Upload a file to Google Drive.

        Args:
            file_content: File content as bytes
            filename: Name for the file
            mime_type: MIME type of the file
            parent_folder_id: ID of the parent folder

        Returns:
            Dict with file metadata
        """
        service = await self._get_service_async()

        file_metadata = {
            "name": filename,
            "parents": [parent_folder_id],
        }

        try:
            media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=mime_type, resumable=True)

            file = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink",
                )
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Uploaded file: {filename} ({file['id']})")

            # Transfer ownership if configured (for quota management)
            await self._transfer_ownership_if_configured(file["id"], filename)

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error uploading file {filename}: {e}")
            raise

    @drive_operation("create_folder")
    async def create_folder(
        self,
        name: str,
        parent_folder_id: str,
    ) -> dict[str, Any]:
        """
        Create a new folder in Google Drive.

        Args:
            name: Folder name
            parent_folder_id: ID of the parent folder

        Returns:
            Dict with folder metadata
        """
        service = await self._get_service_async()

        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }

        try:
            folder = (
                service.files()
                .create(body=file_metadata, fields="id, name, mimeType, modifiedTime, webViewLink")
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Created folder: {name} ({folder['id']})")

            # Transfer ownership if configured (for quota management)
            await self._transfer_ownership_if_configured(folder["id"], name)

            return {
                "id": folder["id"],
                "name": folder["name"],
                "type": "folder",
                "mimeType": folder["mimeType"],
                "size": 0,
                "modifiedTime": folder.get("modifiedTime"),
                "webViewLink": folder.get("webViewLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error creating folder {name}: {e}")
            raise

    @drive_operation("create_google_doc")
    async def create_google_doc(
        self,
        name: str,
        parent_folder_id: str,
        doc_type: str = "document",
    ) -> dict[str, Any]:
        """
        Create a new Google Doc, Sheet, or Slides.

        Args:
            name: Document name
            parent_folder_id: ID of the parent folder
            doc_type: One of 'document', 'spreadsheet', 'presentation'

        Returns:
            Dict with document metadata
        """
        service = await self._get_service_async()

        mime_types = {
            "document": "application/vnd.google-apps.document",
            "spreadsheet": "application/vnd.google-apps.spreadsheet",
            "presentation": "application/vnd.google-apps.presentation",
        }

        if doc_type not in mime_types:
            raise ValueError(
                f"Invalid doc_type: {doc_type}. Must be one of: {list(mime_types.keys())}"
            )

        file_metadata = {
            "name": name,
            "mimeType": mime_types[doc_type],
            "parents": [parent_folder_id],
        }

        try:
            doc = (
                service.files()
                .create(body=file_metadata, fields="id, name, mimeType, modifiedTime, webViewLink")
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Created {doc_type}: {name} ({doc['id']})")

            # Transfer ownership if configured (for quota management)
            await self._transfer_ownership_if_configured(doc["id"], name)

            return {
                "id": doc["id"],
                "name": doc["name"],
                "type": "file",
                "mimeType": doc["mimeType"],
                "size": 0,
                "modifiedTime": doc.get("modifiedTime"),
                "webViewLink": doc.get("webViewLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error creating {doc_type} {name}: {e}")
            raise

    @drive_operation("rename_file")
    async def rename_file(
        self,
        file_id: str,
        new_name: str,
    ) -> dict[str, Any]:
        """
        Rename a file or folder.

        Args:
            file_id: ID of the file/folder
            new_name: New name

        Returns:
            Dict with updated metadata
        """
        service = await self._get_service_async()

        try:
            file = (
                service.files()
                .update(
                    fileId=file_id,
                    body={"name": new_name},
                    fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink",
                )
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Renamed file {file_id} to: {new_name}")

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder"
                if file["mimeType"] == "application/vnd.google-apps.folder"
                else "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error renaming file {file_id}: {e}")
            raise

    @drive_operation("delete_file")
    async def delete_file(
        self,
        file_id: str,
        permanent: bool = False,
    ) -> bool:
        """
        Delete a file or folder (move to trash or permanently delete).

        Args:
            file_id: ID of the file/folder
            permanent: If True, permanently delete. If False, move to trash.

        Returns:
            True if successful
        """
        service = await self._get_service_async()

        try:
            if permanent:
                service.files().delete(fileId=file_id).execute()
                logger.info(f"[TEAM_DRIVE] Permanently deleted file: {file_id}")
            else:
                service.files().update(fileId=file_id, body={"trashed": True}).execute()
                logger.info(f"[TEAM_DRIVE] Moved to trash: {file_id}")

            return True

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error deleting file {file_id}: {e}")
            raise

    @drive_operation("move_file")
    async def move_file(
        self,
        file_id: str,
        new_parent_id: str,
        old_parent_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Move a file to a different folder.

        Args:
            file_id: ID of the file/folder to move
            new_parent_id: ID of the destination folder
            old_parent_id: ID of the current parent (optional, will be fetched if not provided)

        Returns:
            Dict with updated metadata
        """
        service = await self._get_service_async()

        try:
            # Get current parent if not provided
            if not old_parent_id:
                current = service.files().get(fileId=file_id, fields="parents").execute()
                old_parent_id = current.get("parents", [None])[0]

            # Move the file
            file = (
                service.files()
                .update(
                    fileId=file_id,
                    addParents=new_parent_id,
                    removeParents=old_parent_id,
                    fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink, parents",
                )
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Moved file {file_id} to folder {new_parent_id}")

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder"
                if file["mimeType"] == "application/vnd.google-apps.folder"
                else "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error moving file {file_id}: {e}")
            raise

    @drive_operation("copy_file")
    async def copy_file(
        self,
        file_id: str,
        new_name: str | None = None,
        parent_folder_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Copy a file.

        Args:
            file_id: ID of the file to copy
            new_name: Optional new name for the copy
            parent_folder_id: Optional destination folder (same as original if not provided)

        Returns:
            Dict with new file metadata
        """
        service = await self._get_service_async()

        try:
            body = {}
            if new_name:
                body["name"] = new_name
            if parent_folder_id:
                body["parents"] = [parent_folder_id]

            file = (
                service.files()
                .copy(
                    fileId=file_id,
                    body=body if body else None,
                    fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink",
                )
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Copied file {file_id} to: {file['id']}")

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder"
                if file["mimeType"] == "application/vnd.google-apps.folder"
                else "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error copying file {file_id}: {e}")
            raise

    # =========================================================================
    # Permission Management (Board only)
    # =========================================================================

    @drive_operation("list_permissions")
    async def list_permissions(self, file_id: str) -> list[dict[str, Any]]:
        """
        List all permissions for a file/folder.

        Args:
            file_id: ID of the file/folder

        Returns:
            List of permission dicts with id, email, role, type
        """
        service = await self._get_service_async()

        try:
            results = (
                service.permissions()
                .list(
                    fileId=file_id, fields="permissions(id, emailAddress, role, type, displayName)"
                )
                .execute()
            )

            permissions = []
            for p in results.get("permissions", []):
                permissions.append(
                    {
                        "id": p["id"],
                        "email": p.get("emailAddress", ""),
                        "name": p.get("displayName", p.get("emailAddress", "Unknown")),
                        "role": p["role"],  # owner, writer, commenter, reader
                        "type": p["type"],  # user, group, domain, anyone
                    }
                )

            logger.info(f"[TEAM_DRIVE] Listed {len(permissions)} permissions for {file_id}")
            return permissions

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error listing permissions for {file_id}: {e}")
            raise

    @drive_operation("add_permission")
    async def add_permission(
        self,
        file_id: str,
        email: str,
        role: str = "reader",
        send_notification: bool = True,
    ) -> dict[str, Any]:
        """
        Add permission for a user to access a file/folder.

        Args:
            file_id: ID of the file/folder
            email: Email of the user to grant access
            role: Permission role (reader, commenter, writer)
            send_notification: Whether to send email notification

        Returns:
            Dict with permission details
        """
        service = await self._get_service_async()

        try:
            permission = (
                service.permissions()
                .create(
                    fileId=file_id,
                    body={
                        "type": "user",
                        "role": role,
                        "emailAddress": email,
                    },
                    sendNotificationEmail=send_notification,
                    fields="id, emailAddress, role, type, displayName",
                )
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Added {role} permission for {email} on {file_id}")

            return {
                "id": permission["id"],
                "email": permission.get("emailAddress", email),
                "name": permission.get("displayName", email),
                "role": permission["role"],
                "type": permission["type"],
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error adding permission for {email} on {file_id}: {e}")
            raise

    @drive_operation("update_permission")
    async def update_permission(
        self,
        file_id: str,
        permission_id: str,
        role: str,
    ) -> dict[str, Any]:
        """
        Update permission role for a user.

        Args:
            file_id: ID of the file/folder
            permission_id: ID of the permission to update
            role: New role (reader, commenter, writer)

        Returns:
            Dict with updated permission
        """
        service = await self._get_service_async()

        try:
            permission = (
                service.permissions()
                .update(
                    fileId=file_id,
                    permissionId=permission_id,
                    body={"role": role},
                    fields="id, emailAddress, role, type, displayName",
                )
                .execute()
            )

            logger.info(f"[TEAM_DRIVE] Updated permission {permission_id} to {role} on {file_id}")

            return {
                "id": permission["id"],
                "email": permission.get("emailAddress", ""),
                "name": permission.get("displayName", ""),
                "role": permission["role"],
                "type": permission["type"],
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error updating permission {permission_id}: {e}")
            raise

    @drive_operation("remove_permission")
    async def remove_permission(
        self,
        file_id: str,
        permission_id: str,
    ) -> bool:
        """
        Remove permission for a user.

        Args:
            file_id: ID of the file/folder
            permission_id: ID of the permission to remove

        Returns:
            True if successful
        """
        service = await self._get_service_async()

        try:
            service.permissions().delete(
                fileId=file_id,
                permissionId=permission_id,
            ).execute()

            logger.info(f"[TEAM_DRIVE] Removed permission {permission_id} from {file_id}")
            return True

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error removing permission {permission_id}: {e}")
            raise


# Singleton instances
_team_drive_service: TeamDriveService | None = None
_team_drive_service_with_oauth: TeamDriveService | None = None


def get_team_drive_service(db_pool=None) -> TeamDriveService:
    """
    Get the TeamDriveService instance.

    Args:
        db_pool: Optional asyncpg pool. If provided, enables OAuth mode
                 which uses antonellosiano@gmail.com's 30TB quota.
                 If None, falls back to Service Account.

    Returns:
        TeamDriveService instance
    """
    global _team_drive_service, _team_drive_service_with_oauth

    # Get root_folder_id from settings
    root_folder_id = os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID")

    if db_pool is not None:
        # OAuth-enabled instance (with 30TB quota)
        if (
            _team_drive_service_with_oauth is None
            or _team_drive_service_with_oauth._db_pool != db_pool
        ):
            _team_drive_service_with_oauth = TeamDriveService(
                db_pool=db_pool, root_folder_id=root_folder_id
            )
        return _team_drive_service_with_oauth
    else:
        # Service Account only (fallback)
        if _team_drive_service is None:
            _team_drive_service = TeamDriveService(root_folder_id=root_folder_id)
        return _team_drive_service
