"""Idempotency cache for GARUDA VOA magic-link customer commands
(`requestMagicLink` issue, `exchangeMagicLink` exchange).

Same scoped-identity + canonical-payload shape as
`backend.services.garuda_orders.idempotency` (L3's `garuda_order_idempotency`)
-- reused rather than reinvented (products/garuda-voa/L4-CONTINUATION.md:
"L3 already solved this shape ... reuse that pattern rather than inventing
a third"). `scoped_key_sha256` / `canonical_payload_sha256` / `IdempotencyConflict`
are imported from there unchanged -- they are pure, table-agnostic hash
helpers. Only `reserve`/`complete` are new here, against
`garuda_magic_link_idempotency` (migration 285), because that table has no
`order_id`-equivalent column: neither magic-link operation's cached response
names a persistent resource id a replay would need to resume -- `issue` is
always an empty 202, and `exchange`'s cached body carries only the
non-secret `ExchangeOutcome` fields (never a raw token or session secret).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import asyncpg

from backend.services.garuda_orders.idempotency import (
    IdempotencyConflict,
    canonical_payload_sha256,
    scoped_key_sha256,
)

__all__ = [
    "IdempotencyConflict",
    "ReservationOutcome",
    "canonical_payload_sha256",
    "complete",
    "reserve",
    "scoped_key_sha256",
]


@dataclass(frozen=True, slots=True)
class ReservationOutcome:
    replayed: bool
    """True: a COMPLETED prior attempt exists -- return its cached response,
    never touch the token table or mint a second session for this key."""
    response_status: int | None
    response_body: dict[str, Any] | None


async def reserve(
    conn: asyncpg.Connection,
    *,
    key_sha256: bytes,
    payload_sha256: bytes,
) -> ReservationOutcome:
    """Insert-or-inspect. Raises `IdempotencyConflict` on a payload mismatch.

    Must be called inside the SAME transaction that performs the command's
    actual side effect (token INSERT / atomic token consumption) -- a crash
    between this call and that side effect rolls both back together, so
    there is no partial-reservation state to resume, unlike L3's
    order-creation flow (which spans an external payment-provider call and
    therefore does need a resume path).
    """
    inserted = await conn.fetchrow(
        """
        INSERT INTO garuda_magic_link_idempotency (key_sha256, canonical_payload_sha256)
        VALUES ($1, $2)
        ON CONFLICT (key_sha256) DO NOTHING
        RETURNING key_sha256
        """,
        key_sha256,
        payload_sha256,
    )
    if inserted is not None:
        return ReservationOutcome(replayed=False, response_status=None, response_body=None)

    existing = await conn.fetchrow(
        """
        SELECT canonical_payload_sha256, response_status, response_body, completed_at
          FROM garuda_magic_link_idempotency
         WHERE key_sha256 = $1
        """,
        key_sha256,
    )
    if existing is None:  # pragma: no cover - row raced away by its own expiry cleanup
        return ReservationOutcome(replayed=False, response_status=None, response_body=None)
    if bytes(existing["canonical_payload_sha256"]) != payload_sha256:
        raise IdempotencyConflict("Idempotency-Key bound to a different payload")
    if existing["completed_at"] is None:
        return ReservationOutcome(replayed=False, response_status=None, response_body=None)
    body = existing["response_body"]
    if isinstance(body, str):
        body = json.loads(body)
    return ReservationOutcome(
        replayed=True,
        response_status=existing["response_status"],
        response_body=body,
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
        UPDATE garuda_magic_link_idempotency
           SET response_status = $2, response_body = $3, completed_at = statement_timestamp()
         WHERE key_sha256 = $1
        """,
        key_sha256,
        response_status,
        json.dumps(response_body, default=str),
    )
