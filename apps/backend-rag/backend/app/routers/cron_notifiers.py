"""
Cron Notifiers Router

Exposes POST endpoints for the three daily notification jobs:
1. Visa/KITAS/Passport expiry alerts → team leaders + zero@
2. Unpaid invoice reminders → asya@
3. Stale practice alerts → team leaders + zero@

All endpoints are API-key authenticated (same key as MCP/OpenClaw).
Designed to be called from Air cron or OpenClaw scheduler.

Usage:
    curl -X POST https://nuzantara-rag.fly.dev/api/cron/notifiers/all \
         -H "X-API-Key: REDACTED-ROTATED-KEY"
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cron/notifiers", tags=["cron-notifiers"])

_API_KEY = os.getenv("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")


def _verify_api_key(request: Request) -> None:
    """Verify API key from header."""
    key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _get_db_pool(request: Request) -> Any:
    """Get database pool from app state."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool not available")
    return pool


@router.post("/visa-expiry")
async def run_visa_expiry_notifier(request: Request) -> dict[str, Any]:
    """Check visa/KITAS/passport expiry and email team leaders."""
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    from backend.services.compliance.visa_expiry_team_notifier import VisaExpiryTeamNotifier

    notifier = VisaExpiryTeamNotifier(db_pool)
    result = await notifier.check_and_notify()
    logger.info(f"Visa expiry notifier: {result}")
    return {"service": "visa_expiry", **result}


@router.post("/unpaid-invoices")
async def run_unpaid_invoice_notifier(request: Request) -> dict[str, Any]:
    """Check invoices unpaid for 7+ days and remind Asya."""
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    from backend.services.invoicing.unpaid_invoice_notifier import UnpaidInvoiceNotifier

    notifier = UnpaidInvoiceNotifier(db_pool)
    result = await notifier.check_and_notify()
    logger.info(f"Unpaid invoice notifier: {result}")
    return {"service": "unpaid_invoices", **result}


@router.post("/stale-practices")
async def run_stale_practice_notifier(request: Request) -> dict[str, Any]:
    """Check practices with no activity for 7+ days and alert team leaders."""
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    from backend.services.crm.stale_practice_notifier import StalePracticeNotifier

    notifier = StalePracticeNotifier(db_pool)
    result = await notifier.check_and_notify()
    logger.info(f"Stale practice notifier: {result}")
    return {"service": "stale_practices", **result}


@router.post("/welcome-pending")
async def run_welcome_pending(request: Request) -> dict[str, Any]:
    """Process pending welcome emails whose 30-min delay has elapsed. Called every 15 min from Air cron."""
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    from backend.services.crm.welcome.welcome_email_service import process_pending_welcome_emails

    result = await process_pending_welcome_emails(db_pool)
    logger.info(f"Welcome pending processor: {result}")
    return {"service": "welcome_pending", **result}


@router.post("/birthday")
async def run_birthday_notifier(request: Request) -> dict[str, Any]:
    """Send birthday emails to clients with today's birthday. Called daily from Air cron."""
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    from backend.services.crm.birthday_notifier_service import run_birthday_notifier_task

    result = await run_birthday_notifier_task(db_pool)
    logger.info(f"Birthday notifier: {result}")
    return {"service": "birthday", **result}


@router.post("/all")
async def run_all_notifiers(request: Request) -> dict[str, Any]:
    """Run all three notifiers in sequence. Single cron endpoint."""
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    results: dict[str, Any] = {}

    # 1. Visa expiry
    try:
        from backend.services.compliance.visa_expiry_team_notifier import VisaExpiryTeamNotifier

        notifier = VisaExpiryTeamNotifier(db_pool)
        results["visa_expiry"] = await notifier.check_and_notify()
    except Exception as e:
        logger.error(f"Visa expiry notifier failed: {e}", exc_info=True)
        results["visa_expiry"] = {"error": str(e)}

    # 2. Unpaid invoices
    try:
        from backend.services.invoicing.unpaid_invoice_notifier import UnpaidInvoiceNotifier

        notifier = UnpaidInvoiceNotifier(db_pool)
        results["unpaid_invoices"] = await notifier.check_and_notify()
    except Exception as e:
        logger.error(f"Unpaid invoice notifier failed: {e}", exc_info=True)
        results["unpaid_invoices"] = {"error": str(e)}

    # 3. Stale practices
    try:
        from backend.services.crm.stale_practice_notifier import StalePracticeNotifier

        notifier = StalePracticeNotifier(db_pool)
        results["stale_practices"] = await notifier.check_and_notify()
    except Exception as e:
        logger.error(f"Stale practice notifier failed: {e}", exc_info=True)
        results["stale_practices"] = {"error": str(e)}

    logger.info(f"All notifiers completed: {results}")
    return results
