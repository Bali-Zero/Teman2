"""OP-04 reconciliation job — checkout-expiry sweep.

STATE-MACHINE.md OP-04 requires "reconciliation confirms no accepted
payment", not "our clock says the checkout window passed". This job finds
orders whose checkout window has elapsed and are still `awaiting_payment`,
asks the PROVIDER (never our own clock alone) to confirm no charge landed,
and only then commits OP-04. An order the provider says WAS paid is left
alone — the webhook either already reconciled it (rare race) or will
shortly; forcing it here would race a real payment.

Intended cadence: a scheduled job, not a request-path call. Bounded by
`limit` so a large backlog cannot make one run unbounded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg

from backend.services.garuda_orders.repository import GarudaOrderRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReconciliationSummary:
    candidates: int
    expired: int
    left_for_webhook: int


async def reconcile_expired_checkouts(
    pool: asyncpg.Pool,
    repository: GarudaOrderRepository,
    *,
    limit: int = 200,
) -> ReconciliationSummary:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT order_id, provider_session_id
              FROM garuda_orders
             WHERE state = 'awaiting_payment'
               AND checkout_expires_at IS NOT NULL
               AND checkout_expires_at < $1
               AND provider_session_id IS NOT NULL
             ORDER BY checkout_expires_at
             LIMIT $2
            """,
            datetime.now(UTC),
            limit,
        )

    expired = 0
    left_for_webhook = 0
    for row in rows:
        try:
            did_expire = await repository.expire_if_unpaid(
                order_id=row["order_id"], provider_session_id=row["provider_session_id"]
            )
        except Exception:
            logger.exception(
                "garuda_orders reconciliation: failed to check order %s", row["order_id"]
            )
            continue
        if did_expire:
            expired += 1
        else:
            left_for_webhook += 1

    return ReconciliationSummary(
        candidates=len(rows), expired=expired, left_for_webhook=left_for_webhook
    )


__all__ = ["ReconciliationSummary", "reconcile_expired_checkouts"]
