"""Append-only journal + transactional outbox writers over `garuda_order_*`.

Both writes MUST happen inside the caller's transaction alongside the
aggregate state write (SM-G07: "appends an immutable journal event in the
same transaction... A transactional outbox carries customer email and
downstream work"). This module never opens its own transaction — it always
takes a `conn` that is already inside one.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

import asyncpg


def new_opaque_id(prefix: str) -> str:
    """>=128 effective random bits, URL-safe, matching SM-G02's shape."""

    return f"{prefix}_{secrets.token_urlsafe(16)}"


async def append_event(
    conn: asyncpg.Connection,
    *,
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    transition_id: str,
    customer_visible: bool,
    idempotency_key_digest: bytes | None = None,
    canonical_payload_digest: bytes | None = None,
    detail: dict[str, Any] | None = None,
) -> str:
    event_id = new_opaque_id("evt")
    await conn.execute(
        """
        INSERT INTO garuda_order_journal
            (event_id, event_name, aggregate_type, aggregate_id, transition_id,
             idempotency_key_digest, canonical_payload_digest, customer_visible, detail)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
        """,
        event_id,
        event_name,
        aggregate_type,
        aggregate_id,
        transition_id,
        idempotency_key_digest,
        canonical_payload_digest,
        customer_visible,
        json.dumps(detail or {}, default=str),
    )
    return event_id


async def enqueue_outbox(
    conn: asyncpg.Connection,
    *,
    order_id: str,
    journal_event_id: str,
    job_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """UNIQUE(journal_event_id, job_type) makes "email once" structural —
    a retry of the same journal append can call this again for free."""

    await conn.execute(
        """
        INSERT INTO garuda_order_outbox (order_id, journal_event_id, job_type, payload)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (journal_event_id, job_type) DO NOTHING
        """,
        order_id,
        journal_event_id,
        job_type,
        json.dumps(payload or {}, default=str),
    )


__all__ = ["append_event", "enqueue_outbox", "new_opaque_id"]
