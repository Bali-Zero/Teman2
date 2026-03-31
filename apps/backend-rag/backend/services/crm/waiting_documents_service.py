"""
Waiting Documents Automation Service.

Handles automated notification when practice status changes to 'waiting_documents':
- Sends email to team leader with client details and a reminder to collect documents
- Sends email to client asking them to upload/send required documents
"""

import os
from typing import Any

import asyncpg
import httpx

from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.zoho_email_service import ZohoEmailService

# Internal email API — uses Brevo, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "zantara-secret-2024")

logger = get_logger(__name__)


class WaitingDocumentsService:
    """Handles automated notifications when practice moves to 'waiting_documents'."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.zoho_email_service = ZohoEmailService(db_pool)

    async def trigger_on_waiting_documents(
        self,
        practice_id: int,
        triggered_by: str,
    ) -> dict[str, Any]:
        """
        Trigger when practice status changes to 'waiting_documents'.

        Sends:
        1. Email to team leader: reminder to collect documents from client
        2. Email to client: request to provide required documents

        Args:
            practice_id: ID of the practice
            triggered_by: Email of user who triggered the status change

        Returns:
            dict with results of all operations
        """
        logger.info(f"Waiting documents automation triggered for practice {practice_id}")

        try:
            practice_data = await self._fetch_practice_data(practice_id)
            if not practice_data:
                return {"success": False, "error": "Practice not found"}

            client_data = await self._fetch_client_data(practice_data["client_id"])
            if not client_data:
                return {"success": False, "error": "Client not found"}

            team_leader_email = practice_data.get("assigned_to") or practice_data.get("created_by")

            results = {
                "team_leader_notified": False,
                "client_notified": False,
            }

            # Send email to team leader
            if team_leader_email:
                try:
                    await self._send_team_leader_notification(
                        team_leader_email=team_leader_email,
                        client_name=client_data["full_name"],
                        practice_data=practice_data,
                    )
                    results["team_leader_notified"] = True
                    logger.info(
                        f"Waiting docs notification sent to team leader {team_leader_email}",
                    )
                except Exception as e:
                    logger.error(f"Failed to notify team leader: {e}")
            else:
                logger.warning(f"No team leader assigned for practice {practice_id}")

            # Send email to client
            if client_data.get("email"):
                try:
                    await self._send_client_documents_request(
                        client_email=client_data["email"],
                        client_name=client_data["full_name"],
                        practice_data=practice_data,
                    )
                    results["client_notified"] = True
                    logger.info(f"Document request email sent to client {client_data['email']}")
                except Exception as e:
                    logger.error(f"Failed to send document request to client: {e}")
            else:
                logger.warning(f"Client {client_data['id']} has no email")

            await self._log_activity(
                practice_id=practice_id,
                triggered_by=triggered_by,
                description="Waiting documents - notifications sent to team leader and client",
            )

            logger.info(f"Waiting documents automation completed for practice {practice_id}")
            return {"success": True, **results}

        except Exception as error:
            logger.error(
                f"Waiting documents automation failed for practice {practice_id}: {error}",
                exc_info=True,
            )
            return {"success": False, "error": str(error)}

    async def _send_team_leader_notification(
        self,
        team_leader_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Notify team leader that documents need to be collected from the client."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")

        subject = f"[TEAM] 📋 Documents Needed — {client_name} ({practice_type})"

        body = f"""Hi there!

A practice has moved to the **Document Collection** phase and needs your attention.

👤 Client: {client_name}
🔖 Service: {practice_type}
🆔 Practice ID: {practice_data["id"]}

📋 What to do:
1. Contact the client and let them know which documents are required
2. Set a clear deadline for document submission
3. Upload received documents to the CRM
4. Once all documents are received, move to "Sending Invoice"

A document request email has already been sent to the client automatically.

🎯 Quick Access:
https://kita.balizero.com/process/{practice_data["id"]}

Let's keep things moving!

Cheers,
Zantara CRM 🤖
"""

        await self._send_with_brevo_fallback(team_leader_email, subject, body)

    async def _send_client_documents_request(
        self,
        client_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Send warm document request email to client."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")

        subject = f"[CLIENT] 📋 Documents Needed for Your {practice_type}"

        body = f"""Dear {client_name},

Thank you for choosing Zantara Indonesia! We're moving forward with your {practice_type} and we need a few documents from you to get started.

What We Need From You:

Our team will be in touch shortly with the specific list of documents required for your case. In the meantime, here are the most common documents we typically need:

📄 General Documents (may vary by service):
• Valid passport (all pages)
• Recent passport-size photos
• Proof of address
• Any relevant previous permits or visas

How to Submit Your Documents:

Option 1 — Upload to your client portal:
https://my.balizero.com

Option 2 — Send via WhatsApp to your case handler

Option 3 — Reply to this email with scans/photos

⏱️ Please submit your documents as soon as possible so we can proceed without delays.

Questions? We're Here!
If you're unsure about any document, just ask — we're happy to clarify.

Warm regards,
The Zantara Indonesia Team

---
📧 support@balizero.com | 🌐 www.balizero.com
"""

        await self._send_with_brevo_fallback(client_email, subject, body)

    async def _send_with_brevo_fallback(
        self, to_email: str, subject: str, body: str,
    ) -> None:
        """Send email via Brevo (primary), fall back to Zoho if Brevo fails."""
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

        await self.zoho_email_service.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
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
                SELECT id, full_name, email, phone, nationality
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
                "waiting_documents",
                triggered_by,
                description,
            )
