"""
Google Drive Service Account Integration

Uses Service Account credentials for server-side Google Drive access.
No user OAuth required - perfect for automated uploads.
"""

import asyncio
import json
import logging
from io import BytesIO
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class ServiceAccountDriveService:
    """Google Drive operations using Service Account credentials."""

    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self) -> None:
        """Initialize Service Account Drive Service."""
        import base64

        self.root_folder_id = settings.google_drive_root_folder_id

        # Load Service Account credentials (supports raw JSON or base64-encoded JSON)
        creds_str = getattr(settings, "google_credentials_json", None)
        if not creds_str:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not configured in settings")

        service_account_info = None

        # Try raw JSON first
        try:
            parsed = json.loads(creds_str)
            if parsed.get("type") == "service_account":
                service_account_info = parsed
                logger.info("✅ Loaded Google credentials from raw JSON")
        except json.JSONDecodeError:
            pass

        # Try base64-encoded JSON
        if not service_account_info:
            try:
                decoded = base64.b64decode(creds_str).decode("utf-8")
                parsed = json.loads(decoded)
                if parsed.get("type") == "service_account":
                    service_account_info = parsed
                    logger.info("✅ Loaded Google credentials from base64-encoded JSON")
            except Exception:
                pass

        if not service_account_info:
            raise ValueError(
                "Invalid Service Account credentials - must be raw JSON or base64-encoded JSON",
            )

        # Create credentials with Domain-wide Delegation
        # This allows the Service Account to impersonate a Workspace user
        # who has access to Shared Drives (AMBARADAM)
        base_credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=self.SCOPES,
        )

        # Impersonate a Workspace user with Shared Drive access
        # Domain-wide delegation configured in Google Admin Console for this SA
        delegated_user = "zero@balizero.com"
        self.credentials = base_credentials.with_subject(delegated_user)
        logger.info(f"✅ Using Domain-wide delegation, impersonating: {delegated_user}")

        # Build API client
        self.service = build("drive", "v3", credentials=self.credentials)

    async def create_folder(
        self,
        name: str,
        parent_id: str | None = None,
        user_id: str | None = None,  # noqa: ARG002  # Kept for API compatibility
    ) -> dict[str, Any]:
        """Create a new folder in Google Drive."""
        if not parent_id:
            parent_id = self.root_folder_id

        folder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id] if parent_id else [],
        }

        # Build request
        request = self.service.files().create(
            body=folder_metadata,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        )

        # Execute non-blocking
        import asyncio

        folder = await asyncio.to_thread(request.execute)

        logger.info(f"✅ Created folder: {name} (ID: {folder['id']})")
        return folder

    async def get_folder_structure(
        self,
        root_folder_id: str,
        user_id: str | None = None,  # noqa: ARG002  # Kept for API compatibility
    ) -> dict[str, Any]:
        """Get folder structure (list subfolders and stats)."""
        # Get root folder info
        root_request = self.service.files().get(
            fileId=root_folder_id,
            fields="id, name",
            supportsAllDrives=True,
        )

        import asyncio

        root_folder = await asyncio.to_thread(root_request.execute)

        # List subfolders
        query = f"'{root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        folders_request = self.service.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        results = await asyncio.to_thread(folders_request.execute)

        folders = results.get("files", [])

        # Count files
        file_query = f"'{root_folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        files_request = self.service.files().list(
            q=file_query,
            fields="files(id, size)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        file_results = await asyncio.to_thread(files_request.execute)

        files = file_results.get("files", [])
        total_files = len(files)
        total_size_bytes = sum(int(f.get("size", 0)) for f in files if f.get("size"))

        return {
            "root_id": root_folder["id"],
            "root_name": root_folder["name"],
            "folders": folders,
            "total_files": total_files,
            "total_size_bytes": total_size_bytes,
        }

    async def upload_file_to_folder(
        self,
        folder_id: str,
        file_content: bytes,
        file_name: str,
        mime_type: str | None = None,
        user_id: str | None = None,  # noqa: ARG002  # Kept for API compatibility
    ) -> dict[str, Any]:
        """Upload a file to Google Drive folder."""
        if not mime_type:
            mime_type = "application/octet-stream"
            if file_name.lower().endswith(".pdf"):
                mime_type = "application/pdf"
            elif file_name.lower().endswith((".png", ".jpg", ".jpeg")):
                mime_type = "image/jpeg"

        file_metadata = {"name": file_name, "parents": [folder_id]}

        # Create file stream
        file_stream = BytesIO(file_content)
        media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)

        # Build request (don't execute yet)
        request = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, size",
            supportsAllDrives=True,
        )

        # Execute in thread pool to avoid blocking event loop
        file = await asyncio.to_thread(request.execute)

        logger.info(f"✅ Uploaded: {file_name} ({file.get('size')} bytes)")
        return file

    async def create_client_folder(
        self,
        client_id: int,
        client_name: str,
        client_type: str = "individual",
        db_pool: Any | None = None,
    ) -> dict[str, Any]:
        """
        Create standardized folder structure for a new client.

        Creates: {ID}_{ClientName}/ with subfolders:
        - 00_Profile
        - 01_Immigration
        - 02_Company
        - 03_Tax
        - 04_Family
        """
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

        # Determine parent folder based on client type
        if client_type == "individual":
            parent_folder_id = getattr(settings, "gdrive_individuals_folder_id", None)
        elif client_type == "company":
            parent_folder_id = getattr(settings, "gdrive_companies_folder_id", None)
        else:
            parent_folder_id = settings.google_drive_root_folder_id

        # Fallback to root if no specific folder configured
        if not parent_folder_id:
            parent_folder_id = settings.google_drive_root_folder_id

        # Create root folder: "[ID]_[Name]"
        root_folder_name = f"{client_id}_{client_name}"
        root_folder = await self.create_folder(
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
                logger.error(f"Failed to create subfolder {subfolder_path}: {e}")
                continue

        logger.info(f"✅ Created client folder structure for {client_name}: {root_folder_id}")

        # Persist folder IDs to DB so DrivePollService can match files to clients
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    # Save root folder ID on client record
                    await conn.execute(
                        "UPDATE clients SET google_drive_folder_id = $1 WHERE id = $2",
                        root_folder_id,
                        client_id,
                    )
                    # Save each top-level subfolder to client_drive_subfolders
                    for subfolder_path, subfolder_data in subfolders.items():
                        if "/" not in subfolder_path:  # top-level only
                            await conn.execute(
                                """INSERT INTO client_drive_subfolders
                                   (client_id, subfolder_name, subfolder_id, created_at)
                                   VALUES ($1, $2, $3, NOW())
                                   ON CONFLICT DO NOTHING""",
                                client_id,
                                subfolder_path,
                                subfolder_data["id"],
                            )
                logger.info(f"✅ Drive folder IDs persisted to DB for client {client_id}")
            except Exception as e:
                logger.error(f"Failed to persist drive folder IDs for client {client_id}: {e}")

        return {
            "success": True,
            "root_folder_id": root_folder_id,
            "root_folder_url": root_folder.get("webViewLink", ""),
            "subfolders": subfolders,
        }

    async def get_start_page_token(self) -> str:
        """Get the current start page token for changes tracking."""
        request = self.service.changes().getStartPageToken(
            supportsAllDrives=True,
        )
        result = await asyncio.to_thread(request.execute)
        return result["startPageToken"]

    async def list_changes_since(self, page_token: str) -> dict[str, Any]:
        """
        List file changes since the given page token.

        Returns:
            {
                "changes": [{"fileId": "...", "file": {...}, "removed": bool}],
                "new_page_token": "...",
            }
        """
        all_changes: list[dict] = []
        current_token = page_token

        while True:
            request = self.service.changes().list(
                pageToken=current_token,
                fields="nextPageToken, newStartPageToken, changes(fileId, file(id, name, mimeType, parents, trashed), removed)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=100,
            )
            result = await asyncio.to_thread(request.execute)

            changes = result.get("changes", [])
            all_changes.extend(changes)

            if "nextPageToken" in result:
                current_token = result["nextPageToken"]
            else:
                break

        return {
            "changes": all_changes,
            "new_page_token": result.get("newStartPageToken", page_token),
        }
