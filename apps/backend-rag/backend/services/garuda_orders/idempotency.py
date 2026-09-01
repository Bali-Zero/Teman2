"""Customer-command idempotency over `garuda_order_idempotency`.

Scoped identity = actor + operation + raw Idempotency-Key header (never
stored raw — only its SHA-256, same discipline as 262_visa_evaluate_
idempotency.sql). Canonical-payload digest distinguishes an exact replay
(same key, same body -> return committed result) from a conflict (same
key, different body -> IDEMPOTENCY_CONFLICT, OP-F06).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import asyncpg


def scoped_key_sha256(*, actor: str, operation: str, raw_key: str) -> bytes:
    identity = f"{actor}\x1f{operation}\x1f{raw_key}".encode()
    return hashlib.sha256(identity).digest()


def canonical_payload_sha256(payload: dict[str, Any]) -> bytes:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).digest()


class IdempotencyConflict(Exception):
    """OP-F06: same key, different canonical payload."""


@dataclass(frozen=True, slots=True)
class ReservationOutcome:
    replayed: bool
    """True: a COMPLETED prior attempt exists — return its cached response,
    do not touch the provider or the aggregate again."""
    order_id: str | None
    """Set only when a prior (possibly crashed) attempt already created the
    order row before this reservation completed — the resume path."""
    response_status: int | None
    response_body: dict[str, Any] | None


async def reserve(
    conn: asyncpg.Connection,
    *,
    key_sha256: bytes,
    payload_sha256: bytes,
) -> ReservationOutcome:
    """Insert-or-inspect. Raises `IdempotencyConflict` on a payload mismatch."""

    inserted = await conn.fetchrow(
        """
        INSERT INTO garuda_order_idempotency (key_sha256, canonical_payload_sha256)
        VALUES ($1, $2)
        ON CONFLICT (key_sha256) DO NOTHING
        RETURNING key_sha256
        """,
        key_sha256,
        payload_sha256,
    )
    if inserted is not None:
        return ReservationOutcome(
            replayed=False, order_id=None, response_status=None, response_body=None
        )

    existing = await conn.fetchrow(
        """
        SELECT canonical_payload_sha256, order_id, response_status, response_body, completed_at
          FROM garuda_order_idempotency
         WHERE key_sha256 = $1
        """,
        key_sha256,
    )
    if existing is None:  # pragma: no cover - row raced away by its own expiry cleanup
        return ReservationOutcome(
            replayed=False, order_id=None, response_status=None, response_body=None
        )
    if bytes(existing["canonical_payload_sha256"]) != payload_sha256:
        raise IdempotencyConflict("Idempotency-Key bound to a different payload")
    if existing["completed_at"] is None:
        # A prior attempt reserved this key but never completed (crash, or
        # still in flight). Resume from wherever it got to, keyed by the
        # order_id it may already have recorded.
        return ReservationOutcome(
            replayed=False,
            order_id=existing["order_id"],
            response_status=None,
            response_body=None,
        )
    body = existing["response_body"]
    if isinstance(body, str):
        body = json.loads(body)
    return ReservationOutcome(
        replayed=True,
        order_id=existing["order_id"],
        response_status=existing["response_status"],
        response_body=body,
    )


async def bind_order_id(conn: asyncpg.Connection, *, key_sha256: bytes, order_id: str) -> None:
    """Record the order_id as soon as it exists, before any external call."""

    await conn.execute(
        "UPDATE garuda_order_idempotency SET order_id = $2 WHERE key_sha256 = $1 AND order_id IS NULL",
        key_sha256,
        order_id,
    )


async def complete(
    conn: asyncpg.Connection,
    *,
    key_sha256: bytes,
    response_status: int,
    response_body: dict[str, Any],
) -> None:
    await conn.execute(
        """
        UPDATE garuda_order_idempotency
           SET response_status = $2, response_body = $3, completed_at = statement_timestamp()
         WHERE key_sha256 = $1
        """,
        key_sha256,
        response_status,
        response_body,
    )


__all__ = [
    "IdempotencyConflict",
    "ReservationOutcome",
    "bind_order_id",
    "canonical_payload_sha256",
    "complete",
    "reserve",
    "scoped_key_sha256",
]
