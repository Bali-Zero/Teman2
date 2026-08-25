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
import re

import asyncpg

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_orders.ports import ReviewedCheckSnapshot

logger = logging.getLogger(__name__)

__all__ = ["PostgresEligibilityCheckLookup"]

# CodeQL finding (Log Injection, medium; PR #4920 review 2026-08-25): the old
# guard here tested only emptiness, so a client-supplied result_id containing
# newlines/control characters sailed straight through into both the query
# and the `logger.warning` call below -- on a product whose PII boundary
# explicitly covers logs, arbitrary client text landing in them is exactly
# what that rule exists to prevent. This is the SAME contract already
# enforced in four other places -- migrations 285/286's
# `CHECK (result_id ~ '^[A-Za-z0-9_-]{22,128}$')`, and the identical
# `_RESULT_ID_PATTERN` in `app/routers/garuda_portal_auth.py` and
# `app/routers/garuda_voa_public.py` -- this is a local copy rather than a
# shared import because importing a router-owned pattern into this SERVICE
# module would be a layering violation, and creating a new shared home for
# one regex was judged to widen this PR's diff at gate time (team-lead
# review, 2026-08-25) more than a documented duplicate does. The migration
# CHECK constraint is the actual SSOT; if this ever needs a fourth touch
# point, that is the signal to extract it properly.
_RESULT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22,128}$")


class PostgresEligibilityCheckLookup:
    """Real ``EligibilityCheckLookup`` over ``garuda_voa_check_results``."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        # Malformed input never reaches the database with a query shaped to
        # explain why -- absent and malformed both resolve to None, matching
        # the Protocol's "None for malformed/absent/non-owned" contract. The
        # schema's own definition of "malformed" is `_RESULT_ID_PATTERN`
        # (migrations 285/286's CHECK constraint), not merely "non-empty" --
        # a value that fails this pattern can be neither a real row nor a
        # safe thing to interpolate into a log line.
        if not isinstance(result_id, str) or _RESULT_ID_PATTERN.fullmatch(result_id) is None:
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
