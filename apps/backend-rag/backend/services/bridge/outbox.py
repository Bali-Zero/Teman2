"""
Bridge outbox helper.

The outbox accumulates events that the Pro will pull via
GET /api/bridge/events?after_id=<cursor>.

Used by EventBus handlers (handlers.py) and the RAG low-confidence trigger.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


# Whitelisted event types — anything else is rejected to keep the contract tight.
ALLOWED_TYPES: frozenset[str] = frozenset({
    # Phase 1
    "crm.client_created",
    "crm.client_sector_changed",
    "crm.practice_completed",
    "crm.practice_created",
    # Phase 2 (entries pre-allowed so Phase 2 doesn't need a migration)
    "compliance.critical_alert",
    "rag.low_confidence",
})


async def insert_outbox_event(
    conn: asyncpg.Connection,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    """Insert an event into bridge_outbox. Returns the new BIGSERIAL id.

    Raises ValueError if event_type is not in ALLOWED_TYPES.
    """
    if event_type not in ALLOWED_TYPES:
        raise ValueError(
            f"event_type {event_type!r} not in ALLOWED_TYPES "
            f"({sorted(ALLOWED_TYPES)})"
        )

    row = await conn.fetchrow(
        "INSERT INTO bridge_outbox (type, payload) "
        "VALUES ($1, $2::jsonb) RETURNING id",
        event_type,
        json.dumps(payload, ensure_ascii=False),
    )
    new_id = int(row["id"])
    logger.debug("Inserted outbox event id=%d type=%s", new_id, event_type)
    return new_id


async def fetch_outbox_events(
    conn: asyncpg.Connection,
    after_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch events with id > after_id, ordered by id, capped at limit.

    Returns list of dicts with keys: id, type, payload, created_at (str).
    """
    rows = await conn.fetch(
        "SELECT id, type, payload, created_at "
        "FROM bridge_outbox "
        "WHERE id > $1 "
        "ORDER BY id ASC "
        "LIMIT $2",
        int(after_id),
        int(limit),
    )
    return [
        {
            "id": int(r["id"]),
            "type": r["type"],
            "payload": r["payload"],  # asyncpg auto-decodes JSONB
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
