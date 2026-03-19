"""Test Invoice automation with debug - public endpoint."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/test/trigger-sending-invoice-debug")
async def test_trigger_sending_invoice_debug(practice_id: int = 47):
    """Debug version of sending invoice trigger."""
    import traceback

    import asyncpg

    db_url = os.environ.get("DATABASE_URL")

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        # Step 1: Fetch data
        practice_row = await pool.fetchrow(
            """
            SELECT p.*, c.google_drive_folder_id, pt.code as practice_type_code
            FROM practices p
            LEFT JOIN clients c ON p.client_id = c.id
            LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE p.id = $1
            """,
            practice_id,
        )

        if not practice_row:
            return {"error": "Practice not found"}

        client_row = await pool.fetchrow(
            "SELECT * FROM clients WHERE id = $1", practice_row["client_id"]
        )

        await pool.close()

        # Test Invoice Generator
        from backend.services.invoicing.invoice_generator import InvoiceGenerator

        gen = InvoiceGenerator()
        invoice_number = gen.generate_invoice_number(practice_id)

        # Test PDF generation
        try:
            pdf_bytes = gen.generate(
                practice_id=practice_id,
                client_name=client_row["full_name"],
                client_email=client_row.get("email"),
                client_phone=client_row.get("phone"),
                practice_type=practice_row.get("practice_type_code", "SERVICE"),
                quoted_price=float(practice_row.get("quoted_price", 0)),
            )
        except Exception as e:
            return {
                "error": "PDF generation failed",
                "details": str(e),
                "traceback": traceback.format_exc(),
            }

        # Test Zoho Email upload
        from backend.services.integrations.zoho_email_service import ZohoEmailService

        email_service = ZohoEmailService(pool=None)

        SYSTEM_EMAIL_USER_ID = "7dfe56b2-ff63-4d40-b78b-90c018127a02"

        try:
            attachment = await email_service.upload_attachment(
                user_id=SYSTEM_EMAIL_USER_ID,
                filename=f"Invoice_{invoice_number}.pdf",
                content=pdf_bytes,
                content_type="application/pdf",
            )
            upload_success = True
        except Exception as e:
            return {
                "error": "Upload failed",
                "details": str(e),
                "traceback": traceback.format_exc(),
            }

        # Test sending email
        try:
            await email_service.send_email(
                user_id=SYSTEM_EMAIL_USER_ID,
                to=[client_row["email"]],
                subject=f"Invoice {invoice_number}",
                content="Test invoice email",
                attachments=[attachment],
            )
            send_success = True
        except Exception as e:
            return {"error": "Send failed", "details": str(e), "traceback": traceback.format_exc()}

        return {
            "success": True,
            "invoice_number": invoice_number,
            "pdf_size": len(pdf_bytes),
            "attachment": attachment,
            "upload_success": upload_success,
            "send_success": send_success,
        }

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}
