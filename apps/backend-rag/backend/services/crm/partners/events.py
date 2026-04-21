"""
EventBus subscriber for the CRM Partners module.

Subscribes to ``practice.status_changed`` (PG channel ``practice_changed``
aliased in event_bus.PG_CHANNEL_MAP).  When a process transitions to
``completed``, delegates accrual to :class:`CommissionEngine` and publishes
``partner.commission_changed`` via ``pg_notify`` on success.

Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 6
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.app.db import get_pool
from backend.services.crm.partners.commission_engine import CommissionEngine

if TYPE_CHECKING:
    from backend.services.events.event_bus import EventBus

logger = logging.getLogger(__name__)

PARTNER_COMMISSION_CHANGED = "partner.commission_changed"


async def handle_practice_status_changed(payload: dict[str, Any]) -> None:
    """Handler for ``practice.status_changed`` events.

    Triggers commission accrual when a practice flips to ``completed``.
    Payment status is re-verified inside
    :meth:`CommissionEngine.accrue_from_practice` by querying the practice row
    directly — the event payload may not carry ``payment_status``.

    Early-exit conditions (no DB access):
    - ``new_status`` != ``"completed"``
    - ``practice_id`` is absent or falsy
    - ``practice_id`` cannot be parsed as a UUID
    """
    new_status = payload.get("new_status")
    practice_id = payload.get("practice_id")

    if new_status != "completed" or not practice_id:
        return

    try:
        pid = UUID(practice_id) if isinstance(practice_id, str) else practice_id
    except (ValueError, TypeError):
        logger.warning(
            "handle_practice_status_changed: bad practice_id %r", practice_id
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        engine = CommissionEngine(conn)
        cid = await engine.accrue_from_practice(pid)
        if cid is None:
            return

        # Read partner_id for the notification payload
        row = await conn.fetchrow(
            "SELECT partner_id FROM partner_commissions WHERE id = $1", cid
        )
        if row is None:
            return
        partner_id = row["partner_id"]

    await _publish_changed(partner_id, cid, kind="accrued")


async def _publish_changed(
    partner_id: UUID,
    commission_id: UUID,
    *,
    kind: str,
) -> None:
    """Emit a ``partner.commission_changed`` notification via PostgreSQL NOTIFY.

    Uses parameterised ``pg_notify($1, $2)`` — NOT string-interpolated NOTIFY —
    to avoid SQL injection on malformed UUIDs or unexpected ``kind`` values.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        notification_payload = json.dumps(
            {
                "partner_id": str(partner_id),
                "commission_id": str(commission_id),
                "type": kind,
            }
        )
        # pg_notify with parameters — injection-safe
        await conn.execute(
            "SELECT pg_notify($1, $2)",
            PARTNER_COMMISSION_CHANGED,
            notification_payload,
        )
    logger.info(
        "Published partner.commission_changed: %s (%s)", commission_id, kind
    )


def register_partner_handlers(bus: "EventBus") -> None:
    """Subscribe partner-module handlers to the EventBus."""
    bus.subscribe("practice.status_changed", handle_practice_status_changed)
    logger.info("Partner handlers registered on practice.status_changed")
