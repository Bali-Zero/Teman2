"""Real ``EligibilityCheckLookup`` bridging L3's port to L2's persisted check.

Composition-lane adapter: reads `garuda_voa_check_results` (migration 286,
owned by the composition lane, not L2 or L3's own file-ownership scope) and
translates it into the `ReviewedCheckSnapshot` `garuda_orders.ports`
declares. This is the orchestrator wiring `ports.py` describes ("the
orchestrator wires the real adapter at router-composition time").

``review_confirmed`` semantics: `garuda_orders_router.create_order_from_check`
already requires the CLIENT to assert `review_confirmed: true` in its own
request body (contract `CreateOrderRequest.review_confirmed: {const: true}`)
before this lookup is ever reached, and
`GarudaOrderRepository.create_order_and_checkout` independently checks
`check.review_confirmed` on what THIS lookup returns. The two checks answer
different questions: the client's assertion is "I have looked at my result",
the check's own `review_confirmed` is "this result is the kind of thing that
CAN be ordered" -- a DECLINE verdict has nothing to sell (`price_idr` is
NULL by the 286 CHECK constraint) and must never reach checkout regardless of
what the client claims. `review_confirmed` here is therefore exactly
``outcome.accepted`` -- true iff the persisted verdict was ACCEPT.

Ownership-to-session binding (does result_id belong to the caller's magic-link
session) is enforced by the ROUTER (`garuda_orders_router.create_order_from_
check` compares the session's own result_id, as returned by
`PostgresMagicLinkStore.verify_session`, against the body's `result_id` --
see that file), not by this lookup: `EligibilityCheckLookup.get_reviewed_
check` takes only `result_id` per its frozen Protocol signature, with no
actor parameter to check ownership against. This adapter therefore answers
"does a reviewed, orderable check exist for this result_id" -- the same
question the Protocol's own docstring poses -- and defers "is the caller
allowed to ask" to the layer that actually holds session identity.
"""

from __future__ import annotations

import logging

import asyncpg

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot

logger = logging.getLogger(__name__)

__all__ = ["PostgresEligibilityCheckLookup"]


class PostgresEligibilityCheckLookup:
    """Real ``EligibilityCheckLookup`` over ``garuda_voa_check_results``."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        # Malformed input never reaches the database with a query shaped to
        # explain why -- absent and malformed both resolve to None, matching
        # the Protocol's "None for malformed/absent/non-owned" contract.
        if not isinstance(result_id, str) or not result_id:
            return None
        try:
            row = await self._pool.fetchrow(
                "SELECT case_type, decision FROM garuda_voa_check_results WHERE result_id = $1",
                result_id,
            )
        except asyncpg.PostgresError:
            logger.warning(
                "garuda_orders: eligibility check lookup failed for result_id=%s", result_id
            )
            return None
        if row is None:
            return None
        return ReviewedCheckSnapshot(
            result_id=result_id,
            case_type=CaseType(row["case_type"]),
            review_confirmed=row["decision"] == "ACCEPT",
        )
