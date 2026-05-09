"""
EventBus subscriber for the CRM Partners module.

Subscribes to ``practice.status_changed`` (PG channel ``practice_changed``
aliased in event_bus.PG_CHANNEL_MAP).  When a process transitions to
``completed``, delegates accrual to :class:`CommissionEngine` and publishes
``partner_commission_changed`` durably via ``outbox.publish`` on success.

Channel rename 2026-05-09 (everyone-hears-everything wave 2): the legacy
``partner.commission_changed`` channel name failed ``validate_channel``
(dotted name regex-rejected) and was therefore left out of phase-2 outbox
durability. Renamed to ``partner_commission_changed`` (single underscore)
to satisfy the regex and routed through the same outbox.publish path used
by the rest of PG_CHANNEL_MAP.

Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 6
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.app.db import get_pool
from backend.services.crm.partners.commission_engine import CommissionEngine
from backend.services.events.outbox import publish as outbox_publish

if TYPE_CHECKING:
    from backend.services.events.event_bus import EventBus

logger = logging.getLogger(__name__)

PARTNER_COMMISSION_CHANGED = "partner_commission_changed"


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
    practice_id_raw = payload.get("practice_id")

    if new_status != "completed" or not practice_id_raw:
        return

    try:
        pid = int(practice_id_raw) if not isinstance(practice_id_raw, int) else practice_id_raw
    except (ValueError, TypeError):
        logger.warning(
            "handle_practice_status_changed: bad practice_id %r", practice_id_raw
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
    """Emit a ``partner_commission_changed`` notification durably via Outbox.

    Writes to ``events_outbox`` first, then ``pg_notify`` with ``_outbox_id``
    injected — same contract as the other PG_CHANNEL_MAP channels post
    migration 146. Payload schema preserved (partner_id, commission_id, type).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await outbox_publish(
            conn,
            PARTNER_COMMISSION_CHANGED,
            {
                "partner_id": str(partner_id),
                "commission_id": str(commission_id),
                "type": kind,
            },
        )
    logger.info(
        "Published partner_commission_changed: %s (%s)", commission_id, kind
    )


def register_partner_handlers(bus: EventBus) -> None:
    """Subscribe partner-module handlers to the EventBus."""
    bus.subscribe("practice.status_changed", handle_practice_status_changed)
    logger.info("Partner handlers registered on practice.status_changed")
