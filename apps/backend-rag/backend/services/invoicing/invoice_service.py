"""
Invoice Automation Service.

Orchestrates the complete invoice workflow:
1. Generate PDF invoice
2. Upload to Google Drive
3. Send via Email
4. Send via WhatsApp
5. Update practice with invoice details
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, Any

import asyncpg
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from backend.core.logging_utils import get_logger
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService
from .invoice_generator import InvoiceGenerator

logger = get_logger(__name__)


class InvoiceAutomationService:
    """Handles automated invoice generation and distribution for practice quotations."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.invoice_generator = InvoiceGenerator()
        self.drive_service = ServiceAccountDriveService()

    async def trigger_on_quotation_sent(
        self,
        practice_id: int,
        triggered_by: str,
    ) -> dict[str, Any]:
        """
        Main trigger function when practice status changes to 'quotation_sent'.

        This function:
        1. Fetches practice and client details
        2. Generates PDF invoice
        3. Uploads to Google Drive
        4. Sends email to client
        5. Sends WhatsApp message to client
        6. Updates practice with invoice info

        Args:
            practice_id: ID of the practice
            triggered_by: Email of user who triggered the status change

        Returns:
            dict with results of all operations
        """
        logger.info(
            f"Invoice automation triggered for practice {practice_id} by {triggered_by}"
        )

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

            # Step 2: Generate PDF invoice
            logger.info(f"Generating invoice PDF for practice {practice_id}")
            pdf_bytes = self.invoice_generator.generate(
                practice_id=practice_id,
                client_name=client_data["full_name"],
                client_email=client_data.get("email"),
                client_phone=client_data.get("phone"),
                client_address=client_data.get("address"),
                practice_type=practice_data["practice_type_code"],
                practice_description=practice_data.get("notes"),
                quoted_price=float(practice_data.get("quoted_price", 0)),
                notes="Thank you for choosing Zantara Indonesia. We look forward to serving you.",
            )

            invoice_number = self.invoice_generator.generate_invoice_number(practice_id)
            filename = f"Invoice_{invoice_number}.pdf"

            # Step 3: Upload to Google Drive
            logger.info(f"Uploading invoice to Google Drive: {filename}")
            drive_file_id = None
            drive_web_link = None
            try:
                # Upload to specific folder (you can configure this)
                # For now, uploads to root. In production, create "Invoices" folder
                upload_result = await self.drive_service.upload_file_async(
                    file_content=pdf_bytes,
                    filename=filename,
                    mime_type="application/pdf",
                    # folder_id="<INVOICES_FOLDER_ID>"  # Configure this
                )
                drive_file_id = upload_result.get("id")
                drive_web_link = upload_result.get("webViewLink")
                logger.info(f"Invoice uploaded to Drive: {drive_file_id}")
            except Exception as drive_error:
                logger.error(f"Failed to upload invoice to Drive: {drive_error}")
                # Continue even if Drive upload fails

            # Step 4: Send Email
            email_sent = False
            if client_data.get("email"):
                try:
                    await self._send_email(
                        to_email=client_data["email"],
                        client_name=client_data["full_name"],
                        invoice_number=invoice_number,
                        amount=float(practice_data.get("quoted_price", 0)),
                        pdf_bytes=pdf_bytes,
                        filename=filename,
                        drive_link=drive_web_link,
                    )
                    email_sent = True
                    logger.info(f"Invoice email sent to {client_data['email']}")
                except Exception as email_error:
                    logger.error(f"Failed to send invoice email: {email_error}")
            else:
                logger.warning(f"Client {client_data['id']} has no email, skipping email")

            # Step 5: Send WhatsApp
            whatsapp_sent = False
            if client_data.get("phone"):
                try:
                    await self._send_whatsapp(
                        phone=client_data["phone"],
                        client_name=client_data["full_name"],
                        invoice_number=invoice_number,
                        amount=float(practice_data.get("quoted_price", 0)),
                        drive_link=drive_web_link,
                    )
                    whatsapp_sent = True
                    logger.info(f"WhatsApp notification sent to {client_data['phone']}")
                except Exception as whatsapp_error:
                    logger.error(f"Failed to send WhatsApp notification: {whatsapp_error}")
            else:
                logger.warning(f"Client {client_data['id']} has no phone, skipping WhatsApp")

            # Step 6: Update practice with invoice details
            invoice_info = {
                "invoice_number": invoice_number,
                "invoice_generated_at": datetime.now().isoformat(),
                "invoice_drive_id": drive_file_id,
                "invoice_drive_link": drive_web_link,
                "email_sent": email_sent,
                "whatsapp_sent": whatsapp_sent,
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
                "whatsapp_sent": whatsapp_sent,
            }

        except Exception as error:
            logger.error(
                f"Invoice automation failed for practice {practice_id}: {error}",
                exc_info=True,
            )
            return {"success": False, "error": str(error)}

    async def _fetch_practice_data(self, practice_id: int) -> Optional[dict]:
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

    async def _fetch_client_data(self, client_id: int) -> Optional[dict]:
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

    async def _send_email(
        self,
        to_email: str,
        client_name: str,
        invoice_number: str,
        amount: float,
        pdf_bytes: bytes,
        filename: str,
        drive_link: Optional[str] = None,
    ) -> None:
        """
        Send invoice email to client.

        Note: This is a placeholder. In production, use:
        - SendGrid API
        - AWS SES
        - SMTP with proper configuration
        """
        # TODO: Implement actual email sending with your email service
        # For now, just log what would be sent

        email_body = f"""
Dear {client_name},

Thank you for choosing Zantara Indonesia for your immigration services.

Please find attached your invoice {invoice_number} for the amount of IDR {amount:,.0f}.

Payment is due within 7 days from the invoice date.

{f'You can also view/download your invoice here: {drive_link}' if drive_link else ''}

If you have any questions, please don't hesitate to contact us.

Best regards,
Zantara Indonesia Team
"""

        logger.info(
            f"[EMAIL PLACEHOLDER] Would send to {to_email}:\n"
            f"Subject: Invoice {invoice_number} - Zantara Indonesia\n"
            f"Body: {email_body}\n"
            f"Attachment: {filename} ({len(pdf_bytes)} bytes)"
        )

        # TODO: Actual implementation
        # msg = MIMEMultipart()
        # msg['From'] = "billing@zantara.com"
        # msg['To'] = to_email
        # msg['Subject'] = f"Invoice {invoice_number} - Zantara Indonesia"
        # msg.attach(MIMEText(email_body, 'plain'))
        # pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        # pdf_attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        # msg.attach(pdf_attachment)
        # # Send via SMTP or API

    async def _send_whatsapp(
        self,
        phone: str,
        client_name: str,
        invoice_number: str,
        amount: float,
        drive_link: Optional[str] = None,
    ) -> None:
        """
        Send WhatsApp notification to client.

        Note: This is a placeholder. In production, use:
        - WhatsApp Business API
        - Twilio WhatsApp API
        - Third-party WhatsApp services
        """
        # TODO: Implement actual WhatsApp sending with WhatsApp Business API

        message = f"""
Hello {client_name},

Your invoice {invoice_number} for IDR {amount:,.0f} has been generated.

{f'View/Download: {drive_link}' if drive_link else ''}

Payment is due within 7 days. Contact us for any questions.

Best regards,
Zantara Indonesia
"""

        logger.info(
            f"[WHATSAPP PLACEHOLDER] Would send to {phone}:\n{message}"
        )

        # TODO: Actual implementation using WhatsApp Business API
        # await whatsapp_api.send_message(
        #     to=phone,
        #     message=message,
        #     attachment_url=drive_link if drive_link else None
        # )

    async def _update_practice_with_invoice(
        self,
        practice_id: int,
        invoice_info: dict,
        triggered_by: str,
    ) -> None:
        """Update practice with invoice information."""
        async with self.db_pool.acquire() as conn:
            # Get existing documents
            existing_docs = await conn.fetchval(
                "SELECT documents FROM practices WHERE id = $1",
                practice_id,
            )

            # Merge with new invoice info
            documents = existing_docs or {}
            if isinstance(documents, str):
                documents = json.loads(documents)

            documents["invoice"] = invoice_info

            # Update practice
            await conn.execute(
                """
                UPDATE practices
                SET
                    documents = $1,
                    payment_status = 'pending',
                    updated_at = NOW()
                WHERE id = $2
                """,
                json.dumps(documents),
                practice_id,
            )

            # Log to activity_log
            await conn.execute(
                """
                INSERT INTO activity_log (
                    entity_type, entity_id, action, performed_by, description
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                "practice",
                practice_id,
                "invoice_generated",
                triggered_by,
                f"Invoice {invoice_info['invoice_number']} generated and sent automatically",
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
        - Client lost the invoice
        - Need to send updated version
        - Previous automation failed
        """
        logger.info(f"Manual invoice regeneration requested for practice {practice_id}")
        return await self.trigger_on_quotation_sent(practice_id, triggered_by)
