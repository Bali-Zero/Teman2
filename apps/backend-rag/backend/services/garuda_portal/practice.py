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
`practice_release` job onto `garuda_order_outbox` at OP-02 -- but no
production code anywhere in this repository consumes `garuda_order_outbox`
for ANY job_type yet (checked: `payment_paid_email` and
`staff_page_duplicate_charge` are equally unconsumed). Building a
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
                    extra={"order_id": order_id},
                )
                return None
            paid_event_id = paid_event["event_id"]

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
                paid_event_id,
            )

            if inserted is None:
                # Lost the race -- another concurrent read already created
                # the practice for this same OP-02 event. Re-read its real
                # practice_id rather than returning the id we minted but
                # never persisted.
                existing = await conn.fetchrow(
                    "SELECT practice_id FROM garuda_practices WHERE source_paid_journal_event_id = $1",
                    paid_event_id,
                )
                if existing is None:
                    # Genuinely impossible under READ COMMITTED+ (the
                    # conflicting row's inserting transaction must commit
                    # before ON CONFLICT can observe it) -- fail safe.
                    logger.error(
                        "garuda_portal.practice.pr01_race_lost_row_vanished",
                        extra={"order_id": order_id},
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
                idempotency_key_digest=hashlib.sha256(paid_event_id.encode("utf-8")).digest(),
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
                extra={"order_id": order_id},
            )
            return PracticeView(
                practice_id=won_practice_id,
                state="Received",
                artifact_available=False,
            )


__all__ = ["PracticeRepository", "PracticeView"]
