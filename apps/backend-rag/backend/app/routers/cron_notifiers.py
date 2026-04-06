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
         -H "X-API-Key: $NUZANTARA_API_KEY"
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cron/notifiers", tags=["cron-notifiers"])

_API_KEY = os.getenv("NUZANTARA_API_KEY", "")


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

    # Kill switch: check system_settings for approval flag
    async with db_pool.acquire() as conn:
        approved = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key = 'visa_expiry_notifier_enabled'"
        )
    if approved != "true":
        logger.warning("Visa expiry notifier BLOCKED — awaiting owner approval (set visa_expiry_notifier_enabled=true)")
        return {"service": "visa_expiry", "status": "blocked", "reason": "awaiting_owner_approval"}

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


@router.post("/compliance-forecast")
async def run_compliance_forecast(request: Request) -> dict[str, Any]:
    """
    Run the predictive compliance engine and return forecasts with revenue estimates.

    Kill switch: system_settings.compliance_forecast_enabled must be "true".
    Optional query param: ?scan_days=365 (default 365).
    """
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    from backend.services.compliance.predictive_engine import (
        PredictiveComplianceEngine,
        is_engine_enabled,
    )
    from backend.services.pricing.pricing_service import get_pricing_service

    if not await is_engine_enabled(db_pool):
        return {
            "service": "compliance_forecast",
            "status": "disabled",
            "reason": "Set compliance_forecast_enabled=true in system_settings to enable",
        }

    scan_days_raw = request.query_params.get("scan_days", "365")
    try:
        scan_days = max(30, min(int(scan_days_raw), 730))
    except ValueError:
        scan_days = 365

    try:
        pricing_service = get_pricing_service()
        all_prices = pricing_service.get_pricing("all")
    except Exception:
        logger.exception("Failed to load pricing data for compliance forecast")
        return {
            "service": "compliance_forecast",
            "status": "error",
            "reason": "pricing_unavailable",
        }

    engine = PredictiveComplianceEngine(db_pool, all_prices, scan_window_days=scan_days)
    result = await engine.scan()

    # Serialize to JSON-safe dict
    forecasts_out = [
        {
            "client_id": f.client_id,
            "client_name": f.client_name,
            "assigned_to": f.assigned_to,
            "document_type": f.document_type,
            "current_visa_type": f.current_visa_type,
            "expiry_date": f.expiry_date.isoformat(),
            "days_until_expiry": f.days_until_expiry,
            "matched_rule_id": f.matched_rule_id,
            "processing_days": f.processing_days,
            "lead_time_start": f.lead_time_start.isoformat(),
            "recommended_action_by": f.recommended_action_by.isoformat(),
            "days_until_action": f.days_until_action,
            "estimated_revenue_idr": f.estimated_revenue_idr,
            "renewal_pricing_key": f.renewal_pricing_key,
            "priority_score": f.priority_score,
            "urgency_level": f.urgency_level,
            "required_docs": f.required_docs,
            "passport_expires_before_visa": f.passport_expires_before_visa,
            "notes": f.notes,
        }
        for f in result.forecasts
    ]

    return {
        "service": "compliance_forecast",
        "status": "ok",
        "scan_window_days": result.scan_window_days,
        "generated_at": result.generated_at,
        "summary": {
            "total_forecasts": result.summary.total_forecasts,
            "by_urgency": result.summary.by_urgency,
            "total_estimated_revenue_idr": result.summary.total_estimated_revenue_idr,
            "clients_with_active_practice_skipped": (
                result.summary.clients_with_active_practice_skipped
            ),
            "top_revenue_forecasts": [
                {
                    "client_name": f.client_name,
                    "document_type": f.document_type,
                    "expiry_date": f.expiry_date.isoformat(),
                    "estimated_revenue_idr": f.estimated_revenue_idr,
                    "urgency_level": f.urgency_level,
                }
                for f in result.summary.top_revenue_forecasts
            ],
        },
        "forecasts": forecasts_out,
    }


@router.post("/all")
async def run_all_notifiers(request: Request) -> dict[str, Any]:
    """Run all three notifiers in sequence. Single cron endpoint."""
    _verify_api_key(request)
    db_pool = _get_db_pool(request)

    results: dict[str, Any] = {}

    # 1. Visa expiry (with kill switch)
    try:
        async with db_pool.acquire() as conn:
            approved = await conn.fetchval(
                "SELECT value FROM system_settings WHERE key = 'visa_expiry_notifier_enabled'"
            )
        if approved != "true":
            logger.warning("Visa expiry notifier BLOCKED in /all — awaiting owner approval")
            results["visa_expiry"] = {"status": "blocked", "reason": "awaiting_owner_approval"}
        else:
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
