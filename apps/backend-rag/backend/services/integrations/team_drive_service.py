"""
Team Drive Service - Service Account Based Access

Provides Google Drive access for all team members via a shared Service Account.
Team members authenticate via their Zoho credentials in Zantara, then access
Drive files through this service.

No individual OAuth required - the Service Account has access to shared folders.
"""

import base64
import io
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

logger = logging.getLogger(__name__)

# Path to service account credentials (local development)
CREDENTIALS_PATH = Path(__file__).parent.parent.parent.parent / "google_credentials.json"

# Environment variable for production (base64 encoded JSON)
CREDENTIALS_ENV_VAR = "GOOGLE_SERVICE_ACCOUNT_JSON"


class TeamDriveService:
    """
    Google Drive access for team members using Service Account authentication.

    The Service Account (nuzantara-bot@nuzantara.iam.gserviceaccount.com) has
    been granted access to the company's shared Drive folders.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/drive",  # Full access for CRUD operations
    ]

    # MIME type mappings for Google Docs export
    EXPORT_MIMETYPES = {
        "application/vnd.google-apps.document": "application/pdf",
        "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.presentation": "application/pdf",
    }

    def __init__(self):
        """Initialize the Team Drive service."""
        self._service = None
        self._credentials = None

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
                creds_json = base64.b64decode(env_creds).decode('utf-8')

                # Validate it's valid JSON
                json.loads(creds_json)

                # Write to temp file
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.json',
                    delete=False
                )
                temp_file.write(creds_json)
                temp_file.close()

                logger.info("[TEAM_DRIVE] Using credentials from environment variable")
                return temp_file.name

            except Exception as e:
                logger.error(f"[TEAM_DRIVE] Failed to decode credentials from env: {e}")
                return None

        return None

    def _get_service(self):
        """Get or create the Drive API service."""
        if self._service is None:
            creds_path = self._get_credentials_path()

            if not creds_path:
                raise FileNotFoundError(
                    "Google credentials not found. Either add google_credentials.json "
                    "to the backend-rag directory, or set GOOGLE_SERVICE_ACCOUNT_JSON "
                    "environment variable with base64-encoded credentials."
                )

            self._credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=self.SCOPES
            )
            self._service = build('drive', 'v3', credentials=self._credentials)
            logger.info("[TEAM_DRIVE] Service initialized with Service Account")

        return self._service

    def is_configured(self) -> bool:
        """Check if the service account credentials are available."""
        return CREDENTIALS_PATH.exists() or os.environ.get(CREDENTIALS_ENV_VAR) is not None

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
            folder_id: Optional folder ID to list contents of
            page_size: Number of results per page (max 100)
            page_token: Token for pagination
            query: Optional search query

        Returns:
            Dict with 'files' list and optional 'next_page_token'
        """
        service = self._get_service()

        # Build query
        q_parts = ["trashed = false"]
        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")
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
                files.append({
                    "id": f["id"],
                    "name": f["name"],
                    "type": "folder" if f["mimeType"] == "application/vnd.google-apps.folder" else "file",
                    "mimeType": f["mimeType"],
                    "size": int(f.get("size", 0)),
                    "modifiedTime": f.get("modifiedTime"),
                    "webViewLink": f.get("webViewLink"),
                    "thumbnailLink": f.get("thumbnailLink"),
                })

            return {
                "files": files,
                "next_page_token": results.get("nextPageToken"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error listing files: {e}")
            raise

    async def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        """
        Get metadata for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dict
        """
        service = self._get_service()

        try:
            file = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink, parents, description"
            ).execute()

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder" if file["mimeType"] == "application/vnd.google-apps.folder" else "file",
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
        service = self._get_service()

        try:
            # Get file metadata first
            file = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType"
            ).execute()

            mime_type = file["mimeType"]
            filename = file["name"]

            # Check if it's a Google Docs type that needs export
            if mime_type in self.EXPORT_MIMETYPES:
                export_mime = self.EXPORT_MIMETYPES[mime_type]
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime
                )

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

    async def get_folder_path(self, folder_id: str) -> list[dict[str, str]]:
        """
        Get the breadcrumb path to a folder.

        Args:
            folder_id: Folder ID

        Returns:
            List of {id, name} dicts from root to folder
        """
        service = self._get_service()
        path = []
        current_id = folder_id

        try:
            while current_id:
                file = service.files().get(
                    fileId=current_id,
                    fields="id, name, parents"
                ).execute()

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
        service = self._get_service()

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
            results = service.files().list(
                q=" and ".join(q_parts),
                pageSize=page_size,
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink, parents)",
                orderBy="modifiedTime desc"
            ).execute()

            return [
                {
                    "id": f["id"],
                    "name": f["name"],
                    "type": "folder" if f["mimeType"] == "application/vnd.google-apps.folder" else "file",
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
    # CRUD Operations
    # =========================================================================

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
        service = self._get_service()

        file_metadata = {
            "name": filename,
            "parents": [parent_folder_id],
        }

        try:
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )

            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink"
            ).execute()

            logger.info(f"[TEAM_DRIVE] Uploaded file: {filename} ({file['id']})")

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
        service = self._get_service()

        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }

        try:
            folder = service.files().create(
                body=file_metadata,
                fields="id, name, mimeType, modifiedTime, webViewLink"
            ).execute()

            logger.info(f"[TEAM_DRIVE] Created folder: {name} ({folder['id']})")

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
        service = self._get_service()

        mime_types = {
            "document": "application/vnd.google-apps.document",
            "spreadsheet": "application/vnd.google-apps.spreadsheet",
            "presentation": "application/vnd.google-apps.presentation",
        }

        if doc_type not in mime_types:
            raise ValueError(f"Invalid doc_type: {doc_type}. Must be one of: {list(mime_types.keys())}")

        file_metadata = {
            "name": name,
            "mimeType": mime_types[doc_type],
            "parents": [parent_folder_id],
        }

        try:
            doc = service.files().create(
                body=file_metadata,
                fields="id, name, mimeType, modifiedTime, webViewLink"
            ).execute()

            logger.info(f"[TEAM_DRIVE] Created {doc_type}: {name} ({doc['id']})")

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
        service = self._get_service()

        try:
            file = service.files().update(
                fileId=file_id,
                body={"name": new_name},
                fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink"
            ).execute()

            logger.info(f"[TEAM_DRIVE] Renamed file {file_id} to: {new_name}")

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder" if file["mimeType"] == "application/vnd.google-apps.folder" else "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error renaming file {file_id}: {e}")
            raise

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
        service = self._get_service()

        try:
            if permanent:
                service.files().delete(fileId=file_id).execute()
                logger.info(f"[TEAM_DRIVE] Permanently deleted file: {file_id}")
            else:
                service.files().update(
                    fileId=file_id,
                    body={"trashed": True}
                ).execute()
                logger.info(f"[TEAM_DRIVE] Moved to trash: {file_id}")

            return True

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error deleting file {file_id}: {e}")
            raise

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
        service = self._get_service()

        try:
            # Get current parent if not provided
            if not old_parent_id:
                current = service.files().get(
                    fileId=file_id,
                    fields="parents"
                ).execute()
                old_parent_id = current.get("parents", [None])[0]

            # Move the file
            file = service.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=old_parent_id,
                fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink, parents"
            ).execute()

            logger.info(f"[TEAM_DRIVE] Moved file {file_id} to folder {new_parent_id}")

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder" if file["mimeType"] == "application/vnd.google-apps.folder" else "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error moving file {file_id}: {e}")
            raise

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
        service = self._get_service()

        try:
            body = {}
            if new_name:
                body["name"] = new_name
            if parent_folder_id:
                body["parents"] = [parent_folder_id]

            file = service.files().copy(
                fileId=file_id,
                body=body if body else None,
                fields="id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink"
            ).execute()

            logger.info(f"[TEAM_DRIVE] Copied file {file_id} to: {file['id']}")

            return {
                "id": file["id"],
                "name": file["name"],
                "type": "folder" if file["mimeType"] == "application/vnd.google-apps.folder" else "file",
                "mimeType": file["mimeType"],
                "size": int(file.get("size", 0)),
                "modifiedTime": file.get("modifiedTime"),
                "webViewLink": file.get("webViewLink"),
                "thumbnailLink": file.get("thumbnailLink"),
            }

        except Exception as e:
            logger.error(f"[TEAM_DRIVE] Error copying file {file_id}: {e}")
            raise


# Singleton instance
_team_drive_service: TeamDriveService | None = None


def get_team_drive_service() -> TeamDriveService:
    """Get the singleton TeamDriveService instance."""
    global _team_drive_service
    if _team_drive_service is None:
        _team_drive_service = TeamDriveService()
    return _team_drive_service
