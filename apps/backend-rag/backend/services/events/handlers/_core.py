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
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import asyncpg

from backend.services.bridge.outbox import insert_outbox_event
from backend.services.common.background import spawn

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.services.events.event_bus import EventBus

# ── Deduplication guard ──────────────────────────────────────────────────
# PG triggers fire on every UPDATE, including no-op updates (SET x = x).
# This prevents duplicate processing within a short window.
_recent_events: dict[str, float] = {}
_DEDUP_WINDOW_S = 10  # ignore same event within 10 seconds


def _is_duplicate(event_key: str) -> bool:
    """Check if this event was already processed recently."""
    now = time.monotonic()
    # Prune old entries
    stale = [k for k, t in _recent_events.items() if now - t > _DEDUP_WINDOW_S]
    for k in stale:
        del _recent_events[k]
    if event_key in _recent_events:
        return True
    _recent_events[event_key] = now
    return False


# ── Cross-chain shared context ───────────────────────────────────────────
# In-memory store of recent events so chains can check what already happened.
# Key: "{event_type}:{entity_id}", Value: payload + timestamp.
# Max 200 entries, auto-pruned.
_chain_context: dict[str, dict[str, Any]] = {}
_CHAIN_CONTEXT_MAX = 200


def get_chain_context() -> dict[str, dict[str, Any]]:
    """Read-only access to recent event context for chains."""
    return dict(_chain_context)


def _store_context(event_type: str, entity_id: str | int, payload: dict[str, Any]) -> None:
    """Store event in cross-chain context."""
    key = f"{event_type}:{entity_id}"
    _chain_context[key] = {
        **payload,
        "_stored_at": datetime.now(timezone.utc).isoformat(),
    }
    # Prune if too many
    if len(_chain_context) > _CHAIN_CONTEXT_MAX:
        oldest_keys = sorted(
            _chain_context,
            key=lambda k: _chain_context[k].get("_stored_at", ""),
        )[:50]
        for k in oldest_keys:
            del _chain_context[k]


def register_handlers(
    bus: "EventBus",
    db_pool: asyncpg.Pool,
) -> None:
    """Register all event handlers on the bus.

    Called once at app startup after EventBus.start().
    """
    # ── client.changed ─────────────────────────────────────────────────
    async def on_client_changed(payload: dict[str, Any]) -> None:
        """React to client creation or update.

        Actions:
          - Dedup guard (PG fires on every UPDATE, even no-ops)
          - Invalidate CRM cache
          - Store in cross-chain context
          - On INSERT: create Drive folder + log CRM interaction
        """
        client_id = payload.get("client_id")
        operation = payload.get("operation", "UPDATE")
        email = payload.get("email", "unknown")

        dedup_key = f"client:{client_id}:{operation}"
        if _is_duplicate(dedup_key):
            return

        logger.info(
            f"🔔 Event client.changed: {operation} client_id={client_id} "
            f"email={email}"
        )

        # Invalidate CRM cache
        try:
            from backend.core.cache import invalidate_cache
            await invalidate_cache("zantara:crm_clients_stats:*")
        except Exception as e:
            logger.debug(f"Cache invalidation skipped: {e}")

        # Store in cross-chain context
        _store_context("client.changed", client_id, payload)

        # ── Bridge outbox: notify Pro of CRM client changes ──────────
        try:
            async with db_pool.acquire() as conn:
                if operation == "INSERT":
                    await insert_outbox_event(
                        conn,
                        event_type="crm.client_created",
                        payload={
                            "client_id": client_id,
                            "email": email,
                            "sector": payload.get("sector"),
                        },
                    )
                elif operation == "UPDATE" and "sector" in (payload.get("changed_fields") or []):
                    await insert_outbox_event(
                        conn,
                        event_type="crm.client_sector_changed",
                        payload={
                            "client_id": client_id,
                            "sector": payload.get("sector"),
                            "old_sector": payload.get("old_sector"),
                        },
                    )
        except Exception as e:
            logger.error(f"Bridge outbox write failed for client {client_id}: {e}")

        # On new client: create Drive folder + log interaction
        if operation == "INSERT":
            logger.info(
                f"🆕 New client created: id={client_id}, email={email}"
            )
            # Create Drive folder in background (non-blocking)
            spawn(
                _create_drive_folder(db_pool, client_id),
                name=f"drive_folder_{client_id}",
            )
            # Log CRM interaction
            spawn(
                _log_interaction(
                    db_pool, client_id,
                    "system",
                    "Client created — auto-provisioning started",
                    "internal",
                ),
                name=f"log_interaction_{client_id}",
            )

    # ── practice.status_changed ────────────────────────────────────────
    async def on_practice_status_changed(payload: dict[str, Any]) -> None:
        """React to practice status changes.

        PracticeStatusListener handles M4/M5 emails.
        This handler adds:
          - Cross-chain context (so daily_ops knows what changed)
          - Compliance check on completion
          - Cache invalidation
        """
        practice_id = payload.get("practice_id")
        old_status = payload.get("old_status")
        new_status = payload.get("new_status")
        client_id = payload.get("client_id")

        dedup_key = f"practice:{practice_id}:{old_status}:{new_status}"
        if _is_duplicate(dedup_key):
            return

        logger.info(
            f"🔔 Event practice.status_changed: "
            f"practice_id={practice_id} {old_status}→{new_status}"
        )

        # Invalidate practice cache
        try:
            from backend.core.cache import invalidate_cache
            await invalidate_cache("zantara:crm_practices:*")
        except Exception as e:
            logger.debug(f"Cache invalidation skipped: {e}")

        # Store in cross-chain context
        _store_context("practice.status_changed", practice_id, payload)

        # ── Bridge outbox: notify Pro of practice lifecycle ──────────
        try:
            async with db_pool.acquire() as conn:
                if new_status == "completed":
                    await insert_outbox_event(
                        conn,
                        event_type="crm.practice_completed",
                        payload={
                            "practice_id": practice_id,
                            "client_id": client_id,
                            "completed_at": payload.get("completed_at"),
                        },
                    )
                elif old_status is None and new_status in ("created", "open", "in_progress"):
                    await insert_outbox_event(
                        conn,
                        event_type="crm.practice_created",
                        payload={
                            "practice_id": practice_id,
                            "client_id": client_id,
                            "practice_type": payload.get("practice_type"),
                        },
                    )
        except Exception as e:
            logger.error(f"Bridge outbox write failed for practice {practice_id}: {e}")

        # On completion: check if client has other expiring docs
        if new_status == "completed" and client_id:
            spawn(
                _check_client_expiry_on_completion(db_pool, client_id, practice_id),
                name=f"expiry_check_{client_id}",
            )
            # Predictive engine: mini-scan for this client on completion
            spawn(
                _run_predictive_scan_for_client(db_pool, client_id),
                name=f"predictive_scan_{client_id}",
            )

        # On cancellation: log for analytics
        if new_status == "cancelled":
            spawn(
                _log_interaction(
                    db_pool, client_id,
                    "system",
                    f"Practice #{practice_id} cancelled (was: {old_status})",
                    "internal",
                ),
                name=f"cancel_log_{practice_id}",
            )

    # ── compliance.alert ───────────────────────────────────────────────
    async def on_compliance_alert(payload: dict[str, Any]) -> None:
        """React to compliance alerts.

        Actions:
          - Store in cross-chain context
          - High/critical: send Telegram alert to admin
          - Log CRM interaction for affected client
        """
        alert_id = payload.get("alert_id")
        severity = payload.get("severity", "low")
        message = payload.get("message", "")
        client_id = payload.get("client_id")
        alert_type = payload.get("alert_type", "unknown")

        dedup_key = f"compliance:{alert_id}"
        if _is_duplicate(dedup_key):
            return

        logger.info(
            f"🔔 Event compliance.alert: severity={severity} "
            f"client_id={client_id} type={alert_type}"
        )

        # Store in cross-chain context
        _store_context("compliance.alert", alert_id or client_id, payload)

        # ── Bridge outbox: notify Pro of critical compliance alerts ──
        days = payload.get("days_until_expiry")
        if severity == "critical" and days is not None and days <= 7:
            try:
                async with db_pool.acquire() as conn:
                    await insert_outbox_event(
                        conn,
                        event_type="compliance.critical_alert",
                        payload={
                            "client_id": client_id,
                            "document_type": payload.get("document_type"),
                            "days_until_expiry": payload.get("days_until_expiry"),
                            "expires_at": payload.get("expires_at"),
                        },
                    )
            except Exception as e:
                logger.error(f"Bridge outbox write failed for compliance alert: {e}")

        # High/critical: Telegram alert
        if severity in ("high", "critical"):
            spawn(
                _send_admin_telegram(
                    f"⚠️ Compliance Alert [{severity.upper()}]",
                    f"Client #{client_id}\nType: {alert_type}\n{message[:300]}",
                ),
                name=f"telegram_compliance_{alert_id}",
            )

        # Log in CRM
        if client_id:
            spawn(
                _log_interaction(
                    db_pool, client_id,
                    "compliance",
                    f"[{severity}] {alert_type}: {message[:200]}",
                    "internal",
                ),
                name=f"compliance_log_{client_id}",
            )

    # ── Register all handlers ──────────────────────────────────────────
    bus.subscribe("client.changed", on_client_changed)
    bus.subscribe("practice.status_changed", on_practice_status_changed)
    bus.subscribe("compliance.alert", on_compliance_alert)

    # ── Compliance + intel handlers (2026-04-18 PR) ────────────────────
    try:
        from backend.services.events.handlers.compliance_handlers import HANDLERS as _compliance_handlers
        for event_type, handler in _compliance_handlers.items():
            bus.subscribe(event_type, handler)
    except ImportError as exc:
        logger.warning("compliance_handlers not loaded: %s", exc)

    # ── Partner handlers (2026-04-20) ──────────────────────────────────
    try:
        from backend.app.db import set_pool as _set_pool
        _set_pool(db_pool)
        from backend.services.crm.partners.events import register_partner_handlers
        register_partner_handlers(bus)
    except ImportError as exc:
        logger.warning("partner handlers not loaded: %s", exc)

    logger.info(
        f"✅ EventBus handlers registered: "
        f"{len(bus._subscribers)} event types"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Background action functions — called via asyncio.create_task from handlers
# ═══════════════════════════════════════════════════════════════════════════

async def _create_drive_folder(db_pool: asyncpg.Pool, client_id: int) -> None:
    """Create a Google Drive folder for a new client."""
    try:
        from backend.services.integrations.service_account_drive_service import (
            ServiceAccountDriveService,
        )
        drive_svc = ServiceAccountDriveService()

        # Fetch client name for folder
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT full_name FROM clients WHERE id = $1", client_id,
            )
        if not row:
            return

        client_name = row["full_name"]
        folder_name = f"Individual_{client_name.replace(' ', '_')}"

        # Check if folder already exists (idempotency)
        async with db_pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT drive_folder_id FROM clients WHERE id = $1", client_id,
            )
        if existing:
            logger.debug(f"Drive folder already exists for client {client_id}")
            return

        folder_id = drive_svc.create_folder(folder_name)
        if folder_id:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE clients SET drive_folder_id = $1 WHERE id = $2",
                    folder_id, client_id,
                )
            logger.info(f"📁 Drive folder created for client {client_id}: {folder_id}")
    except Exception as e:
        logger.error(f"Drive folder creation failed for client {client_id}: {e}")


async def _log_interaction(
    db_pool: asyncpg.Pool,
    client_id: int | None,
    interaction_type: str,
    summary: str,
    channel: str,
) -> None:
    """Insert a CRM interaction record."""
    if not client_id:
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO interactions (client_id, type, summary, channel, created_at)
                   VALUES ($1, $2, $3, $4, NOW())""",
                client_id, interaction_type, summary, channel,
            )
    except Exception as e:
        logger.debug(f"Interaction log failed: {e}")


async def _check_client_expiry_on_completion(
    db_pool: asyncpg.Pool, client_id: int, completed_practice_id: int,
) -> None:
    """When a practice completes, check if the client has other expiring documents.

    This replaces the need for a separate cron job to scan all clients —
    we check proactively at the moment of completion.
    """
    try:
        async with db_pool.acquire() as conn:
            expiring = await conn.fetch(
                """SELECT id, practice_type_code, expiry_date,
                          (expiry_date - CURRENT_DATE) AS days_remaining
                   FROM practices
                   WHERE client_id = $1
                     AND id != $2
                     AND status NOT IN ('completed', 'cancelled', 'archived')
                     AND expiry_date IS NOT NULL
                     AND expiry_date - CURRENT_DATE < 90
                   ORDER BY expiry_date""",
                client_id, completed_practice_id,
            )

        if expiring:
            items = ", ".join(
                f"{r['practice_type_code']}(#{r['id']}, {r['days_remaining']}d)"
                for r in expiring
            )
            logger.info(
                f"📋 Client {client_id} has {len(expiring)} expiring items "
                f"after practice #{completed_practice_id} completed: {items}"
            )
            # Log for CRM visibility
            await _log_interaction(
                db_pool, client_id, "system",
                f"Practice #{completed_practice_id} completed. "
                f"Note: {len(expiring)} other items expiring within 90 days: {items}",
                "internal",
            )
    except Exception as e:
        logger.debug(f"Expiry check failed for client {client_id}: {e}")


async def _send_admin_telegram(title: str, message: str) -> None:
    """Send alert to admin via Telegram."""
    try:
        from backend.services.monitoring.alert_service import AlertLevel, AlertService
        svc = AlertService()
        await svc.send_alert(title=title, message=message, level=AlertLevel.WARNING)
    except Exception as e:
        logger.debug(f"Telegram alert failed: {e}")


async def _run_predictive_scan_for_client(
    db_pool: asyncpg.Pool, client_id: int,
) -> None:
    """
    Run the predictive compliance engine for a single client after their
    practice completes. Logs any high-priority forecasts for CRM visibility.

    This is a lightweight scan (90-day window, 1 client) triggered by EventBus.
    It does NOT send notifications — it only logs findings.
    """
    try:
        from backend.services.compliance.predictive_engine import (
            PredictiveComplianceEngine,
            is_engine_enabled,
        )
        from backend.services.pricing.pricing_service import get_pricing_service

        if not await is_engine_enabled(db_pool):
            return

        pricing_service = get_pricing_service()
        all_prices = pricing_service.get_pricing("all")

        # Use a 90-day scan window for post-completion check
        engine = PredictiveComplianceEngine(db_pool, all_prices, scan_window_days=90)
        result = await engine.scan()

        # Filter forecasts for this client only
        client_forecasts = [f for f in result.forecasts if f.client_id == client_id]

        if not client_forecasts:
            return

        top = client_forecasts[0]
        summary_parts = [
            f"{f.document_type}({f.urgency_level}, {f.days_until_expiry}d)"
            for f in client_forecasts
        ]
        await _log_interaction(
            db_pool,
            client_id,
            "compliance",
            f"Predictive scan: {len(client_forecasts)} upcoming renewal(s) — "
            f"{', '.join(summary_parts)}. "
            f"Top priority: {top.matched_rule_id} (score={top.priority_score})",
            "internal",
        )
        logger.info(
            "Predictive scan for client %d: %d forecast(s), top=%s score=%.1f",
            client_id,
            len(client_forecasts),
            top.matched_rule_id,
            top.priority_score,
        )
    except Exception as e:
        logger.debug(f"Predictive scan failed for client {client_id}: {e}")
