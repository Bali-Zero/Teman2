"""Test Invoice automation - public endpoint."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/test/trigger-sending-invoice")
async def test_trigger_sending_invoice(practice_id: int = 1):
    """Simulate status change to 'sending_invoice' and trigger automation."""
    import asyncpg

    from backend.services.invoicing.invoice_service import InvoiceAutomationService

    db_url = os.environ.get("DATABASE_URL")

    try:
        # Create temp pool
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        service = InvoiceAutomationService(pool)

        # Trigger the automation
        result = await service.trigger_on_sending_invoice(
            practice_id=practice_id, triggered_by="test@balizero.com"
        )

        await pool.close()

        return {
            "success": result.get("success"),
            "invoice_number": result.get("invoice_number"),
            "zoho_invoice_id": result.get("zoho_invoice_id"),
            "email_sent": result.get("email_sent"),
            "accounting_notified": result.get("accounting_notified"),
            "drive_file_id": result.get("drive_file_id"),
            "error": result.get("error"),
        }
    except Exception as e:
        import traceback

        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@router.get("/test/trigger-on-process")
async def test_trigger_on_process(practice_id: int = 1):
    """Simulate status change to 'on_process' and trigger automation."""
    import asyncpg

    from backend.services.crm.process_automation_service import ProcessAutomationService

    db_url = os.environ.get("DATABASE_URL")

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        service = ProcessAutomationService(pool)

        result = await service.trigger_on_process_start(
            practice_id=practice_id, triggered_by="asya@balizero.com"
        )

        await pool.close()

        return {
            "success": result.get("success"),
            "client_notified": result.get("client_notified"),
            "team_leader_notified": result.get("team_leader_notified"),
            "error": result.get("error"),
        }
    except Exception as e:
        import traceback

        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@router.get("/test/trigger-completed")
async def test_trigger_completed(practice_id: int = 1):
    """Simulate status change to 'completed' and trigger automation."""
    import asyncpg

    from backend.services.crm.completed_process_service import CompletedProcessService

    db_url = os.environ.get("DATABASE_URL")

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        service = CompletedProcessService(pool)

        result = await service.trigger_on_completed(
            practice_id=practice_id, triggered_by="team@balizero.com"
        )

        await pool.close()

        return {
            "success": result.get("success"),
            "client_notified": result.get("client_notified"),
            "team_notified": result.get("team_notified"),
            "documents_uploaded": result.get("documents_uploaded"),
            "error": result.get("error"),
        }
    except Exception as e:
        import traceback

        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
