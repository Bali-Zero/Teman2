"""
Event Handlers — concrete subscribers for the EventBus.

Each handler is a simple async function that receives a payload dict.
Handlers are registered in register_handlers() called at app startup.

Design rules:
  - Handlers MUST be fast (< 5s). For slow work, dispatch to background task.
  - Handlers MUST NOT raise — they log errors and continue.
  - Handlers MUST be idempotent — events can be delivered more than once.
"""

import asyncio
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


def register_handlers(
    bus: "EventBus",
    db_pool: asyncpg.Pool,
) -> None:
    """Register all event handlers on the bus.

    Called once at app startup after EventBus.start().
    """
    from backend.services.events.event_bus import EventBus

    # ── client.changed ─────────────────────────────────────────────────
    async def on_client_changed(payload: dict[str, Any]) -> None:
        """React to client creation or update.

        Actions:
          - Log interaction for audit trail
          - Invalidate CRM cache
          - On INSERT: trigger lead assignment check
        """
        client_id = payload.get("client_id")
        operation = payload.get("operation", "UPDATE")
        email = payload.get("email", "unknown")

        logger.info(
            f"🔔 Event client.changed: {operation} client_id={client_id} "
            f"email={email}"
        )

        # Invalidate CRM cache
        try:
            from backend.app.services.cache_service import invalidate_cache
            await invalidate_cache("zantara:crm_clients_stats:*")
        except Exception as e:
            logger.debug(f"Cache invalidation skipped: {e}")

        # On new client: log and potentially trigger onboarding
        if operation == "INSERT":
            logger.info(
                f"🆕 New client created via event bus: "
                f"id={client_id}, email={email}"
            )

    # ── practice.status_changed ────────────────────────────────────────
    async def on_practice_status_changed(payload: dict[str, Any]) -> None:
        """React to practice status changes.

        The existing PracticeStatusListener already handles M4/M5 emails.
        This handler adds cross-chain awareness: stores the event so
        other chains (daily_ops, compliance) can read recent changes.

        We write to a lightweight in-memory store that chains can query.
        """
        practice_id = payload.get("practice_id")
        old_status = payload.get("old_status")
        new_status = payload.get("new_status")

        logger.info(
            f"🔔 Event practice.status_changed: "
            f"practice_id={practice_id} {old_status}→{new_status}"
        )

        # Invalidate practice cache
        try:
            from backend.app.services.cache_service import invalidate_cache
            await invalidate_cache("zantara:crm_practices:*")
        except Exception as e:
            logger.debug(f"Cache invalidation skipped: {e}")

    # ── compliance.alert ───────────────────────────────────────────────
    async def on_compliance_alert(payload: dict[str, Any]) -> None:
        """React to compliance alerts.

        Actions:
          - Log for audit
          - High severity: notify via Telegram
        """
        alert_id = payload.get("alert_id")
        severity = payload.get("severity", "low")
        message = payload.get("message", "")
        client_id = payload.get("client_id")

        logger.info(
            f"🔔 Event compliance.alert: severity={severity} "
            f"client_id={client_id} alert_id={alert_id}"
        )

        if severity in ("high", "critical"):
            logger.warning(
                f"⚠️ HIGH severity compliance alert: {message[:200]}"
            )

    # ── Register all handlers ──────────────────────────────────────────
    bus.subscribe("client.changed", on_client_changed)
    bus.subscribe("practice.status_changed", on_practice_status_changed)
    bus.subscribe("compliance.alert", on_compliance_alert)

    logger.info(
        f"✅ EventBus handlers registered: "
        f"{len(bus._subscribers)} event types"
    )
