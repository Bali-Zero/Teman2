"""
Waiting Documents Automation Service.

Handles automated notification when practice status changes to 'waiting_documents':
- Sends email to team leader with client details and a reminder to collect documents
- Sends email to client asking them to upload/send required documents
"""

import os
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger
from backend.services.common.cache import cache_invalidating
from backend.services.crm.welcome.welcome_templates import PRACTICE_DOCUMENT_CHECKLISTS
from backend.services.integrations.zoho_email_service import ZohoEmailService
from backend.services.notifications.email_audit import (
    log_email_attempt,
    notify_email_failure_critical,
    record_email_result,
)
from backend.services.notifications.email_http import get_email_client

# Internal email API — uses Brevo, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")

logger = get_logger(__name__)


class WaitingDocumentsService:
    """Handles automated notifications when practice moves to 'waiting_documents'."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.zoho_email_service = ZohoEmailService(db_pool)

    @cache_invalidating([
        lambda self, practice_id, *a, **k: f"zantara:crm_practice:{practice_id}:*",  # noqa: ARG005
        "zantara:crm_practices:*",
    ])
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

        await self._send_with_brevo_fallback(
            team_leader_email,
            subject,
            body,
            email_type="waiting_docs_team",
            practice_id=practice_data["id"],
            client_id=practice_data.get("client_id"),
        )

    async def _send_client_documents_request(
        self,
        client_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Send document request email to client with practice-specific checklist."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")
        practice_type_code = (practice_data.get("practice_type_code") or "").upper()

        subject = f"[CLIENT] 📋 Documents Needed for Your {practice_type}"

        # Use practice-specific checklist if available, fall back to generic
        checklist = PRACTICE_DOCUMENT_CHECKLISTS.get(practice_type_code)
        if checklist:
            doc_list = "\n".join(f"• {item}" for item in checklist)
            doc_section = f"""📄 Documents Required for {practice_type}:
{doc_list}"""
        else:
            doc_section = """📄 General Documents (your advisor will confirm the exact list):
• Valid passport (all pages)
• Recent passport-size photos
• Proof of address
• Any relevant previous permits or visas"""

        body = f"""Dear {client_name},

Thank you for choosing Zantara Indonesia! We're moving forward with your {practice_type} and we need a few documents from you to get started.

{doc_section}

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

        await self._send_with_brevo_fallback(
            client_email,
            subject,
            body,
            email_type="waiting_docs_client",
            practice_id=practice_data["id"],
            client_id=practice_data.get("client_id"),
        )

    async def _send_with_brevo_fallback(
        self,
        to_email: str,
        subject: str,
        body: str,
        *,
        email_type: str,
        practice_id: int | None = None,
        client_id: int | None = None,
    ) -> None:
        """Send email via Brevo (primary), fall back to Zoho if Brevo fails.

        Every attempt is recorded in ``email_send_log`` so the retry worker
        can pick up drops silently. If BOTH providers fail the exception is
        re-raised after emitting a Telegram page — the caller's outer
        try/except then flips ``*_notified=False`` in the results dict.
        """
        row_id = await log_email_attempt(
            self.db_pool,
            email_type=email_type,
            to_email=to_email,
            subject=subject,
            practice_id=practice_id,
            client_id=client_id,
        )

        # 1) Brevo
        try:
            html_body = body.replace("\n", "<br>")
            client = await get_email_client()
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={"to": to_email, "subject": subject, "body": html_body},
            )
            response.raise_for_status()
            logger.info(f"Email sent to {to_email} via Brevo")
            await record_email_result(
                self.db_pool, row_id, status="sent", provider="brevo",
            )
            return
        except Exception as brevo_error:
            logger.warning(f"Brevo failed for {to_email}, trying Zoho: {brevo_error}")
            brevo_err_msg = str(brevo_error)

        # 2) Zoho fallback — wrapped so that a double-failure is observable.
        try:
            await self.zoho_email_service.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
            )
            logger.info(f"Email sent to {to_email} via Zoho fallback")
            await record_email_result(
                self.db_pool, row_id, status="sent", provider="zoho",
                error_message=f"brevo_failed: {brevo_err_msg}",
            )
            return
        except Exception as zoho_error:
            combined_err = f"brevo: {brevo_err_msg} | zoho: {zoho_error}"
            logger.error(
                f"Both Brevo and Zoho failed for {to_email}: {combined_err}",
            )
            await record_email_result(
                self.db_pool, row_id, status="failed", provider="zoho",
                error_message=combined_err,
            )
            notify_email_failure_critical(
                email_type=email_type,
                to_email=to_email,
                subject=subject,
                practice_id=practice_id,
                error=combined_err,
            )
            raise

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
