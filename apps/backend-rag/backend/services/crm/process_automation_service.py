"""
Process Automation Service.

Handles automated notifications when practice status changes:
- 'on_process': Payment confirmed, work starts
- 'completed': Process finished, documents delivered
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
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")

logger = get_logger(__name__)


class ProcessAutomationService:
    """Handles automated notifications for practice status changes."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
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
            # Fetch practice and client data
            practice_data = await self._fetch_practice_data(practice_id)
            if not practice_data:
                logger.error(f"Practice {practice_id} not found", exc_info=True)
                return {"success": False, "error": "Practice not found"}

            client_data = await self._fetch_client_data(practice_data["client_id"])
            if not client_data:
                logger.error(f"Client {practice_data['client_id']} not found")
                return {"success": False, "error": "Client not found"}

            # Get team leader email
            team_leader_email = practice_data.get("assigned_to") or practice_data.get("created_by")
            if not team_leader_email:
                logger.warning(f"No team leader assigned for practice {practice_id}")
                team_leader_email = None

            results = {
                "client_notified": False,
                "team_leader_notified": False,
            }

            # Send email to client
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
                        f"Process start notification sent to team leader {team_leader_email}",
                    )
                except Exception as e:
                    logger.error(f"Failed to send notification to team leader: {e}", exc_info=True)

            # Log activity
            await self._log_activity(
                practice_id=practice_id,
                triggered_by=triggered_by,
                description="Process started - notifications sent to client and team leader",
            )

            logger.info(f"Process start automation completed for practice {practice_id}")

            return {
                "success": True,
                **results,
            }

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

        await self._send_with_brevo_fallback(client_email, subject, body)

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
                SELECT id, full_name, email, phone, address, nationality
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
                "process_started",
                triggered_by,
                description,
            )
