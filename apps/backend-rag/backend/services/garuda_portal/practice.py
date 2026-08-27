"""GARUDA VOA — practice-serving (L4, `products/garuda-voa/LANES.md`).

Closes the gap `garuda_orders_router.py::get_order_and_practice` names in
its own comment ("Practice is L4/L7 territory -- served null here rather
than guessed") and the one `garuda_ops/synthetic_probe.py::ReceivedPracticeStage`
names ("no garuda_portal/practice package exists yet").

**Scope, deliberately narrow.** This module implements ONLY PR-01
(STATE-MACHINE.md line 84: "not_started -> Received, system, OP-02
committed and its outbox event is consumed") and the customer-safe READ of
whatever practice state exists. It does NOT implement PR-02..PR-11 (the
staff transition engine: begin review, block, submit, approve, reject,
resume, deliver) -- there is no staff UI, no staff auth surface wired
end-to-end, and no staff endpoint anywhere in this codebase yet to drive
those transitions. Building an unreachable staff write path here would be
exactly the "green mascherava organi morti" shape cicatrix-superscar.md
family #2 warns against; `garuda_practices` (migration 287) is schemed to
hold the full state machine so a later PR adds transition logic without a
second migration, but this file only ever writes `Received`.

**Why PR-01 is lazily materialized on READ rather than by an async worker.**
L3's `handle_paid_event` (repository.py) already enqueues a
`practice_release` job onto `garuda_order_outbox` at OP-02.

CORRECTED 2026-08-27: the rationale below used to rest on "no production
code anywhere in this repository consumes `garuda_order_outbox` for ANY
job_type yet (checked: `payment_paid_email` and
`staff_page_duplicate_charge` are equally unconsumed)". Half of that is now
false: `outbox_handlers.py` registers real handlers for `practice_release`
AND `payment_paid_email` (only the `staff_page_*` half of the parenthetical
still holds -- those nine job types remain unhandled). **So a
`Received` practice now has TWO independent producers: this lazy read, and
`PracticeReleaseHandler` draining the job.** They are believed to agree --
`_create_received_practice`'s idempotency is what makes the pair safe -- but
believed is the operative word: no test crosses both paths, so nothing in
the suite would notice if they diverged. Do not read the design note below
as evidence that they agree; read it as the reason only one path used to
exist.

The original reasoning, kept because it still explains the shape: building a
dedicated outbox dispatcher is cross-cutting infrastructure that belongs to
whoever owns the outbox contract as a whole, not a decision this lane
should make unilaterally by building one worker for one job_type. Instead,
`get_order_and_practice_view` performs PR-01 idempotently the moment a
caller asks to see a paid order's practice -- structurally safe under
concurrent callers (see `_create_received_practice`'s docstring) and
observably identical to a worker having already run, because the contract
never promises a customer-visible email is what makes a practice "exist"
-- it promises `PracticeView` for a paid order eventually returns
`Received`, which this satisfies on first read.

**Ownership filtering.** `get_order_and_practice_view` takes BOTH
`order_id` and `result_id_ref` and requires an exact join match on both --
the same predicate `garuda_orders_router.py::get_order_and_practice`'s own
query uses post-#4910 (the order-ownership IDOR fix). A caller passing the
wrong `result_id_ref` for a real `order_id` gets back `None`, identical to
a genuinely nonexistent `order_id` -- non-enumerating, matching
`OrderNotFound`'s own documented shape.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import sanitize_for_log
from backend.services.garuda_orders import journal

logger = logging.getLogger(__name__)

#: STATE-MACHINE.md: the customer-visible practice states this module can
#: ever observe or create. `not_started` is never a row -- see module
#: docstring. Kept here (not imported from garuda_orders.state_machine,
#: which only models the ORDER half) as the practice-half source of truth
#: until a PR-02..PR-11 module needs to import it.
_DB_TO_WIRE_STATE: dict[str, str] = {
    "Received": "Received",
    "In_review": "In review",
    "Blocked": "Blocked",
    "Submitted": "Submitted",
    "Approved": "Approved",
    "Rejected": "Rejected",
    "Delivered": "Delivered",
}


@dataclass(frozen=True, slots=True)
class PracticeView:
    """Mirrors `contracts/openapi.yaml`'s `PracticeView` schema exactly --
    the wire shape, never the DB row shape (`private_staff_note`,
    `resume_target`, `artifact_id`, `artifact_digest` are staff-only /
    internal and MUST NOT appear here -- PR-F04)."""

    practice_id: str
    state: str
    artifact_available: bool
    customer_reason_key: str | None = None
    required_action_key: str | None = None

    def to_wire(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "practice_id": self.practice_id,
            "state": self.state,
            "artifact_available": self.artifact_available,
        }
        if self.customer_reason_key is not None:
            body["customer_reason_key"] = self.customer_reason_key
        if self.required_action_key is not None:
            body["required_action_key"] = self.required_action_key
        return body


class PracticeRepository:
    """The one L4 write path onto `garuda_practices`: PR-01 only.

    Constructed directly over the shared `asyncpg.Pool` the router already
    exposes as `request.app.state.garuda_db_pool` (the SAME pool
    `get_order_and_practice` reads from post-#4910, not a second
    `create_pool()` -- mirrors `garuda_orders_router.py`'s own comment on
    why that attribute is a domain-named alias, not a new connection).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_order_and_practice_view(
        self, *, order_id: str, result_id_ref: str
    ) -> dict[str, Any] | None:
        """Ownership-filtered read of order + practice, with lazy PR-01.

        Returns `None` if no order exists for this `(order_id,
        result_id_ref)` pair -- the caller's existing 404 `ORDER_NOT_FOUND`
        shape, unchanged by this module. Otherwise returns a dict with the
        order's own fields (`order_id`, `order_state`, `price_idr`,
        `browser_observation`) plus `practice` (a `PracticeView.to_wire()`
        dict, or `None` if the order is not yet paid or PR-01 has not
        fired) -- the full `OrderView` shape the router returns verbatim.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    o.order_id, o.state AS order_state, o.price_idr,
                    o.browser_observation,
                    p.practice_id, p.state AS practice_state,
                    p.customer_reason_key, p.required_action_key,
                    p.artifact_available
                FROM garuda_orders o
                LEFT JOIN garuda_practices p ON p.order_id = o.order_id
                WHERE o.order_id = $1 AND o.result_id_ref = $2
                """,
                order_id,
                result_id_ref,
            )
            if row is None:
                return None

            practice: dict[str, Any] | None = None
            if row["practice_id"] is not None:
                practice = PracticeView(
                    practice_id=row["practice_id"],
                    state=_DB_TO_WIRE_STATE[row["practice_state"]],
                    artifact_available=row["artifact_available"],
                    customer_reason_key=row["customer_reason_key"],
                    required_action_key=row["required_action_key"],
                ).to_wire()
            elif row["order_state"] == "paid":
                # PR-F01 guard: only a `paid` order may ever get a practice.
                # No row exists yet for this paid order -- perform PR-01
                # now (see module docstring for why lazily, on read).
                created = await self._create_received_practice(conn, order_id=order_id)
                if created is not None:
                    practice = created.to_wire()

            return {
                "order_id": row["order_id"],
                "order_state": row["order_state"],
                "price_idr": row["price_idr"],
                "browser_observation": row["browser_observation"],
                "practice": practice,
            }

    async def _create_received_practice(
        self, conn: asyncpg.Connection, *, order_id: str
    ) -> PracticeView | None:
        """PR-01: `not_started -> Received`.

        Idempotent under concurrent callers: `source_paid_journal_event_id`
        is UNIQUE (migration 287), so two racing reads for the same paid
        order both attempt the INSERT, exactly one commits, and the loser's
        `ON CONFLICT DO NOTHING` returns no row -- it then re-SELECTs the
        winner's row rather than raising. Only the winner appends the
        `practice.received` journal event and enqueues the confirmation
        email job, so a race never produces two journal events or two
        emails for one order (SM-G08).

        PR-F01 (guard, enforced by the caller, not re-checked here beyond
        this docstring's assumption): the caller only invokes this when
        `garuda_orders.state = 'paid'`, which is written exclusively by
        OP-02 (`handle_paid_event`) in the SAME transaction as the
        `payment.paid` journal append (SM-G07) -- so a `paid` order is
        guaranteed to have exactly one `payment.paid`/OP-02 journal event.
        If that invariant is ever violated (a bug elsewhere), this method
        fails safe: it finds no OP-02 event, logs, and returns `None`
        rather than fabricating a practice with no idempotency anchor.
        """
        async with conn.transaction():
            paid_event = await conn.fetchrow(
                """
                SELECT event_id FROM garuda_order_journal
                WHERE aggregate_type = 'order' AND aggregate_id = $1
                  AND transition_id = 'OP-02'
                ORDER BY occurred_at ASC
                LIMIT 1
                """,
                order_id,
            )
            if paid_event is None:
                # See docstring: this should be unreachable for a genuinely
                # `paid` order. Logged, not raised -- the GET must still
                # answer with practice=null rather than 500 a customer
                # polling their tracker.
                logger.error(
                    "garuda_portal.practice.pr01_missing_op02_event",
                    extra={"order_id": sanitize_for_log(order_id)},
                )
                return None
            return await mint_received_practice(
                conn, order_id=order_id, paid_journal_event_id=paid_event["event_id"]
            )


async def mint_received_practice(
    conn: asyncpg.Connection, *, order_id: str, paid_journal_event_id: str
) -> PracticeView | None:
    """PR-01's actual write: `not_started -> Received`, given a KNOWN
    `payment.paid`/OP-02 journal event id.

    Two callers, both correct, both idempotent against the SAME
    `source_paid_journal_event_id` UNIQUE constraint (migration 287):

    1. `PracticeRepository._create_received_practice` (lazy-on-read
       safety net): looks up the OP-02 event first, since the caller
       there (a customer's GET) does not already have it.
    2. `GarudaOrderRepository.handle_paid_event` (L3, EAGER path -- team-
       lead directive 2026-08-25, cross-lane call explicitly authorized):
       calls this DIRECTLY with the `event_id` it just minted for
       `payment.paid`, in the SAME transaction, so a practice is recorded
       the instant payment is confirmed -- never conditioned on the
       customer ever opening their tracker page. This closes a real
       product defect the lazy-only version had: a paid, never-viewed
       order left Bali Zero holding money with no work item recorded.
       Minting inside OP-02's own transaction (rather than out-of-band)
       is INTENTIONAL, not merely convenient: if the practice INSERT ever
       fails, the whole transaction rolls back -- `garuda_orders` never
       reaches `paid`, `garuda_payment_inbox`'s dedup row never commits
       either, and the provider's webhook retry (Xendit retries on a
       non-2xx response) gets a clean second attempt instead of a
       silently half-completed payment. This is a STRONGER invariant than
       decoupling payment from practice creation, not merely a smaller
       diff.

    Idempotent under concurrent callers: `source_paid_journal_event_id`
    is UNIQUE, so two racing callers for the same paid order (e.g. the
    eager path from a webhook and a customer's lazy read arriving before
    the webhook transaction commits) both attempt the INSERT, exactly one
    commits, and the loser's `ON CONFLICT DO NOTHING` returns no row -- it
    then re-SELECTs the winner's row rather than raising. Only the winner
    appends the `practice.received` journal event and enqueues the
    confirmation email job, so a race never produces two journal events
    or two emails for one order (SM-G08).
    """
    practice_id = journal.new_opaque_id("practice")
    inserted = await conn.fetchrow(
        """
        INSERT INTO garuda_practices (practice_id, order_id, source_paid_journal_event_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (source_paid_journal_event_id) DO NOTHING
        RETURNING practice_id
        """,
        practice_id,
        order_id,
        paid_journal_event_id,
    )

    if inserted is None:
        # Lost the race -- another concurrent caller already created the
        # practice for this same OP-02 event. Re-read its real
        # practice_id rather than returning the id we minted but never
        # persisted.
        existing = await conn.fetchrow(
            "SELECT practice_id FROM garuda_practices WHERE source_paid_journal_event_id = $1",
            paid_journal_event_id,
        )
        if existing is None:
            # Genuinely impossible under READ COMMITTED+ (the conflicting
            # row's inserting transaction must commit before ON CONFLICT
            # can observe it) -- fail safe.
            logger.error(
                "garuda_portal.practice.pr01_race_lost_row_vanished",
                extra={"order_id": sanitize_for_log(order_id)},
            )
            return None
        return PracticeView(
            practice_id=existing["practice_id"],
            state="Received",
            artifact_available=False,
        )

    won_practice_id = inserted["practice_id"]
    event_id = await journal.append_event(
        conn,
        event_name="practice.received",
        aggregate_type="practice",
        aggregate_id=won_practice_id,
        transition_id="PR-01",
        customer_visible=True,
        idempotency_key_digest=hashlib.sha256(paid_journal_event_id.encode("utf-8")).digest(),
        detail={},
    )
    await journal.enqueue_outbox(
        conn,
        order_id=order_id,
        journal_event_id=event_id,
        job_type="practice_received_email",
    )
    logger.info(
        "garuda_portal.practice.pr01_created",
        extra={"order_id": sanitize_for_log(order_id)},
    )
    return PracticeView(
        practice_id=won_practice_id,
        state="Received",
        artifact_available=False,
    )


__all__ = ["PracticeRepository", "PracticeView", "mint_received_practice"]
