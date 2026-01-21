"""
Google Drive Service Account Integration

Uses Service Account credentials for server-side Google Drive access.
No user OAuth required - perfect for automated uploads.
"""

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

    def __init__(self):
        """Initialize Service Account Drive Service."""
        self.root_folder_id = settings.google_drive_root_folder_id

        # Load Service Account credentials (uses GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_CREDENTIALS_JSON)
        if hasattr(settings, 'google_credentials_json') and settings.google_credentials_json:
            try:
                service_account_info = json.loads(settings.google_credentials_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Service Account JSON: {e}")
                raise ValueError("Invalid Service Account JSON format")
        else:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not configured in settings")

        # Create credentials
        self.credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=self.SCOPES
        )

        # Build API client
        self.service = build('drive', 'v3', credentials=self.credentials)

    async def create_folder(
        self,
        name: str,
        parent_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new folder in Google Drive."""
        if not parent_id:
            parent_id = self.root_folder_id

        folder_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id] if parent_id else []
        }

        folder = self.service.files().create(
            body=folder_metadata,
            fields='id, name, webViewLink'
        ).execute()

        logger.info(f"✅ Created folder: {name} (ID: {folder['id']})")
        return folder

    async def get_folder_structure(
        self,
        root_folder_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get folder structure (list subfolders and stats)."""
        # Get root folder info
        root_folder = self.service.files().get(
            fileId=root_folder_id,
            fields='id, name'
        ).execute()

        # List subfolders
        query = f"'{root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(
            q=query,
            fields='files(id, name)',
            pageSize=100
        ).execute()

        folders = results.get('files', [])

        # Count files
        file_query = f"'{root_folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        file_results = self.service.files().list(
            q=file_query,
            fields='files(id, size)',
            pageSize=1000
        ).execute()

        files = file_results.get('files', [])
        total_files = len(files)
        total_size_bytes = sum(int(f.get('size', 0)) for f in files if f.get('size'))

        return {
            "root_id": root_folder['id'],
            "root_name": root_folder['name'],
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
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Upload a file to Google Drive folder."""
        if not mime_type:
            mime_type = 'application/octet-stream'
            if file_name.lower().endswith('.pdf'):
                mime_type = 'application/pdf'
            elif file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                mime_type = 'image/jpeg'

        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }

        # Create file stream
        file_stream = BytesIO(file_content)
        media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)

        # Upload
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, size'
        ).execute()

        logger.info(f"✅ Uploaded: {file_name} ({file.get('size')} bytes)")
        return file
