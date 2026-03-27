"""
Document Upload Service.

Handles document uploads from both:
- Client portal (my.balizero.com)
- Team leader CRM interface

Automatically uploads to client's Google Drive folder.
"""

from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.drive_folder_service import DriveFolderService

logger = get_logger(__name__)


class DocumentUploadService:
    """Service for handling document uploads to Drive."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.drive_service = DriveFolderService()

    async def upload_from_portal(
        self,
        client_id: int,
        file_content: bytes,
        filename: str,
        document_type: str,  # e.g., 'passport', 'kitas', 'contract'
        mime_type: str = "application/pdf",
    ) -> dict[str, Any]:
        """
        Client uploads document from portal (my.balizero.com).

        Args:
            client_id: ID of the client
            file_content: File bytes
            filename: Original filename
            document_type: Type of document
            mime_type: MIME type

        Returns:
            dict with upload results
        """
        return await self._upload_document(
            client_id=client_id,
            file_content=file_content,
            filename=filename,
            document_type=document_type,
            mime_type=mime_type,
            uploaded_by="client",
        )

    async def upload_from_crm(
        self,
        client_id: int,
        file_content: bytes,
        filename: str,
        document_type: str,
        uploaded_by_email: str,
        mime_type: str = "application/pdf",
    ) -> dict[str, Any]:
        """
        Team leader uploads document from CRM.

        Args:
            client_id: ID of the client
            file_content: File bytes
            filename: Original filename
            document_type: Type of document
            uploaded_by_email: Email of team member who uploaded
            mime_type: MIME type

        Returns:
            dict with upload results
        """
        return await self._upload_document(
            client_id=client_id,
            file_content=file_content,
            filename=filename,
            document_type=document_type,
            mime_type=mime_type,
            uploaded_by=uploaded_by_email,
        )

    async def _upload_document(
        self,
        client_id: int,
        file_content: bytes,
        filename: str,
        document_type: str,
        mime_type: str,
        uploaded_by: str,
    ) -> dict[str, Any]:
        """Internal method to handle document upload."""

        # Get client data
        client_data = await self._fetch_client_data(client_id)
        if not client_data:
            return {"success": False, "error": "Client not found"}

        # Get or create Drive folder
        drive_data = await self._get_or_create_drive_folder(client_id, client_data)
        if not drive_data.get("success"):
            return {"success": False, "error": drive_data.get("error", "Drive folder error")}

        # Upload to Drive
        upload_result = await self.drive_service.upload_document(
            client_folder_id=drive_data["folder_id"],
            file_content=file_content,
            filename=filename,
            mime_type=mime_type,
        )

        if not upload_result.get("success"):
            return {"success": False, "error": upload_result.get("error", "Upload failed")}

        # Save to database
        await self._save_document_record(
            client_id=client_id,
            filename=filename,
            document_type=document_type,
            drive_file_id=upload_result["file_id"],
            drive_file_url=upload_result["file_url"],
            uploaded_by=uploaded_by,
        )

        logger.info(f"Document {filename} uploaded for client {client_id}")

        return {
            "success": True,
            "file_id": upload_result["file_id"],
            "file_url": upload_result["file_url"],
            "folder_url": drive_data["folder_url"],
        }

    async def _fetch_client_data(self, client_id: int) -> dict | None:
        """Fetch client data from database."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, full_name, email, drive_folder_id, drive_folder_url
                FROM clients
                WHERE id = $1
                """,
                client_id,
            )
            return dict(row) if row else None

    async def _get_or_create_drive_folder(
        self,
        client_id: int,
        client_data: dict,
    ) -> dict[str, Any]:
        """Get existing Drive folder or create new one."""

        # Check if folder already exists
        if client_data.get("drive_folder_id"):
            return {
                "success": True,
                "folder_id": client_data["drive_folder_id"],
                "folder_url": client_data.get("drive_folder_url", ""),
            }

        # Create new folder
        folder_result = await self.drive_service.create_client_folder(
            client_name=client_data["full_name"],
            client_id=client_id,
        )

        if not folder_result.get("success"):
            return folder_result

        # Save folder info to database
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE clients
                SET
                    drive_folder_id = $1,
                    drive_folder_url = $2,
                    drive_documents_folder_id = $3,
                    drive_final_folder_id = $4,
                    updated_at = NOW()
                WHERE id = $5
                """,
                folder_result["folder_id"],
                folder_result["folder_url"],
                folder_result["documents_folder_id"],
                folder_result["final_documents_folder_id"],
                client_id,
            )

        return {
            "success": True,
            "folder_id": folder_result["folder_id"],
            "folder_url": folder_result["folder_url"],
            "documents_folder_id": folder_result["documents_folder_id"],
            "final_folder_id": folder_result["final_documents_folder_id"],
        }

    async def _save_document_record(
        self,
        client_id: int,
        filename: str,
        document_type: str,
        drive_file_id: str,
        drive_file_url: str,
        uploaded_by: str,
    ) -> None:
        """Save document record to database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO client_documents (
                    client_id, filename, document_type,
                    drive_file_id, drive_file_url, uploaded_by,
                    uploaded_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                client_id,
                filename,
                document_type,
                drive_file_id,
                drive_file_url,
                uploaded_by,
            )

    async def get_client_documents(self, client_id: int) -> list[dict]:
        """Get all documents for a client."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id, filename, document_type, drive_file_url,
                    uploaded_by, uploaded_at
                FROM client_documents
                WHERE client_id = $1
                ORDER BY uploaded_at DESC
                """,
                client_id,
            )
            return [dict(row) for row in rows]
