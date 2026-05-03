"""
Drive Folder Service.

Automatically creates and manages Google Drive folders for clients.
"""

from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

logger = get_logger(__name__)

# Root folder for all client folders in Drive
CLIENTS_ROOT_FOLDER_ID = "YOUR_CLIENTS_FOLDER_ID"  # Configure this


class DriveFolderService:
    """Service for managing client folders in Google Drive."""

    def __init__(self) -> None:
        self.drive_service = ServiceAccountDriveService()
        self.root_folder_id = CLIENTS_ROOT_FOLDER_ID

    async def create_client_folder(self, client_name: str, _client_id: int) -> dict[str, str]:
        """
        Create a folder for a new client in Google Drive.

        Structure: Clients/{Full Name Client}/

        Args:
            client_name: Full name of the client
            client_id: Client ID for reference

        Returns:
            dict with folder_id and folder_url
        """
        folder_name = client_name.strip()

        try:
            # Create main client folder
            folder = await self.drive_service.create_folder_async(
                folder_name=folder_name,
                parent_folder_id=self.root_folder_id,
            )

            folder_id = folder.get("id")
            folder_url = folder.get(
                "webViewLink", f"https://drive.google.com/drive/folders/{folder_id}",
            )

            # Create subfolder for Documents
            docs_folder = await self.drive_service.create_folder_async(
                folder_name="Documents",
                parent_folder_id=folder_id,
            )

            # Create subfolder for Final Documents
            final_folder = await self.drive_service.create_folder_async(
                folder_name="Final Documents",
                parent_folder_id=folder_id,
            )

            logger.info(f"Created Drive folder for client {client_name}: {folder_id}")

            return {
                "success": True,
                "folder_id": folder_id,
                "folder_url": folder_url,
                "documents_folder_id": docs_folder.get("id"),
                "final_documents_folder_id": final_folder.get("id"),
            }

        except Exception as e:
            logger.error(f"Failed to create Drive folder for client {client_name}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def upload_document(
        self,
        client_folder_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
    ) -> dict[str, str]:
        """
        Upload a document to client's Documents folder.

        Args:
            client_folder_id: The client's main folder ID
            file_content: File bytes
            filename: Name of the file
            mime_type: MIME type of the file

        Returns:
            dict with file_id and file_url
        """
        try:
            # Upload to client's folder (will be in root, can be organized later)
            result = await self.drive_service.upload_file_async(
                file_content=file_content,
                filename=filename,
                mime_type=mime_type,
                folder_id=client_folder_id,
            )

            logger.info(f"Uploaded {filename} to client folder {client_folder_id}")

            return {
                "success": True,
                "file_id": result.get("id"),
                "file_url": result.get("webViewLink"),
            }

        except Exception as e:
            logger.error(f"Failed to upload document {filename}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def upload_final_document(
        self,
        final_folder_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
    ) -> dict[str, str]:
        """
        Upload a final document to client's Final Documents folder.

        Args:
            final_folder_id: The client's Final Documents folder ID
            file_content: File bytes
            filename: Name of the file
            mime_type: MIME type of the file

        Returns:
            dict with file_id and file_url
        """
        try:
            result = await self.drive_service.upload_file_async(
                file_content=file_content,
                filename=filename,
                mime_type=mime_type,
                folder_id=final_folder_id,
            )

            logger.info(f"Uploaded final document {filename}")

            return {
                "success": True,
                "file_id": result.get("id"),
                "file_url": result.get("webViewLink"),
            }

        except Exception as e:
            logger.error(f"Failed to upload final document {filename}: {e}")
            return {
                "success": False,
                "error": str(e),
            }
