"""
CRM Automation — consolidated module.

Merges:
  - process_automation_service.py   (ProcessAutomationService)
  - completed_process_service.py    (CompletedProcessService)
  - waiting_documents_service.py    (WaitingDocumentsService)

Shared helpers (_fetch_practice_data, _fetch_client_data,
_send_with_brevo_fallback, _log_activity) are deduplicated into
module-level functions used by all three classes.
"""

import os
from typing import Any

import asyncpg
import httpx

from backend.app.utils.logging_utils import get_logger

# Internal email API — uses Brevo, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "zantara-secret-2024")

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers (deduplicated from all three services)
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_practice_data(db_pool: asyncpg.Pool, practice_id: int) -> dict | None:
    """Fetch practice data (with practice_type join) from database."""
    async with db_pool.acquire() as conn:
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


async def _fetch_client_data(
    db_pool: asyncpg.Pool, client_id: int, *, include_drive: bool = False,
) -> dict | None:
    """Fetch client data from database.

    Args:
        include_drive: if True, include drive_folder_id / drive_final_folder_id columns.
    """
    if include_drive:
        columns = """id, full_name, email, phone,
                     drive_folder_id, drive_folder_url,
                     drive_documents_folder_id, drive_final_folder_id"""
    else:
        columns = "id, full_name, email, phone, address, nationality"

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {columns} FROM clients WHERE id = $1",
            client_id,
        )
        return dict(row) if row else None


async def _fetch_practice_with_client(
    db_pool: asyncpg.Pool, practice_id: int, *, include_drive: bool = False,
) -> tuple[dict | None, dict | None]:
    """Fetch practice + client in a single connection (eliminates N+1).

    Returns:
        (practice_data, client_data) — either may be None.
    """
    client_cols = (
        "c.id as client_db_id, c.full_name, c.email, c.phone, "
        "c.drive_folder_id, c.drive_folder_url, "
        "c.drive_documents_folder_id, c.drive_final_folder_id"
        if include_drive
        else "c.id as client_db_id, c.full_name, c.email, c.phone, c.address, c.nationality"
    )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT
                p.*,
                pt.code as practice_type_code,
                pt.name as practice_type_name,
                {client_cols}
            FROM practices p
            LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
            LEFT JOIN clients c ON p.client_id = c.id
            WHERE p.id = $1
            """,
            practice_id,
        )

    if not row:
        return None, None

    row_dict = dict(row)

    # Split into practice_data and client_data
    client_keys = {
        "client_db_id", "full_name", "email", "phone", "address", "nationality",
        "drive_folder_id", "drive_folder_url", "drive_documents_folder_id",
        "drive_final_folder_id",
    }
    client_data: dict[str, Any] = {}
    practice_data: dict[str, Any] = {}
    for k, v in row_dict.items():
        if k in client_keys:
            client_data[k] = v
        else:
            practice_data[k] = v

    # Rename client_db_id → id for backward compatibility
    if "client_db_id" in client_data:
        client_data["id"] = client_data.pop("client_db_id")

    if not client_data.get("id"):
        return practice_data, None

    return practice_data, client_data


async def _send_with_brevo_fallback(
    zoho_email_service: Any,
    to_email: str,
    subject: str,
    body: str,
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

    await zoho_email_service.send_email(
        to_email=to_email,
        subject=subject,
        body=body,
    )


async def _log_activity(
    db_pool: asyncpg.Pool,
    practice_id: int,
    triggered_by: str,
    action: str,
    description: str,
) -> None:
    """Log activity to activity_log table."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO activity_log (
                entity_type, entity_id, action, performed_by, description
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            "practice",
            practice_id,
            action,
            triggered_by,
            description,
        )


# ─────────────────────────────────────────────────────────────────────────────
# ProcessAutomationService (from process_automation_service.py)
# ─────────────────────────────────────────────────────────────────────────────

class ProcessAutomationService:
    """Handles automated notifications for practice status changes."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        from backend.services.integrations.zoho_email_service import ZohoEmailService
        self.zoho_email_service = ZohoEmailService(db_pool)

    async def trigger_on_process_start(
        self,
        practice_id: int,
        triggered_by: str,
    ) -> dict[str, Any]:
        """
        Trigger when practice status changes to 'on_process'.

        This happens when Asya confirms payment and changes status
        from 'waiting_payment' to 'on_process'.

        Sends:
        1. Email to client: Payment confirmation + process starting
        2. Email to team leader: Payment received, start working

        Args:
            practice_id: ID of the practice
            triggered_by: Email of user who triggered the status change (Asya)

        Returns:
            dict with results of all operations
        """
        logger.info(f"Process start automation triggered for practice {practice_id}")

        try:
            practice_data, client_data = await _fetch_practice_with_client(
                self.db_pool, practice_id,
            )
            if not practice_data:
                logger.error(f"Practice {practice_id} not found", exc_info=True)
                return {"success": False, "error": "Practice not found"}
            if not client_data:
                logger.error(f"Client for practice {practice_id} not found")
                return {"success": False, "error": "Client not found"}

            team_leader_email = practice_data.get("assigned_to") or practice_data.get("created_by")
            if not team_leader_email:
                logger.warning(f"No team leader assigned for practice {practice_id}")

            results = {
                "client_notified": False,
                "team_leader_notified": False,
            }

            if client_data.get("email"):
                try:
                    await self._send_client_process_start_email(
                        client_email=client_data["email"],
                        client_name=client_data["full_name"],
                        practice_data=practice_data,
                    )
                    results["client_notified"] = True
                    logger.info(f"Process start email sent to client {client_data['email']}")
                except Exception as e:
                    logger.error(f"Failed to send process start email to client: {e}", exc_info=True)
            else:
                logger.warning(f"Client {client_data['id']} has no email")

            if team_leader_email:
                try:
                    await self._send_team_leader_notification(
                        team_leader_email=team_leader_email,
                        client_name=client_data["full_name"],
                        practice_data=practice_data,
                    )
                    results["team_leader_notified"] = True
                    logger.info(
                        f"Process start notification sent to team leader {team_leader_email}",
                    )
                except Exception as e:
                    logger.error(f"Failed to send notification to team leader: {e}", exc_info=True)

            await _log_activity(
                self.db_pool,
                practice_id,
                triggered_by,
                "process_started",
                "Process started - notifications sent to client and team leader",
            )

            logger.info(f"Process start automation completed for practice {practice_id}")
            return {"success": True, **results}

        except Exception as error:
            logger.error(
                f"Process start automation failed for practice {practice_id}: {error}",
                exc_info=True,
            )
            return {"success": False, "error": str(error)}

    async def _send_client_process_start_email(
        self,
        client_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Send warm, human email to client confirming payment and process start."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")

        subject = f"[CLIENT] 🎉 Great News {client_name}! We're Starting Your {practice_type}"

        body = f"""Hi {client_name},

Wonderful news! 🎉

We've received your payment (thank you so much!), and we're officially kicking off your {practice_type} process. We're genuinely excited to help you on this journey!

Here's What Happens Next:

📋 Step 1: Document Review
Our team is carefully reviewing all your documents to ensure everything is perfect.

📝 Step 2: Application Preparation
We'll prepare and organize your application for submission to the authorities.

📤 Step 3: Submission
Once ready, we'll submit your application and handle all the back-and-forth with officials.

📊 Step 4: Progress Updates
You'll hear from us at every milestone—no need to wonder what's happening! We'll update you via email and WhatsApp.

⏱️ Timeline:
Processing times vary depending on the service type and government workload, but we'll keep you informed every step of the way. No surprises, we promise!

Track Your Progress:
You can check your case status anytime at https://my.balizero.com

Questions? We're Here!
Feel free to reach out anytime. Whether it's a quick question or just checking in, we love hearing from our clients.

Thank you again for trusting us with your immigration needs. We're honored to be part of your Indonesian journey!

Warmest regards,
The Zantara Indonesia Team

P.S. Keep an eye on your WhatsApp—we'll be sending you updates there too! 😊

---
💬 Questions? Reply to this email or WhatsApp us at +62 xxx xxxx xxxx
🌐 Visit us at www.balizero.com
"""

        await _send_with_brevo_fallback(self.zoho_email_service, client_email, subject, body)

    async def _send_team_leader_notification(
        self,
        team_leader_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Send friendly, motivating notification to team leader."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")

        subject = f"[TEAM] 🚀 Let's Go! Payment Confirmed - {client_name}"

        body = f"""Hey there!

Great news—payment has just been confirmed for {client_name}'s {practice_type}! 🎉

This one's all yours. Here are the details:

👤 Client: {client_name}
🔖 Service: {practice_type}
🆔 Practice ID: {practice_data["id"]}
💰 Amount: {practice_data.get("quoted_price", "N/A")}

✅ Asya has confirmed the payment is in, so you're good to go!

Your Mission (should you choose to accept it 😄):
1. Review the client's documents in the CRM
2. Start working your magic on the application
3. Update the status to "SUBMITTED TO GOV" when you're ready
4. Keep the client in the loop via WhatsApp—they love updates!

🎯 Quick Access:
https://kita.balizero.com/process

You've got this! We know you'll handle this case with your usual excellence.

If you need anything or have questions about this case, just holler.

Go get 'em!

Cheers,
Zantara CRM 🤖

P.S. The client is excited to get started—let's make it a great experience! ✨
"""

        await _send_with_brevo_fallback(self.zoho_email_service, team_leader_email, subject, body)

    # Keep method aliases for backward compatibility with practice_status_listener
    async def _fetch_practice_data(self, practice_id: int) -> dict | None:
        return await _fetch_practice_data(self.db_pool, practice_id)

    async def _fetch_client_data(self, client_id: int) -> dict | None:
        return await _fetch_client_data(self.db_pool, client_id)

    async def _send_with_brevo_fallback(
        self, to_email: str, subject: str, body: str,
    ) -> None:
        await _send_with_brevo_fallback(self.zoho_email_service, to_email, subject, body)

    async def _log_activity(
        self, practice_id: int, triggered_by: str, description: str,
    ) -> None:
        await _log_activity(
            self.db_pool, practice_id, triggered_by, "process_started", description,
        )


# ─────────────────────────────────────────────────────────────────────────────
# CompletedProcessService (from completed_process_service.py)
# ─────────────────────────────────────────────────────────────────────────────

class CompletedProcessService:
    """Handles automation when process is completed."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        from backend.services.integrations.drive_folder_service import DriveFolderService
        from backend.services.integrations.zoho_email_service import ZohoEmailService
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
            practice_data, client_data = await _fetch_practice_with_client(
                self.db_pool, practice_id, include_drive=True,
            )
            if not practice_data:
                return {"success": False, "error": "Practice not found"}
            if not client_data:
                return {"success": False, "error": "Client not found"}

            uploaded_docs: list[dict] = []
            if final_documents:
                uploaded_docs = await self._upload_final_documents(
                    client_data=client_data,
                    documents=final_documents,
                )

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
                    logger.error(f"Failed to send completion email to client: {e}", exc_info=True)

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
                    logger.error(f"Failed to notify team leader: {e}", exc_info=True)

            await _log_activity(
                self.db_pool,
                practice_id,
                triggered_by,
                "process_completed",
                f"Process completed - {len(uploaded_docs)} documents delivered to client",
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

        docs_section = ""
        if documents:
            docs_section = "\n📎 Your Documents:\n"
            for doc in documents:
                docs_section += f"   • {doc['filename']}: {doc['file_url']}\n"

        subject = f"[CLIENT] 🎉 Congratulations {client_name}! Your {practice_type} is Complete"

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

        await _send_with_brevo_fallback(self.zoho_email_service, client_email, subject, body)
        logger.info(f"Completion email sent to client {client_email}")

    async def _send_team_leader_completion_notification(
        self,
        team_leader_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Send notification to team leader about completion."""
        practice_type = practice_data.get("practice_type_name", "Immigration Service")

        subject = f"[TEAM] ✅ Process Completed - {client_name} ({practice_type})"

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

        await _send_with_brevo_fallback(self.zoho_email_service, team_leader_email, subject, body)

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


# ─────────────────────────────────────────────────────────────────────────────
# WaitingDocumentsService (from waiting_documents_service.py)
# ─────────────────────────────────────────────────────────────────────────────

class WaitingDocumentsService:
    """Handles automated notifications when practice moves to 'waiting_documents'."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        from backend.services.integrations.zoho_email_service import ZohoEmailService
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
            practice_data, client_data = await _fetch_practice_with_client(
                self.db_pool, practice_id,
            )
            if not practice_data:
                return {"success": False, "error": "Practice not found"}
            if not client_data:
                return {"success": False, "error": "Client not found"}

            team_leader_email = practice_data.get("assigned_to") or practice_data.get("created_by")

            results = {
                "team_leader_notified": False,
                "client_notified": False,
            }

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
                    logger.error(f"Failed to notify team leader: {e}", exc_info=True)
            else:
                logger.warning(f"No team leader assigned for practice {practice_id}")

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
                    logger.error(f"Failed to send document request to client: {e}", exc_info=True)
            else:
                logger.warning(f"Client {client_data['id']} has no email")

            await _log_activity(
                self.db_pool,
                practice_id,
                triggered_by,
                "waiting_documents",
                "Waiting documents - notifications sent to team leader and client",
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

        await _send_with_brevo_fallback(self.zoho_email_service, team_leader_email, subject, body)

    async def _send_client_documents_request(
        self,
        client_email: str,
        client_name: str,
        practice_data: dict,
    ) -> None:
        """Send document request email to client with practice-specific checklist."""
        from backend.services.crm.welcome.welcome_templates import PRACTICE_DOCUMENT_CHECKLISTS

        practice_type = practice_data.get("practice_type_name", "Immigration Service")
        practice_type_code = (practice_data.get("practice_type_code") or "").upper()

        subject = f"[CLIENT] 📋 Documents Needed for Your {practice_type}"

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

        await _send_with_brevo_fallback(self.zoho_email_service, client_email, subject, body)
