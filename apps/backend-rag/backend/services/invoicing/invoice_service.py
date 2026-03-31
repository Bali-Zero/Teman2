"""
Invoice Automation Service.

Orchestrates the complete invoice workflow:
1. Generate invoice PDF locally
2. Send invoice via Zoho Email to client
3. Send notification email to Asya (accounting)
4. Upload PDF to Google Drive (backup)
5. Update practice with invoice details
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx

from backend.app.modules.notifications.service import SMTPProvider
from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService
from backend.services.integrations.zoho_email_service import ZohoEmailService
from backend.services.invoicing.invoice_generator import InvoiceGenerator

logger = get_logger(__name__)

# System user for Zoho Email operations
# Using zero@balizero.com which has Zoho OAuth token
SYSTEM_EMAIL_USER_ID = "7dfe56b2-ff63-4d40-b78b-90c018127a02"
SYSTEM_EMAIL_ADDRESS = "zero@balizero.com"

# Accounting email for invoice notifications
ACCOUNTING_EMAIL = "asya@balizero.com"

# Fallback SMTP sender (Gmail)
SMTP_SENDER_EMAIL = "zero@balizero.com"
SMTP_SENDER_NAME = "Bali Zero AI"


class InvoiceAutomationService:
    """Handles automated invoice generation and distribution via Zoho Email or SMTP fallback."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.drive_service = ServiceAccountDriveService()
        self.zoho_email_service = ZohoEmailService(db_pool)
        self.invoice_generator = InvoiceGenerator()
        self.smtp_provider = SMTPProvider()  # Fallback SMTP (Gmail)

    async def trigger_on_sending_invoice(
        self,
        practice_id: int,
        triggered_by: str,
    ) -> dict[str, Any]:
        """
        Main trigger function when practice status changes to 'sending_invoice'.

        This function:
        1. Fetches practice and client details
        2. Generates invoice PDF locally
        3. Sends invoice via Zoho Email to client
        4. Sends notification email to Asya (accounting)
        5. Uploads backup PDF to Google Drive
        6. Updates practice with invoice info

        Args:
            practice_id: ID of the practice
            triggered_by: Email of user who triggered the status change

        Returns:
            dict with results of all operations
        """
        logger.info(f"Invoice automation triggered for practice {practice_id} by {triggered_by}")

        try:
            # Step 1: Fetch practice and client data
            practice_data = await self._fetch_practice_data(practice_id)
            if not practice_data:
                logger.error(f"Practice {practice_id} not found")
                return {"success": False, "error": "Practice not found"}

            client_data = await self._fetch_client_data(practice_data["client_id"])
            if not client_data:
                logger.error(f"Client {practice_data['client_id']} not found")
                return {"success": False, "error": "Client not found"}

            # Step 2: Generate invoice PDF locally
            logger.info(f"Generating invoice PDF for practice {practice_id}")
            try:
                invoice_number = self.invoice_generator.generate_invoice_number(practice_id)

                pdf_bytes = self.invoice_generator.generate(
                    practice_id=practice_id,
                    client_name=client_data["full_name"],
                    client_email=client_data.get("email"),
                    client_phone=client_data.get("phone"),
                    client_address=client_data.get("address"),
                    practice_type=practice_data.get("practice_type_code", "SERVICE"),
                    practice_description=practice_data.get("notes", "Professional Services"),
                    quoted_price=float(practice_data.get("quoted_price", 0)),
                    notes="Thank you for choosing Zantara Indonesia. Payment is due within 7 days.",
                )

                filename = f"Invoice_{invoice_number}.pdf"
                logger.info(f"PDF generated: {filename}")

            except Exception as pdf_error:
                logger.error(f"Failed to generate PDF: {pdf_error}")
                return {"success": False, "error": f"PDF generation failed: {pdf_error}"}

            # Step 3: Send invoice email to client
            email_sent = False
            if client_data.get("email"):
                try:
                    await self._send_invoice_email_to_client(
                        client_email=client_data["email"],
                        client_name=client_data["full_name"],
                        invoice_number=invoice_number,
                        pdf_bytes=pdf_bytes,
                        filename=filename,
                        amount=float(practice_data.get("quoted_price", 0)),
                    )
                    email_sent = True
                    logger.info(f"Invoice email sent to client {client_data['email']}")
                except Exception as email_error:
                    logger.error(f"Failed to send invoice email to client: {email_error}")
            else:
                logger.warning(f"Client {client_data['id']} has no email, skipping email")

            # Step 4: Send notification email to Asya (accounting)
            asya_notified = False
            try:
                await self._send_accounting_notification(
                    client_data=client_data,
                    practice_data=practice_data,
                    invoice_number=invoice_number,
                    pdf_bytes=pdf_bytes,
                    filename=filename,
                )
                asya_notified = True
                logger.info(f"Accounting notification sent to {ACCOUNTING_EMAIL}")
            except Exception as notify_error:
                logger.warning(f"Failed to notify accounting: {notify_error}")

            # Step 5: Upload backup PDF to Google Drive
            logger.info("Uploading invoice backup to Google Drive")
            drive_file_id = None
            drive_web_link = None
            try:
                upload_result = await self.drive_service.upload_file_to_folder(
                    folder_id=practice_data.get("client_drive_folder_id"),
                    file_content=pdf_bytes,
                    file_name=filename,
                    mime_type="application/pdf",
                )
                drive_file_id = upload_result.get("id")
                drive_web_link = upload_result.get("webViewLink")
                logger.info(f"Invoice backup uploaded to Drive: {drive_file_id}")
            except Exception as drive_error:
                logger.warning(f"Failed to upload invoice backup to Drive: {drive_error}")
                # Continue even if Drive upload fails

            # Step 6: Update practice with invoice details
            invoice_info = {
                "invoice_number": invoice_number,
                "invoice_generated_at": datetime.now(tz=timezone.utc).isoformat(),
                "invoice_drive_id": drive_file_id,
                "invoice_drive_link": drive_web_link,
                "email_sent": email_sent,
                "accounting_notified": asya_notified,
                "source": "local_pdf",
            }

            await self._update_practice_with_invoice(
                practice_id=practice_id,
                invoice_info=invoice_info,
                triggered_by=triggered_by,
            )

            logger.info(f"Invoice automation completed successfully for practice {practice_id}")

            return {
                "success": True,
                "invoice_number": invoice_number,
                "drive_file_id": drive_file_id,
                "drive_link": drive_web_link,
                "email_sent": email_sent,
                "accounting_notified": asya_notified,
            }

        except Exception as error:
            logger.error(
                f"Invoice automation failed for practice {practice_id}: {error}",
                exc_info=True,
            )
            return {"success": False, "error": str(error)}

    async def _send_invoice_email_to_client(
        self,
        client_email: str,
        client_name: str,
        invoice_number: str,
        pdf_bytes: bytes,
        filename: str,
        amount: float,
    ) -> bool:
        """Send invoice email to client with PDF attachment via Zoho or SMTP fallback."""
        subject = f"Invoice {invoice_number} from Zantara Indonesia"

        body_text = f"""Dear {client_name},

Thank you for choosing Zantara Indonesia for your immigration services.

Please find your invoice attached to this email.

Invoice Details:
- Invoice Number: {invoice_number}
- Amount Due: IDR {amount:,.0f}
- Payment Terms: Net 7 days

Payment can be made via bank transfer. Please contact us for payment details or if you have any questions.

We look forward to serving you!

Best regards,
Zantara Indonesia Team

---
This is an automated email. Please do not reply to this email.
For support: support@balizero.com | WhatsApp: +62 859 0436 9574
"""

        # Try Zoho Email first
        try:
            attachment = await self.zoho_email_service.upload_attachment(
                user_id=SYSTEM_EMAIL_USER_ID,
                filename=filename,
                content=pdf_bytes,
                content_type="application/pdf",
            )
            await self.zoho_email_service.send_email(
                user_id=SYSTEM_EMAIL_USER_ID,
                to=[client_email],
                subject=subject,
                content=body_text,
                attachments=[attachment],
                is_html=False,
            )
            logger.info(f"Invoice email sent to {client_email} via Zoho")
            return True
        except Exception as zoho_error:
            logger.warning(f"Zoho email failed, trying SMTP: {zoho_error}")

            # Fallback to SMTP
            try:
                success = await self.smtp_provider.send_email(
                    to_email=client_email,
                    subject=subject,
                    html_body=body_text.replace("\n", "<br>"),
                    text_body=body_text,
                    from_email=SMTP_SENDER_EMAIL,
                    from_name=SMTP_SENDER_NAME,
                    attachments=[
                        {
                            "filename": filename,
                            "content": pdf_bytes,
                            "content_type": "application/pdf",
                        },
                    ],
                )
                if success:
                    logger.info(f"Invoice email sent to {client_email} via SMTP")
                    return True
                raise Exception("SMTP send failed")
            except Exception as smtp_error:
                logger.warning(f"SMTP also failed, trying Brevo (no attachment): {smtp_error}")

            # Last resort: Brevo (text-only, no PDF attachment)
            try:
                await self._send_via_brevo(client_email, subject, body_text)
                logger.info(f"Invoice notification sent to {client_email} via Brevo (no PDF)")
                return True
            except Exception as brevo_error:
                logger.error(f"All email providers failed for invoice to {client_email}: {brevo_error}")
                raise

    async def _send_accounting_notification(
        self,
        client_data: dict,
        practice_data: dict,
        invoice_number: str,
        pdf_bytes: bytes,
        filename: str,
    ) -> bool:
        """Send notification email to accounting (Asya) via Zoho or SMTP fallback."""
        subject = f"🎉 New Invoice {invoice_number} - {client_data['full_name']}"

        body_text = f"""Hi Asya!

Hope you're having a great day! ☺️

A new invoice has just been generated and sent to our client. Here's everything you need to know:

👤 Client Details:
   Name: {client_data["full_name"]}
   Email: {client_data.get("email", "N/A")}
   Practice ID: {practice_data["id"]}

💰 Invoice Info:
   Invoice Number: {invoice_number}
   Amount: IDR {float(practice_data.get("quoted_price", 0)):,.0f}

📎 PDF Attached to this email

✨ Your Next Steps:
1. Reach out to the client via WhatsApp for payment follow-up
2. Keep an eye on our bank account
3. Once payment comes through, update the status to "ON PROCESS"

As always, you're doing an amazing job keeping everything running smoothly!

If you need any help with this client or have questions, just give me a shout.

Have a wonderful day!

Warmly,
Zantara CRM Assistant 🤖

P.S. This is an automated email, but the appreciation for your hard work is 100% genuine! 😊
"""

        # Try Zoho Email first
        try:
            attachment = await self.zoho_email_service.upload_attachment(
                user_id=SYSTEM_EMAIL_USER_ID,
                filename=filename,
                content=pdf_bytes,
                content_type="application/pdf",
            )
            await self.zoho_email_service.send_email(
                user_id=SYSTEM_EMAIL_USER_ID,
                to=[ACCOUNTING_EMAIL],
                subject=subject,
                content=body_text,
                attachments=[attachment],
                is_html=False,
            )
            logger.info(f"Accounting notification sent to {ACCOUNTING_EMAIL} via Zoho")
            return True
        except Exception as zoho_error:
            logger.warning(f"Zoho email failed, trying SMTP: {zoho_error}")

            # Fallback to SMTP
            try:
                success = await self.smtp_provider.send_email(
                    to_email=ACCOUNTING_EMAIL,
                    subject=subject,
                    html_body=body_text.replace("\n", "<br>"),
                    text_body=body_text,
                    from_email=SMTP_SENDER_EMAIL,
                    from_name=SMTP_SENDER_NAME,
                    attachments=[
                        {
                            "filename": filename,
                            "content": pdf_bytes,
                            "content_type": "application/pdf",
                        },
                    ],
                )
                if success:
                    logger.info(f"Accounting notification sent to {ACCOUNTING_EMAIL} via SMTP")
                    return True
                raise Exception("SMTP send failed")
            except Exception as smtp_error:
                logger.warning(f"SMTP also failed for accounting, trying Brevo: {smtp_error}")

            # Last resort: Brevo (text-only, no PDF attachment)
            try:
                await self._send_via_brevo(ACCOUNTING_EMAIL, subject, body_text)
                logger.info(f"Accounting notification sent to {ACCOUNTING_EMAIL} via Brevo (no PDF)")
                return True
            except Exception as brevo_error:
                logger.error(f"All providers failed for accounting notification: {brevo_error}")
                raise

    async def _send_via_brevo(self, to_email: str, subject: str, body: str) -> None:
        """Send text-only email via Brevo internal API (no attachments)."""
        api_url = os.getenv(
            "INTERNAL_EMAIL_API_URL",
            "https://nuzantara-rag.fly.dev/api/notifications/send-email",
        )
        api_key = os.getenv("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")
        html_body = body.replace("\n", "<br>")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={"X-API-Key": api_key},
                json={"to": to_email, "subject": subject, "body": html_body},
            )
            response.raise_for_status()

    async def _fetch_practice_data(self, practice_id: int) -> dict | None:
        """Fetch practice data from database."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    p.*,
                    pt.code as practice_type_code,
                    pt.name as practice_type_name,
                    c.google_drive_folder_id as client_drive_folder_id
                FROM practices p
                LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
                LEFT JOIN clients c ON p.client_id = c.id
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

    async def _update_practice_with_invoice(
        self,
        practice_id: int,
        invoice_info: dict,
        triggered_by: str,
    ) -> None:
        """Update practice with invoice information (dual-write: JSONB + invoices table)."""
        async with self.db_pool.acquire() as conn:
            # ── 1. Fetch practice for amount + client_id ──────────────────────
            practice_row = await conn.fetchrow(
                "SELECT client_id, quoted_price FROM practices WHERE id = $1",
                practice_id,
            )

            # ── 2. JSONB write (backward compat — kept until Sprint 3 cleanup) ─
            existing_docs = await conn.fetchval(
                "SELECT documents FROM practices WHERE id = $1",
                practice_id,
            )

            documents: dict = {}
            if existing_docs:
                if isinstance(existing_docs, str):
                    try:
                        docs_str = existing_docs.strip()
                        if docs_str:
                            parsed = json.loads(docs_str)
                            if isinstance(parsed, str):
                                parsed = json.loads(parsed)
                            documents = parsed if isinstance(parsed, dict) else {}
                    except (json.JSONDecodeError, TypeError):
                        documents = {}
                elif isinstance(existing_docs, dict):
                    documents = existing_docs

            documents["invoice"] = invoice_info

            await conn.execute(
                """
                UPDATE practices
                SET documents = $1::jsonb, payment_status = 'pending', updated_at = NOW()
                WHERE id = $2
                """,
                json.dumps(documents),
                practice_id,
            )

            # ── 3. invoices table write (primary going forward) ───────────────
            if practice_row:
                generated_at_raw = invoice_info.get("invoice_generated_at")
                generated_at = None
                if generated_at_raw:
                    try:
                        generated_at = datetime.fromisoformat(generated_at_raw)
                    except ValueError:
                        pass  # invalid ISO date format — generated_at stays None

                await conn.execute(
                    """
                    INSERT INTO invoices (
                        practice_id, client_id, invoice_number, invoice_source,
                        amount_idr, drive_file_id, drive_web_link,
                        email_sent_to_client, accounting_notified, generated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (invoice_number) DO UPDATE SET
                        drive_file_id        = EXCLUDED.drive_file_id,
                        drive_web_link       = EXCLUDED.drive_web_link,
                        email_sent_to_client = EXCLUDED.email_sent_to_client,
                        accounting_notified  = EXCLUDED.accounting_notified,
                        updated_at           = NOW()
                    """,
                    practice_id,
                    practice_row["client_id"],
                    invoice_info.get("invoice_number") or None,
                    invoice_info.get("source", "local_pdf"),
                    float(practice_row["quoted_price"] or 0),
                    invoice_info.get("invoice_drive_id") or None,
                    invoice_info.get("invoice_drive_link") or None,
                    bool(invoice_info.get("email_sent", False)),
                    bool(invoice_info.get("accounting_notified", False)),
                    generated_at,
                )

            # ── 4. Activity log ───────────────────────────────────────────────
            await conn.execute(
                """
                INSERT INTO activity_log (
                    entity_type, entity_id, action, performed_by, description
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                "practice",
                practice_id,
                "invoice_generated",
                triggered_by,
                f"Invoice {invoice_info['invoice_number']} created and sent",
            )

        logger.info(f"Practice {practice_id} updated with invoice information")

    async def regenerate_invoice(
        self,
        practice_id: int,
        triggered_by: str,
    ) -> dict[str, Any]:
        """
        Manually regenerate and resend invoice for a practice.

        Useful if:
        - Client lost the invoice email
        - Need to send updated version
        - Previous automation failed
        """
        logger.info(f"Manual invoice regeneration requested for practice {practice_id}")
        return await self.trigger_on_sending_invoice(practice_id, triggered_by)
