"""
CRM Automation — ProcessAutomationService + shared helpers.

Note (2026-08-08): this module's docstring used to claim it also
"merges" completed_process_service.py (CompletedProcessService) and
waiting_documents_service.py (WaitingDocumentsService) — it never did.
Those two classes were duplicated in here but the standalone files were
never deleted, and the only live callers (crm_practices.py) import from
the standalone modules directly. The duplicates (dead code — zero
production imports, only self-referential tests) were removed.

Shared helpers (_fetch_practice_data, _fetch_client_data,
_send_with_brevo_fallback, _log_activity) are used by ProcessAutomationService.
"""

import os
from typing import Any

import asyncpg
import httpx

from backend.app.core.config import settings
from backend.app.utils.logging_utils import get_logger
from backend.services.common.cache import cache_invalidating

# Internal email API — uses Brevo, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", os.environ.get("NUZANTARA_API_KEY", ""))

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
    db_pool: asyncpg.Pool,
    client_id: int,
    *,
    include_drive: bool = False,
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
    db_pool: asyncpg.Pool,
    practice_id: int,
    *,
    include_drive: bool = False,
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
        "client_db_id",
        "full_name",
        "email",
        "phone",
        "address",
        "nationality",
        "drive_folder_id",
        "drive_folder_url",
        "drive_documents_folder_id",
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
        logger.info("Email sent to %s via Brevo", to_email)
        return
    except (httpx.HTTPError, httpx.InvalidURL) as brevo_error:
        logger.warning("Brevo failed for %s, trying Zoho: %s", to_email, brevo_error)
    except Exception as brevo_error:
        logger.warning(
            "Brevo failed for %s (unexpected error), trying Zoho: %s",
            to_email,
            brevo_error,
            exc_info=True,
        )

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

    @cache_invalidating(
        [
            lambda self, practice_id, *a, **k: f"zantara:crm_practice:{practice_id}:*",
            "zantara:crm_practices:*",
            "zantara:crm_activity:*",
        ]
    )
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
        logger.info("Process start automation triggered for practice %s", practice_id)

        try:
            practice_data, client_data = await _fetch_practice_with_client(
                self.db_pool,
                practice_id,
            )
            if not practice_data:
                logger.error("Practice %s not found", practice_id)
                return {"success": False, "error": "Practice not found"}
            if not client_data:
                logger.error("Client for practice %s not found", practice_id)
                return {"success": False, "error": "Client not found"}

            team_leader_email = practice_data.get("assigned_to") or practice_data.get("created_by")
            if not team_leader_email:
                logger.warning("No team leader assigned for practice %s", practice_id)

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
                except (httpx.HTTPError, ValueError) as e:
                    logger.error(
                        "Failed to send process start email to client: %s", e, exc_info=True
                    )
                except Exception as e:
                    logger.error(
                        "Unexpected error sending process start email to client: %s",
                        e,
                        exc_info=True,
                    )
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
                        "Process start notification sent to team leader %s",
                        team_leader_email,
                    )
                except (httpx.HTTPError, ValueError) as e:
                    logger.error("Failed to send notification to team leader: %s", e, exc_info=True)
                except Exception as e:
                    logger.error(
                        "Unexpected error notifying team leader: %s",
                        e,
                        exc_info=True,
                    )

            await _log_activity(
                self.db_pool,
                practice_id,
                triggered_by,
                "process_started",
                "Process started - notifications sent to client and team leader",
            )

            logger.info("Process start automation completed for practice %s", practice_id)
            return {"success": True, **results}

        except Exception as error:
            logger.error(
                "Process start automation failed for practice %s: %s",
                practice_id,
                error,
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
Zantara — Bali Zero Team

P.S. Keep an eye on your WhatsApp—we'll be sending you updates there too! 😊

---
💬 Questions? Reply to this email or WhatsApp us at {settings.CLIENT_CONTACT_WHATSAPP}
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
        self,
        to_email: str,
        subject: str,
        body: str,
    ) -> None:
        await _send_with_brevo_fallback(self.zoho_email_service, to_email, subject, body)

    async def _log_activity(
        self,
        practice_id: int,
        triggered_by: str,
        description: str,
    ) -> None:
        await _log_activity(
            self.db_pool,
            practice_id,
            triggered_by,
            "process_started",
            description,
        )

