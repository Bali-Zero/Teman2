"""
Invoice Automation Service.

Orchestrates the complete invoice workflow:
1. Generate invoice PDF locally
2. Send invoice via Zoho Email to client
3. Send notification email to Asya (accounting)
4. Upload PDF to Google Drive (backup)
5. Update practice with invoice details
"""

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx
from googleapiclient.errors import HttpError as GoogleHttpError

from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService
from backend.services.invoicing.invoice_generator import InvoiceGenerator
from backend.services.notifications.email_audit import (
    log_email_attempt,
    notify_email_failure_critical,
    record_email_result,
)
from backend.services.notifications.email_branding import logo_header_html, team_email_html
from backend.services.notifications.email_http import get_email_client

logger = get_logger(__name__)

# Accounting email for invoice notifications
ACCOUNTING_EMAIL = "asya@balizero.com"

# CC on all invoice emails: owner + accounting
INVOICE_CC_EMAILS = ["zero@balizero.com", "asya@balizero.com"]

# Internal email API (sender is always zantara@balizero.com)
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")


class InvoiceAutomationService:
    """Handles automated invoice generation and distribution via Zoho Email or SMTP fallback."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.drive_service = ServiceAccountDriveService()
        self.invoice_generator = InvoiceGenerator()

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

                # Discount fields — added migration 158 (2026-05-06).
                # Optional and default 0/None for legacy rows that predate
                # the columns. The generator handles 0 as "no discount" so
                # the existing visual stays untouched for non-discounted
                # invoices.
                discount_value = practice_data.get("discount_amount")
                discount_amount_float = (
                    float(discount_value) if discount_value is not None else 0.0
                )
                discount_reason_value = practice_data.get("discount_reason")
                quoted_price_float = float(practice_data.get("quoted_price", 0))
                # Defensive clamp matches the generator's logic so the email,
                # PDF, and invoices.amount_idr all converge on the same value.
                if discount_amount_float < 0:
                    discount_amount_float = 0.0
                if discount_amount_float > quoted_price_float:
                    discount_amount_float = quoted_price_float
                final_amount_float = quoted_price_float - discount_amount_float

                pdf_bytes = self.invoice_generator.generate(
                    practice_id=practice_id,
                    client_name=client_data["full_name"],
                    client_email=client_data.get("email"),
                    client_phone=client_data.get("phone"),
                    client_address=client_data.get("address"),
                    practice_type=practice_data.get("practice_type_code", "SERVICE"),
                    practice_description=practice_data.get("notes", "Professional Services"),
                    quoted_price=float(practice_data.get("quoted_price", 0)),
                    notes="Thank you for choosing Bali Zero. Payment is due within 2 days.",
                    discount_amount=discount_amount_float,
                    discount_reason=discount_reason_value,
                )

                filename = f"Invoice_{invoice_number}.pdf"
                logger.info(f"PDF generated: {filename}")

            except (OSError, ValueError, KeyError) as pdf_error:
                logger.warning(f"Failed to generate PDF: {pdf_error}")
                return {"success": False, "error": f"PDF generation failed: {pdf_error}"}
            except Exception as pdf_error:
                logger.exception(f"Unexpected error generating PDF for practice {practice_id}")
                return {"success": False, "error": f"PDF generation failed: {pdf_error}"}

            # Step 3: Send invoice email to client
            # Audit bug #9: failure now persists to email_send_log AND
            # pages the owner via Telegram when the client email is lost —
            # previously AR aging started silently with email_sent=False
            # only visible during Asya's manual ledger review.
            email_sent = False
            if client_data.get("email"):
                audit_row_id = await log_email_attempt(
                    self.db_pool,
                    email_type="invoice_client",
                    to_email=client_data["email"],
                    subject=f"Invoice {invoice_number} from Bali Zero",
                    practice_id=practice_id,
                    client_id=client_data["id"],
                )
                try:
                    await self._send_invoice_email_to_client(
                        client_email=client_data["email"],
                        client_name=client_data["full_name"],
                        invoice_number=invoice_number,
                        pdf_bytes=pdf_bytes,
                        filename=filename,
                        amount=final_amount_float,
                        triggered_by=triggered_by,
                        team_member_email=(
                            practice_data.get("assigned_to")
                            or practice_data.get("created_by")
                        ),
                    )
                    email_sent = True
                    await record_email_result(
                        self.db_pool, audit_row_id, status="sent", provider="brevo",
                    )
                    logger.info(f"Invoice email sent to client {client_data['email']}")
                except Exception as email_error:
                    err_msg = str(email_error)
                    if isinstance(email_error, httpx.HTTPStatusError):
                        err_msg = f"status={email_error.response.status_code} {err_msg}"
                    logger.warning(
                        f"Failed to send invoice email to {client_data['email']}: {err_msg}",
                    )
                    await record_email_result(
                        self.db_pool, audit_row_id, status="failed", provider="brevo",
                        error_message=err_msg,
                    )
                    notify_email_failure_critical(
                        email_type="invoice_client",
                        to_email=client_data["email"],
                        subject=f"Invoice {invoice_number}",
                        practice_id=practice_id,
                        error=err_msg,
                    )
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
            except httpx.HTTPStatusError as notify_error:
                logger.warning(
                    f"Email API returned {notify_error.response.status_code} "
                    f"sending accounting notification: {notify_error}",
                )
            except httpx.HTTPError as notify_error:
                logger.warning(f"Failed to notify accounting: {notify_error}")
            except Exception:
                logger.exception("Unexpected error sending accounting notification")

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
            except GoogleHttpError as drive_error:
                logger.warning(
                    f"Google Drive API error uploading invoice backup: "
                    f"{drive_error.status_code} {drive_error.reason}",
                )
            except OSError as drive_error:
                logger.warning(f"Network error uploading invoice backup to Drive: {drive_error}")
            except Exception:
                logger.exception("Unexpected error uploading invoice backup to Drive")
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

        except (asyncpg.PostgresError, OSError) as error:
            logger.warning(
                f"Invoice automation failed for practice {practice_id} "
                f"({type(error).__name__}): {error}",
            )
            return {"success": False, "error": str(error)}
        except Exception as error:
            logger.exception(f"Unexpected error in invoice automation for practice {practice_id}")
            return {"success": False, "error": str(error)}

    async def _send_invoice_email_to_client(
        self,
        client_email: str,
        client_name: str,
        invoice_number: str,
        pdf_bytes: bytes,
        filename: str,
        amount: float,
        triggered_by: str | None = None,
        team_member_email: str | None = None,
    ) -> bool:
        """Send invoice email to client via internal email API (sender: zantara@balizero.com)."""
        subject = f"Invoice {invoice_number} from Bali Zero"
        body_html = (
            f"{logo_header_html()}"
            f"<p>Dear {client_name},</p>"
            f"<p>Thank you for choosing Bali Zero for your business in Indonesia.</p>"
            f"<p>Please find your invoice attached to this email.</p>"
            f"<p><b>Invoice Details:</b><br>"
            f"Invoice Number: {invoice_number}<br>"
            f"Amount Due: IDR {amount:,.0f}<br>"
            f"Payment Terms: Net 2 days</p>"
            f"<p>Payment can be made via bank transfer to the details provided on the invoice.</p>"
            f"<p>We look forward to serving you!</p>"
            f"<p>Best regards,<br>Zantara — Bali Zero Team</p>"
            f"<hr><small>For support: asya@balizero.com | WhatsApp: +62 821 3107 363</small>"
        )

        cc_emails = list(INVOICE_CC_EMAILS)
        if team_member_email and team_member_email not in cc_emails and team_member_email != client_email:
            cc_emails.append(team_member_email)
        if triggered_by and triggered_by not in cc_emails and triggered_by != client_email:
            cc_emails.append(triggered_by)

        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        payload: dict[str, Any] = {
            "to": client_email,
            "subject": subject,
            "body": body_html,
            "cc": ", ".join(cc_emails),
            "attachments": [{"name": filename, "content": pdf_b64}],
        }
        client = await get_email_client()
        response = await client.post(
            _EMAIL_API_URL,
            headers={"X-API-Key": _EMAIL_API_KEY},
            json=payload,
        )
        response.raise_for_status()

        logger.info(f"Invoice email sent to {client_email} from zantara@ (cc: {cc_emails})")
        return True

    async def _send_accounting_notification(
        self,
        client_data: dict,
        practice_data: dict,
        invoice_number: str,
        pdf_bytes: bytes,
        filename: str,
    ) -> bool:
        """Send notification email to accounting (Asya) via internal email API."""
        subject = f"[TEAM] New Invoice {invoice_number} - {client_data['full_name']}"
        amount = float(practice_data.get("quoted_price", 0))
        body_html = team_email_html(
            title=f"New Invoice {invoice_number}",
            intro=f"Hi Asya — a new invoice has been generated and sent to {client_data['full_name']}. PDF attached.",
            meta_rows=[
                ("Client", client_data["full_name"]),
                ("Email", client_data.get("email") or "—"),
                ("Practice", f"#{practice_data['id']}"),
                ("Amount", f"IDR {amount:,.0f}"),
            ],
            body_html=(
                "<b>Next steps:</b>"
                "<ol style='margin:6px 0 4px 18px;padding:0;'>"
                "<li>Reach out to the client via WhatsApp for payment follow-up</li>"
                "<li>Keep an eye on our bank account</li>"
                "<li>Once payment comes through, update the status to ON PROCESS</li>"
                "</ol>"
            ),
            cta_label="Open practice in CRM",
            cta_url=f"https://kita.balizero.com/process/{practice_data['id']}",
            signature="Zantara CRM",
        )

        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        payload: dict[str, Any] = {
            "to": ACCOUNTING_EMAIL,
            "subject": subject,
            "body": body_html,
            "attachments": [{"name": filename, "content": pdf_b64}],
        }
        client = await get_email_client()
        response = await client.post(
            _EMAIL_API_URL,
            headers={"X-API-Key": _EMAIL_API_KEY},
            json=payload,
        )
        response.raise_for_status()

        logger.info(f"Accounting notification sent to {ACCOUNTING_EMAIL} from zantara@")
        return True

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
            # ── 1. Fetch practice for amount + client_id + discount ───────────
            # Defensive try/except keeps the dual-write working on databases
            # that have not yet applied migration 158.
            try:
                practice_row = await conn.fetchrow(
                    "SELECT client_id, quoted_price, discount_amount FROM practices WHERE id = $1",
                    practice_id,
                )
            except Exception as fetch_exc:
                if getattr(fetch_exc, "sqlstate", None) == "42703":
                    practice_row = await conn.fetchrow(
                        "SELECT client_id, quoted_price FROM practices WHERE id = $1",
                        practice_id,
                    )
                else:
                    raise

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

            # payment_status is NOT reset here: FE ciclo is unpaid→partial→paid
            # (no 'pending' state). Keep whatever value was set before.
            # Pass dict directly — the api pool's jsonb codec encodes once
            # via json.dumps. Double-encoding (calling json.dumps here AND
            # letting the codec re-encode) was the root cause of the
            # discount_log audit trail landing as a JSONB string scalar in
            # production (observed 2026-05-06 on practice_id=390).
            await conn.execute(
                """
                UPDATE practices
                SET documents = $1, updated_at = NOW()
                WHERE id = $2
                """,
                documents,
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

                # amount_idr stores the FINAL total (post-discount) so the
                # AR reports add up to what the client actually owes; the
                # discount itself is mirrored in discount_amount_idr per
                # owner Q4=a (2026-05-06). On legacy databases that still
                # lack discount_amount_idr (no migration 158), fall back to
                # the pre-158 INSERT shape.
                quoted_for_invoice = float(practice_row["quoted_price"] or 0)
                discount_for_invoice = 0.0
                try:
                    raw_disc = practice_row["discount_amount"]
                    if raw_disc is not None:
                        discount_for_invoice = float(raw_disc)
                except (KeyError, TypeError):
                    discount_for_invoice = 0.0
                if discount_for_invoice < 0:
                    discount_for_invoice = 0.0
                if discount_for_invoice > quoted_for_invoice:
                    discount_for_invoice = quoted_for_invoice
                amount_for_invoice = quoted_for_invoice - discount_for_invoice

                try:
                    await conn.execute(
                        """
                        INSERT INTO invoices (
                            practice_id, client_id, invoice_number, invoice_source,
                            amount_idr, discount_amount_idr,
                            drive_file_id, drive_web_link,
                            email_sent_to_client, accounting_notified, generated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (practice_id) DO UPDATE SET
                            invoice_number       = EXCLUDED.invoice_number,
                            invoice_source       = EXCLUDED.invoice_source,
                            amount_idr           = EXCLUDED.amount_idr,
                            discount_amount_idr  = EXCLUDED.discount_amount_idr,
                            drive_file_id        = EXCLUDED.drive_file_id,
                            drive_web_link       = EXCLUDED.drive_web_link,
                            email_sent_to_client = EXCLUDED.email_sent_to_client,
                            accounting_notified  = EXCLUDED.accounting_notified,
                            generated_at         = EXCLUDED.generated_at,
                            updated_at           = NOW()
                        """,
                        practice_id,
                        practice_row["client_id"],
                        invoice_info.get("invoice_number") or None,
                        invoice_info.get("source", "local_pdf"),
                        amount_for_invoice,
                        discount_for_invoice,
                        invoice_info.get("invoice_drive_id") or None,
                        invoice_info.get("invoice_drive_link") or None,
                        bool(invoice_info.get("email_sent", False)),
                        bool(invoice_info.get("accounting_notified", False)),
                        generated_at,
                    )
                except Exception as insert_exc:
                    if getattr(insert_exc, "sqlstate", None) == "42703":
                        await conn.execute(
                            """
                            INSERT INTO invoices (
                                practice_id, client_id, invoice_number, invoice_source,
                                amount_idr, drive_file_id, drive_web_link,
                                email_sent_to_client, accounting_notified, generated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (practice_id) DO UPDATE SET
                                invoice_number       = EXCLUDED.invoice_number,
                                invoice_source       = EXCLUDED.invoice_source,
                                amount_idr           = EXCLUDED.amount_idr,
                                drive_file_id        = EXCLUDED.drive_file_id,
                                drive_web_link       = EXCLUDED.drive_web_link,
                                email_sent_to_client = EXCLUDED.email_sent_to_client,
                                accounting_notified  = EXCLUDED.accounting_notified,
                                generated_at         = EXCLUDED.generated_at,
                                updated_at           = NOW()
                            """,
                            practice_id,
                            practice_row["client_id"],
                            invoice_info.get("invoice_number") or None,
                            invoice_info.get("source", "local_pdf"),
                            amount_for_invoice,
                            invoice_info.get("invoice_drive_id") or None,
                            invoice_info.get("invoice_drive_link") or None,
                            bool(invoice_info.get("email_sent", False)),
                            bool(invoice_info.get("accounting_notified", False)),
                            generated_at,
                        )
                    else:
                        raise

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
