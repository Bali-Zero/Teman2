"""OP-04 reconciliation job — checkout-expiry sweep.

STATE-MACHINE.md OP-04 requires "reconciliation confirms no accepted
payment", not "our clock says the checkout window passed". This job finds
orders whose checkout window has elapsed and are still `awaiting_payment`,
asks the PROVIDER (never our own clock alone) to confirm no charge landed,
and only then commits OP-04. An order the provider says WAS paid keeps its
state — forcing `paid` here would race a real payment, and OP-F01 forbids
any non-webhook writer from making that transition anyway.

CORRECTED 2026-09-19. This paragraph used to end "the webhook either
already reconciled it (rare race) or will shortly", and on that premise the
paid branch did nothing but log. The premise is false, measured in
production: an order paid on 2026-09-16 was still `awaiting_payment` on
2026-09-19 with `garuda_payment_inbox` empty — no webhook had EVER arrived,
because a callback URL that is not registered with the provider looks
exactly like a customer who never paid. "Will shortly" has no deadline and
nothing was watching it, so the wait was unbounded and silent. The paid
branch now opens a late case and pages (OP-F08, `repository.py::
_open_late_case_from_reconciliation`); it still does not touch `state`.

An order whose late case is OPEN, or that staff have already RESOLVED, is
no longer a candidate: it keeps `awaiting_payment` by design (OP-F01), its
checkout window stays elapsed forever, and without this filter every tick
would re-ask the provider about it for the rest of its life — an unbounded
stream of provider calls, and with `limit` rows ordered oldest-first,
enough resolved orders would eventually crowd out real candidates. The
same three predicates guard the WRITE in
`repository.py::_open_late_case_from_reconciliation`; this one keeps the
sweep from paying to rediscover what it already knows (Kimi `k3`,
cross-family review).

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
    late_cases_opened: int
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
               AND late_case_open = FALSE
               AND late_case_resolution IS NULL
             ORDER BY checkout_expires_at
             LIMIT $2
            """,
            datetime.now(UTC),
            limit,
        )

    expired = 0
    late_cases_opened = 0
    left_for_webhook = 0
    for row in rows:
        try:
            outcome = await repository.expire_if_unpaid(
                order_id=row["order_id"], provider_session_id=row["provider_session_id"]
            )
        except Exception:
            logger.exception(
                "garuda_orders reconciliation: failed to check order %s", row["order_id"]
            )
            continue
        if outcome.expired:
            expired += 1
        elif outcome.late_case_opened:
            late_cases_opened += 1
        else:
            left_for_webhook += 1

    return ReconciliationSummary(
        candidates=len(rows),
        expired=expired,
        late_cases_opened=late_cases_opened,
        left_for_webhook=left_for_webhook,
    )


__all__ = ["ReconciliationSummary", "reconcile_expired_checkouts"]
