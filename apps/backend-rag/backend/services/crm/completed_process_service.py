"""
Completed Process Automation Service.

Handles automation when practice status changes to 'completed':
1. Upload final documents to client's Drive Final Documents folder
2. Send email to client with congratulations and document links
3. Send notification to team leader
"""

import os
from typing import Any

import asyncpg
import httpx

from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.drive_folder_service import DriveFolderService
from backend.services.integrations.zoho_email_service import ZohoEmailService

# Internal email API — uses Brevo, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "zantara-secret-2024")

logger = get_logger(__name__)


class CompletedProcessService:
    """Handles automation when process is completed."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.zoho_email_service = ZohoEmailService(db_pool)
        self.drive_service = DriveFolderService()

    async def trigger_on_completed(
        self,
        practice_id: int,
        triggered_by: str,
        final_documents: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Trigger when practice status changes to 'completed'.

        Args:
            practice_id: ID of the practice
            triggered_by: Email of user who triggered the status change
            final_documents: Optional list of final documents to upload

        Returns:
            dict with results of all operations
        """
        logger.info(f"Process completion automation triggered for practice {practice_id}")

        try:
            # Fetch practice and client data
            practice_data = await self._fetch_practice_data(practice_id)
            if not practice_data:
                return {"success": False, "error": "Practice not found"}

            client_data = await self._fetch_client_data(practice_data["client_id"])
            if not client_data:
                return {"success": False, "error": "Client not found"}

            # Upload final documents if provided
            uploaded_docs = []
            if final_documents:
                uploaded_docs = await self._upload_final_documents(
                    client_data=client_data,
                    documents=final_documents,
                )

            # Send email to client
            client_notified = False
            if client_data.get("email"):
                try:
                    await self._send_completion_email(
                        client_email=client_data["email"],
                        client_name=client_data["full_name"],
                        practice_data=practice_data,
                        documents=uploaded_docs,
                    )
                    client_notified = True
                except Exception as e:
                    logger.error(f"Failed to send completion email to client: {e}")

            # Send notification to team leader
            team_leader_email = practice_data.get("assigned_to") or practice_data.get("created_by")
            team_notified = False
            if team_leader_email:
                try:
                    await self._send_team_leader_completion_notification(
                        team_leader_email=team_leader_email,
                        client_name=client_data["full_name"],
                        practice_data=practice_data,
                    )
                    team_notified = True
                except Exception as e:
                    logger.error(f"Failed to notify team leader: {e}")

            # Log activity
            await self._log_activity(
                practice_id=practice_id,
                triggered_by=triggered_by,
                description=f"Process completed - {len(uploaded_docs)} documents delivered to client",
            )

            return {
                "success": True,
                "client_notified": client_notified,
                "team_notified": team_notified,
                "documents_uploaded": len(uploaded_docs),
            }

        except Exception as error:
            logger.error(
                f"Process completion automation failed for practice {practice_id}: {error}",
                exc_info=True,
            )
            return {"success": False, "error": str(error)}

    async def _upload_final_documents(
        self,
        client_data: dict,
        documents: list[dict],
    ) -> list[dict]:
        """Upload final documents to client's Final Documents folder."""
        uploaded = []

        final_folder_id = client_data.get("drive_final_folder_id")
        if not final_folder_id:
            logger.warning(f"No final folder for client {client_data['id']}")
            return uploaded

        for doc in documents:
            try:
                result = await self.drive_service.upload_final_document(
                    final_folder_id=final_folder_id,
                    file_content=doc["content"],
                    filename=doc["filename"],
                    mime_type=doc.get("mime_type", "application/pdf"),
                )

                if result.get("success"):
                    uploaded.append(
                        {
                            "filename": doc["filename"],
                            "file_url": result["file_url"],
                        },
                    )

                    # Save to database
                    await self._save_final_document_record(
                        client_id=client_data["id"],
                        filename=doc["filename"],
                        drive_file_id=result["file_id"],
                        drive_file_url=result["file_url"],
                    )

            except Exception as e:
                logger.error(f"Failed to upload {doc['filename']}: {e}")

        return uploaded

    async def _send_completion_email(
        self,
        client_email: str,
        client_name: str,
        practice_data: dict,
        documents: list[dict],
    ) -> None:
        """Send human, congratulatory email to client."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")

        # Build document links section
        docs_section = ""
        if documents:
            docs_section = "\n📎 Your Documents:\n"
            for doc in documents:
                docs_section += f"   • {doc['filename']}: {doc['file_url']}\n"

        subject = f"🎉 Congratulations {client_name}! Your {practice_type} is Complete"

        body = f"""Dear {client_name},

Great news! We're thrilled to inform you that your {practice_type} process has been successfully completed! 🎉

This is an exciting milestone, and we couldn't be happier to share it with you. Your documents are now ready, and you can officially enjoy your new status in Indonesia.

What This Means for You:
✅ Your application has been approved by the authorities
✅ All legal requirements have been fulfilled
✅ You can now proceed with confidence in your Indonesian journey

{docs_section}
All your important documents are safely stored in your personal Google Drive folder. You can access them anytime through the link above.

A Few Things to Remember:
• Keep your documents secure and make backup copies
• Note any important renewal dates (we'll remind you too!)
• Don't hesitate to reach out if you have any questions

We're Here for You:
This may be the end of this particular process, but it's not goodbye! Our team remains available to support you with:
• Future renewals or extensions
• Additional services you might need
• Any questions about living and working in Indonesia

Thank You for Trusting Us:
It's been our privilege to help you navigate this journey. Thank you for choosing Zantara Indonesia—we truly appreciate your trust in our team.

We'd love to hear about your experience! If you have a moment, please let us know how we did. Your feedback helps us serve even better.

Wishing you all the best in your Indonesian adventure!

Warm regards,
The Zantara Indonesia Team

P.S. Save our contact info for future needs—we're always here to help! 😊

---
📧 support@balizero.com | 🌐 www.balizero.com | 📱 WhatsApp: +62 xxx xxxx xxxx
"""

        await self._send_with_brevo_fallback(client_email, subject, body)
        logger.info(f"Completion email sent to client {client_email}")

    async def _send_team_leader_completion_notification(
        self,
        team_leader_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Send notification to team leader about completion."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")

        subject = f"✅ Process Completed - {client_name} ({practice_type})"

        body = f"""Hi Team Leader,

Great work! The following practice has been successfully completed:

📋 Practice Details:
• Client: {client_name}
• Service: {practice_type}
• Practice ID: {practice_data["id"]}
• Status: ✅ COMPLETED

The client has been notified and all final documents have been delivered to their Google Drive folder.

No further action required on this case.

Best regards,
Zantara CRM System
"""

        await self._send_with_brevo_fallback(team_leader_email, subject, body)

    async def _send_with_brevo_fallback(
        self, to_email: str, subject: str, body: str,
    ) -> None:
        """Send email via Brevo (primary), fall back to Zoho if Brevo fails."""
        # Primary: Brevo
        try:
            html_body = body.replace("\n", "<br>")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _EMAIL_API_URL,
                    headers={"X-API-Key": _EMAIL_API_KEY},
                    json={"to": to_email, "subject": subject, "body": html_body},
                )
                response.raise_for_status()
            logger.info(f"Email sent to {to_email} via Brevo")
            return
        except Exception as brevo_error:
            logger.warning(f"Brevo failed for {to_email}, trying Zoho: {brevo_error}")

        # Fallback: Zoho
        await self.zoho_email_service.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
        )

    async def _save_final_document_record(
        self,
        client_id: int,
        filename: str,
        drive_file_id: str,
        drive_file_url: str,
    ) -> None:
        """Save final document record."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO client_documents (
                    client_id, filename, document_type,
                    drive_file_id, drive_file_url, uploaded_by, is_final,
                    uploaded_at
                )
                VALUES ($1, $2, 'final_document', $3, $4, 'system', true, NOW())
                """,
                client_id,
                filename,
                drive_file_id,
                drive_file_url,
            )

    async def _fetch_practice_data(self, practice_id: int) -> dict | None:
        """Fetch practice data from database."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    p.*,
                    pt.code as practice_type_code,
                    pt.name as practice_type_name
                FROM practices p
                LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.id = $1
                """,
                practice_id,
            )
            return dict(row) if row else None

    async def _fetch_client_data(self, client_id: int) -> dict | None:
        """Fetch client data from database."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id, full_name, email, phone,
                    drive_folder_id, drive_folder_url,
                    drive_documents_folder_id, drive_final_folder_id
                FROM clients
                WHERE id = $1
                """,
                client_id,
            )
            return dict(row) if row else None

    async def _log_activity(
        self,
        practice_id: int,
        triggered_by: str,
        description: str,
    ) -> None:
        """Log activity to activity_log table."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity_log (
                    entity_type, entity_id, action, performed_by, description
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                "practice",
                practice_id,
                "process_completed",
                triggered_by,
                description,
            )
