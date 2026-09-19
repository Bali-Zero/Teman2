"""GARUDA VOA order/payment repository — STATE-MACHINE.md order half.

Every write here follows SM-G07: compare-and-set against the source state,
append an immutable journal event, and enqueue outbox work, ALL inside one
transaction. `garuda_orders`'s own trigger (`guard_garuda_order_state_
transition`) is defense-in-depth behind the CAS `WHERE state = $expected`,
not a substitute for it — the CAS is what makes a concurrent duplicate
webhook see 0 rows updated instead of racing the trigger.

One deliberate cross-lane call (team-lead directive, 2026-08-25, gate on
PR #4928): `handle_paid_event`'s `awaiting_payment -> paid` branch calls
L4's `garuda_portal.practice.mint_received_practice` directly, inside THIS
transaction, right after appending `payment.paid`/OP-02. Measured
reachability before this fix: the only production call site that ever
inserted a `garuda_practices` row was the customer's own GET (lazy-on-
read) — a paid order the customer never looked at again left Bali Zero
holding the money with no work item ever recorded, and the synthetic
probe cannot catch it (it always opens the tracker, same as a curious
customer). Minting PR-01 inside OP-02's own transaction — rather than via
the `practice_release` outbox job this branch also still enqueues, which
NO production code consumes for any job_type — means the whole payment
event is atomic with its resulting practice: if the practice INSERT ever
fails, `garuda_orders` never reaches `paid` and `garuda_payment_inbox`'s
dedup row never commits either, so the provider's webhook retry gets a
clean second attempt instead of a half-completed payment. The customer-
facing lazy-on-read path (`PracticeRepository._create_received_practice`)
is UNCHANGED and stays live as an idempotent safety net for any order
paid before this fix landed — both paths mint through the same
`mint_received_practice`, guarded by the same `source_paid_journal_
event_id` UNIQUE constraint (migration 287), so neither path can ever
double-create.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from backend.services.garuda_flow import pricing
from backend.services.garuda_orders import idempotency, journal
from backend.services.garuda_orders.errors import (
    NoOpenLateCase,
    OrderNotFound,
    OrderNotReady,
    PaymentProviderUnavailable,
    PersistencePolicyUnavailable,
    PriceUnresolvable,
    ResultNotFound,
)
from backend.services.garuda_orders.models import Applicant
from backend.services.garuda_orders.ports import EligibilityCheckLookup
from backend.services.garuda_orders.state_machine import OrderState
from backend.services.garuda_portal.practice import mint_received_practice
from backend.services.payments.port import (
    NormalizedFailureEvent,
    NormalizedPaidEvent,
    NormalizedRefundEvent,
    PaymentProvider,
    RefundFailed,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExpiryOutcome:
    """What one OP-04 sweep candidate turned out to be.

    Three outcomes, mutually exclusive, because the caller COUNTS them and a
    counter that merges two of them lies in the log: the order was expired,
    or an OP-F08 late case was opened on it, or the webhook won the race
    while we were asking. Before this existed `expire_if_unpaid` returned a
    bare bool and reconciliation counted every False as "left for the
    webhook" -- including the orders it had just PAGED about, for which the
    whole point is that no webhook is coming.
    """

    expired: bool
    late_case_opened: bool


_CHECKOUT_TTL_MINUTES = 60


async def _quarantine(conn: asyncpg.Connection, *, provider_event_id: str, reason: str) -> None:
    """Refuse an authentic provider callback, ON THE RECORD and with the cause.

    A quarantined row is not an error we swallowed — it is a signature-valid
    callback we DELIBERATELY declined to act on, because it could not be tied
    to exactly one order or it claimed a payment for the wrong amount. Money
    moved on the provider's side and we did not move our own state to match.
    That is a page, not a metric: `payment_inbox_watch.count_quarantined`
    reads these rows and `quarantine_alarm.QuarantineAlarm` turns them into
    one, wired into the GARUDA scheduler in `main_api.py`.

    `reason` is one of migration 298's four CHECK-enforced values. It is
    recorded HERE, where the branch that made the decision knows it for
    certain, rather than re-derived later by a reader that would have to
    guess between three causes this table used to collapse into one.

    Five call sites shared this UPDATE verbatim before the reason existed;
    they call this instead so the vocabulary has exactly one home.
    """

    await conn.execute(
        """
        UPDATE garuda_payment_inbox
           SET outcome = 'quarantined',
               quarantine_reason = $2,
               processed_at = statement_timestamp()
         WHERE provider = 'xendit' AND provider_event_id = $1
        """,
        provider_event_id,
        reason,
    )


async def _open_late_case(
    conn: asyncpg.Connection, *, order_id: str, charge_id: str | None
) -> None:
    """Open a remediation case on an order — CLEARING whatever the previous
    case left behind.

    Migration 284's CHECK admits (open TRUE, resolution NULL) and
    (open FALSE, resolution NOT NULL), never (open TRUE, resolution NOT
    NULL): `late_case_resolution` describes the case the order carries NOW,
    and the history lives in the journal, where `order.late_resolved` and
    OP-02's `honoured` close are permanent. So an order whose case was closed
    and which now earns a SECOND one must start it with an empty resolution,
    or the UPDATE is a `check_violation` that aborts the whole webhook
    transaction — the payment inbox row never commits and the provider
    retries into the same wall.

    That second case stopped being hypothetical when a refunded OP-F08 case
    started leaving `awaiting_payment` for `refunded`: the staff page's first
    instruction is to replay the webhook, the replay lands in OP-F04, and
    OP-F04 opens a case on an order that has just been resolved. MEASURED as
    `CheckViolationError ... garuda_orders_check` before this existed. OP-F05
    and OP-08 carry the same write, reachable the same way from an
    OP-F08 case that OP-02 closed as `honoured`, so all three call here.

    `late_case_open = FALSE` in the predicate keeps the write idempotent: a
    case already open is never re-opened, and its charge id is never
    overwritten by a later event.
    """

    await conn.execute(
        """
        UPDATE garuda_orders
           SET late_case_open = TRUE,
               late_case_charge_id = COALESCE($2, late_case_charge_id),
               late_case_resolution = NULL,
               late_case_staff_reference = NULL
         WHERE order_id = $1 AND late_case_open = FALSE
        """,
        order_id,
        charge_id,
    )


class GarudaOrderRepository:
    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        eligibility_lookup: EligibilityCheckLookup,
        provider: PaymentProvider,
        environment: str,
    ) -> None:
        self._pool = pool
        self._lookup = eligibility_lookup
        self._provider = provider
        self._environment = environment

    # ---- OP-00 + OP-01: createOrderFromCheck ---------------------------

    async def create_order_and_checkout(
        self,
        *,
        result_id: str,
        applicant: Applicant,
        review_confirmed: bool,
        idempotency_key_sha256: bytes,
        canonical_payload_sha256: bytes,
    ) -> tuple[dict[str, Any], bool]:
        """Returns (OrderCheckout-shaped body, replayed)."""

        if not review_confirmed:
            raise OrderNotReady("review_confirmed must be true")

        check = await self._lookup.get_reviewed_check(result_id)
        if check is None:
            raise ResultNotFound(result_id)
        if not check.review_confirmed:
            raise OrderNotReady(result_id)

        today = datetime.now(UTC).date()
        if not await self._active_order_policy_available():
            raise PersistencePolicyUnavailable("no active GARUDA_ORDER retention policy")

        price_idr, price_key = pricing.price_for_case(check.case_type, today=today)
        if price_idr is None or price_key is None:
            raise PriceUnresolvable(check.case_type.value)

        async with self._pool.acquire() as conn:
            outcome = await idempotency.reserve(
                conn,
                key_sha256=idempotency_key_sha256,
                payload_sha256=canonical_payload_sha256,
            )
            if outcome.replayed:
                assert outcome.response_body is not None
                return outcome.response_body, True

            order_id = outcome.order_id
            if order_id is None:
                # CORRECTED (refuter finding): a customer who reloads and
                # issues a FRESH Idempotency-Key against a still-live
                # `result_id_ref` used to hit `INSERT INTO garuda_orders`
                # head-on into `uq_garuda_orders_result_id_ref_live` with no
                # ON CONFLICT -- a raw asyncpg.UniqueViolationError -> 500 on
                # the self-recovery path of a payment flow. Look up the live
                # order for this check FIRST and bind this (new) key to it
                # instead of inserting a duplicate -- two different
                # Idempotency-Keys are allowed to reference the same order
                # (no uniqueness on garuda_order_idempotency.order_id), and
                # this also means a live `created` order gets a REAL
                # checkout_url below (the CREATED branch calls the provider)
                # instead of ever reaching the `pending-resume:` placeholder.
                existing = await conn.fetchrow(
                    """
                    SELECT order_id FROM garuda_orders
                     WHERE result_id_ref = $1 AND state IN ('created', 'awaiting_payment', 'paid')
                    """,
                    result_id,
                )
                if existing is not None:
                    order_id = existing["order_id"]
                    async with conn.transaction():
                        await idempotency.bind_order_id(
                            conn, key_sha256=idempotency_key_sha256, order_id=order_id
                        )
                else:
                    # CORRECTED (gate finding): the lookup above and this
                    # INSERT are two separate statements, not one atomic
                    # unit -- two concurrent requests with two fresh keys
                    # and no live order can both read `existing=None` and
                    # both attempt the insert. Catch the loser's
                    # UniqueViolationError on `uq_garuda_orders_result_id_
                    # ref_live` and fall back to the same lookup-and-bind
                    # path as the `existing is not None` branch above,
                    # instead of letting the race surface as a 500.
                    candidate_order_id = journal.new_opaque_id("ord")
                    try:
                        async with conn.transaction():
                            await conn.execute(
                                """
                                INSERT INTO garuda_orders
                                    (order_id, result_id_ref, case_type, applicant_full_name,
                                     applicant_email, applicant_phone, applicant_passport_number,
                                     price_idr, price_catalogue_key)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                                """,
                                candidate_order_id,
                                result_id,
                                check.case_type.value,
                                applicant.full_name,
                                applicant.email,
                                applicant.phone,
                                applicant.passport_number,
                                price_idr,
                                price_key,
                            )
                            await journal.append_event(
                                conn,
                                event_name="order.created",
                                aggregate_type="order",
                                aggregate_id=candidate_order_id,
                                transition_id="OP-00",
                                customer_visible=False,
                                idempotency_key_digest=idempotency_key_sha256,
                                canonical_payload_digest=canonical_payload_sha256,
                                detail={"price_idr": price_idr, "price_catalogue_key": price_key},
                            )
                            await idempotency.bind_order_id(
                                conn, key_sha256=idempotency_key_sha256, order_id=candidate_order_id
                            )
                        order_id = candidate_order_id
                    except asyncpg.exceptions.UniqueViolationError:
                        winner = await conn.fetchrow(
                            """
                            SELECT order_id FROM garuda_orders
                             WHERE result_id_ref = $1
                               AND state IN ('created', 'awaiting_payment', 'paid')
                            """,
                            result_id,
                        )
                        if winner is None:  # pragma: no cover - defensive
                            raise
                        order_id = winner["order_id"]
                        async with conn.transaction():
                            await idempotency.bind_order_id(
                                conn, key_sha256=idempotency_key_sha256, order_id=order_id
                            )

            row = await conn.fetchrow(
                "SELECT state, price_idr FROM garuda_orders WHERE order_id = $1",
                order_id,
            )
        if row is None:  # pragma: no cover - defensive, cannot happen post-insert
            raise OrderNotFound(order_id)

        if row["state"] == OrderState.CREATED.value:
            try:
                checkout = await self._provider.create_checkout_session(
                    order_id=order_id,
                    price_idr=row["price_idr"],
                    idempotency_key=idempotency_key_sha256.hex(),
                )
            except Exception as exc:  # provider transport/HTTP errors
                logger.warning(
                    "garuda_orders: checkout session creation failed for %s: %s", order_id, exc
                )
                raise PaymentProviderUnavailable(order_id) from exc

            async with self._pool.acquire() as conn, conn.transaction():
                updated = await conn.fetchrow(
                    """
                    UPDATE garuda_orders
                       SET state = 'awaiting_payment',
                           provider_session_id = $2,
                           checkout_expires_at = $3
                     WHERE order_id = $1 AND state = 'created'
                     RETURNING order_id
                    """,
                    order_id,
                    checkout.provider_session_id,
                    datetime.now(UTC) + timedelta(minutes=_CHECKOUT_TTL_MINUTES),
                )
                if updated is not None:
                    event_id = await journal.append_event(
                        conn,
                        event_name="payment.awaiting",
                        aggregate_type="order",
                        aggregate_id=order_id,
                        transition_id="OP-01",
                        customer_visible=True,
                    )
                    await journal.enqueue_outbox(
                        conn,
                        order_id=order_id,
                        journal_event_id=event_id,
                        job_type="checkout_ready_email",
                        payload={"checkout_url": checkout.checkout_url},
                    )
            checkout_url = checkout.checkout_url
            final_state = OrderState.AWAITING_PAYMENT.value
        else:
            # Resume path: `order_id` was bound to a previously-reserved
            # idempotency key OR to a still-live order found by the
            # result_id_ref lookup above. Either way it can be in ANY
            # state by now -- a webhook may have advanced it past
            # `awaiting_payment` while the original attempt was crashed or
            # in flight. CORRECTED (gate finding): this used to hardcode
            # `order_state: "awaiting_payment"` and always return a
            # checkout_url regardless of the order's REAL state, so a
            # customer whose order was already `paid` (or refunded/failed/
            # expired) was told to pay again. Report the real state, and
            # offer a checkout action ONLY while the order is genuinely
            # still awaiting payment.
            final_state = row["state"]
            if final_state == OrderState.AWAITING_PAYMENT.value:
                checkout_row = await self._pool.fetchrow(
                    "SELECT provider_session_id FROM garuda_orders WHERE order_id = $1", order_id
                )
                # Sandbox-safe placeholder: the real checkout_url isn't
                # persisted (it's a provider capability, never journal/DB
                # content per SM-G03) -- a genuine resume-after-crash
                # re-fetches it from the provider by provider_session_id.
                # Kept minimal here; flagged in the PR report as a
                # follow-up rather than guessed (scoped to the orchestrator
                # per the standing "returning customer" spec).
                checkout_url = (
                    f"pending-resume:{checkout_row['provider_session_id']}" if checkout_row else ""
                )
            else:
                checkout_url = None

        response_body = {
            "order_id": order_id,
            "order_state": final_state,
            "price_idr": row["price_idr"],
            "checkout_url": checkout_url,
        }
        async with self._pool.acquire() as conn:
            await idempotency.complete(
                conn,
                key_sha256=idempotency_key_sha256,
                response_status=201,
                response_body=response_body,
            )
        return response_body, False

    async def _active_order_policy_available(self) -> bool:
        async with self._pool.acquire() as conn:
            return bool(
                await conn.fetchval(
                    "SELECT public.active_garuda_order_policy_available($1, $2)",
                    self._environment,
                    datetime.now(UTC),
                )
            )

    # ---- OP-07: browser return observation ------------------------------

    async def record_browser_return_observation(
        self, *, order_id: str, result_id: str, return_nonce: str
    ) -> None:
        """`result_id` is the caller's session ownership key (the router's
        `_require_magic_session_actor`-derived value) -- both the UPDATE and
        the not-found fallback below filter on `result_id_ref = $3` so an
        order that exists but belongs to a different session's result_id
        raises the SAME `OrderNotFound` a genuinely absent order_id would,
        never a distinguishable status (`OrderNotFound`'s docstring already
        calls this "non-enumerating" -- a caller probing another customer's
        order_id must not learn it exists)."""
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE garuda_orders
                   SET browser_observation = 'browser_return_observed', browser_return_nonce = $2
                 WHERE order_id = $1 AND result_id_ref = $3
                   AND browser_return_nonce IS DISTINCT FROM $2
                 RETURNING order_id
                """,
                order_id,
                return_nonce,
                result_id,
            )
            if row is None:
                exists = await conn.fetchval(
                    "SELECT 1 FROM garuda_orders WHERE order_id = $1 AND result_id_ref = $2",
                    order_id,
                    result_id,
                )
                if exists is None:
                    raise OrderNotFound(order_id)
                return  # exact nonce replay — no-op, no second write (OP-07 idempotent)
            # OP-07 deliberately appends NO authoritative journal event and
            # sends no email — it is non-authoritative by contract.

    # ---- OP-02..OP-09, OP-F04, OP-F05, OP-08: webhook reconciliation ----

    async def handle_paid_event(
        self, event: NormalizedPaidEvent, *, canonical_payload_sha256: bytes
    ) -> str:
        """Returns the outcome tag for logging/metrics: committed transition id."""

        async with self._pool.acquire() as conn, conn.transaction():
            inbox_row = await conn.fetchrow(
                """
                INSERT INTO garuda_payment_inbox
                    (provider, provider_event_id, canonical_payload_sha256, transition_id)
                VALUES ('xendit', $1, $2, 'OP-02')
                ON CONFLICT (provider, provider_event_id) DO NOTHING
                RETURNING id
                """,
                event.provider_event_id,
                canonical_payload_sha256,
            )
            if inbox_row is None:
                return "OP-09"  # duplicate delivery — already processed or in flight

            order = await conn.fetchrow(
                "SELECT order_id, state, price_idr FROM garuda_orders WHERE provider_session_id = $1 FOR UPDATE",
                event.provider_session_id,
            )
            if order is None:
                await _quarantine(
                    conn,
                    provider_event_id=event.provider_event_id,
                    reason="unmatched_session",
                )
                return "OP-F03"  # cannot reconcile to exactly one order

            order_id, state = order["order_id"], order["state"]
            transition_id = "OP-02"

            # CORRECTED (refuter finding): a signed webhook is authentic
            # about WHO paid, never about HOW MUCH -- SM-G09/OP-F03 require
            # "exact reconciliation to the order and amount", and this was
            # missing entirely. A PAID event for the wrong amount/currency
            # must never flip the order to `paid`.
            if state == OrderState.AWAITING_PAYMENT.value and (
                event.amount_idr != order["price_idr"] or event.currency != "IDR"
            ):
                await _quarantine(
                    conn,
                    provider_event_id=event.provider_event_id,
                    reason="amount_mismatch",
                )
                return "OP-F03"

            if state == OrderState.AWAITING_PAYMENT.value:
                # The OP-F08 late case, if one is open, closes HERE as
                # `honoured` — in the same transaction that admits the
                # payment. Without this the case opened by reconciliation
                # survives the webhook that answers it: the order reads
                # `paid` with a practice minted beside it AND an open,
                # refundable late case, and `resolve_late_order` does not
                # re-check state before calling the provider. A staff member
                # acting on that page would refund a payment that had already
                # bought the service. Found by Codex `gpt-5.6-sol` as the
                # mirror image of the race cured on the OPENING side, and it
                # is the same invariant read backwards: a case must not
                # outlive the question it was asking.
                #
                # `CASE WHEN late_case_open` reads the OLD row (SET
                # expressions always do), so an order that never had a case
                # keeps `late_case_resolution` NULL rather than acquiring a
                # resolution for a case that never existed — migration 284's
                # CHECK admits (open FALSE, resolution NOT NULL) only as the
                # shape of a CLOSED case.
                closed_late_case = await conn.fetchval(
                    """
                    WITH before AS (
                        SELECT order_id, late_case_open
                          FROM garuda_orders
                         WHERE order_id = $1
                    )
                    UPDATE garuda_orders o
                       SET state = 'paid',
                           provider_charge_id = $2,
                           late_case_resolution = CASE
                               WHEN o.late_case_open THEN 'honoured'
                               ELSE o.late_case_resolution
                           END,
                           late_case_open = FALSE
                      FROM before b
                     WHERE o.order_id = b.order_id AND o.state = 'awaiting_payment'
                    RETURNING b.late_case_open
                    """,
                    order_id,
                    event.provider_charge_id,
                )
                if closed_late_case:
                    # Order id only: this line exists so the close is
                    # searchable next to the page that opened it.
                    logger.info(
                        "garuda_orders %s: webhook paid an order with an open late case; "
                        "closed as honoured in the same transaction (OP-F08 -> OP-02)",
                        order_id,
                    )
                event_id = await journal.append_event(
                    conn,
                    event_name="payment.paid",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    transition_id="OP-02",
                    customer_visible=True,
                    detail={"amount_idr": event.amount_idr, "currency": event.currency},
                )
                await journal.enqueue_outbox(
                    conn,
                    order_id=order_id,
                    journal_event_id=event_id,
                    job_type="payment_paid_email",
                )
                await journal.enqueue_outbox(
                    conn, order_id=order_id, journal_event_id=event_id, job_type="practice_release"
                )
                # The customer's way IN. Enqueued in this same transaction, and
                # deliberately NOT ordered after `practice_release`: the outbox
                # gives no inter-job ordering (SKIP LOCKED claims whatever is
                # free), so `PortalInviteHandler` keys on the practice row and
                # raises until it exists. Ordering enforced by the handler, not
                # by the enqueue sequence — see that class's docstring.
                await journal.enqueue_outbox(
                    conn, order_id=order_id, journal_event_id=event_id, job_type="portal_invite"
                )
                # PR-01, eagerly, in the SAME transaction as the payment.paid
                # event above -- see this module's own docstring for why
                # (team-lead directive: a paid order must never depend on the
                # customer opening their tracker to get a work item).
                await mint_received_practice(
                    conn, order_id=order_id, paid_journal_event_id=event_id
                )
            elif state == OrderState.PAID.value:
                transition_id = "OP-08"
                event_id = await journal.append_event(
                    conn,
                    event_name="payment.duplicate_charge_detected",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    transition_id="OP-08",
                    customer_visible=True,
                    detail={"second_charge_id": event.provider_charge_id},
                )
                await _open_late_case(conn, order_id=order_id, charge_id=None)
                await journal.enqueue_outbox(
                    conn,
                    order_id=order_id,
                    journal_event_id=event_id,
                    job_type="staff_page_duplicate_charge",
                )
            elif state == OrderState.REFUNDED.value:
                transition_id = "OP-F04"
                # CORRECTED (refuter finding): this branch previously opened
                # NO remediation case at all, so resolveLateOrder could never
                # act on the very orders OP-F04 pages staff about. Also
                # persists the LATE charge id (never `provider_charge_id`,
                # which for a refunded order still names the ORIGINAL,
                # already-refunded charge) so resolveLateOrder refunds the
                # right money.
                await _open_late_case(conn, order_id=order_id, charge_id=event.provider_charge_id)
                event_id = await journal.append_event(
                    conn,
                    event_name="payment.late_paid_after_refund",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    transition_id="OP-F04",
                    customer_visible=False,
                    detail={"charge_id": event.provider_charge_id},
                )
                await journal.enqueue_outbox(
                    conn,
                    order_id=order_id,
                    journal_event_id=event_id,
                    job_type="staff_page_late_paid_after_refund",
                )
            elif state in (OrderState.FAILED.value, OrderState.EXPIRED.value):
                transition_id = "OP-F05"
                # CORRECTED (refuter finding): `provider_charge_id` is NULL
                # here (a failed/expired order never reached OP-02) — the
                # late charge id must be persisted on the order, not only in
                # journal `detail`, or resolveLateOrder has nothing to refund.
                await _open_late_case(conn, order_id=order_id, charge_id=event.provider_charge_id)
                event_id = await journal.append_event(
                    conn,
                    event_name="payment.late_paid_after_terminal",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    transition_id="OP-F05",
                    customer_visible=False,
                    detail={"charge_id": event.provider_charge_id},
                )
                await journal.enqueue_outbox(
                    conn,
                    order_id=order_id,
                    journal_event_id=event_id,
                    job_type="staff_page_late_paid_after_terminal",
                )
            else:  # created — a paid event for a session never bound is unreconcilable
                await _quarantine(
                    conn,
                    provider_event_id=event.provider_event_id,
                    reason="session_not_bound",
                )
                return "OP-F03"

            await conn.execute(
                """
                UPDATE garuda_payment_inbox
                   SET order_id = $2, transition_id = $3, outcome = 'committed', processed_at = statement_timestamp()
                 WHERE provider = 'xendit' AND provider_event_id = $1
                """,
                event.provider_event_id,
                order_id,
                transition_id,
            )
            return transition_id

    async def handle_failure_event(
        self, event: NormalizedFailureEvent, *, canonical_payload_sha256: bytes
    ) -> str:
        async with self._pool.acquire() as conn, conn.transaction():
            inbox_row = await conn.fetchrow(
                """
                INSERT INTO garuda_payment_inbox (provider, provider_event_id, canonical_payload_sha256, transition_id)
                VALUES ('xendit', $1, $2, 'OP-03')
                ON CONFLICT (provider, provider_event_id) DO NOTHING
                RETURNING id
                """,
                event.provider_event_id,
                canonical_payload_sha256,
            )
            if inbox_row is None:
                return "OP-09"

            order = await conn.fetchrow(
                "SELECT order_id, state FROM garuda_orders WHERE provider_session_id = $1 FOR UPDATE",
                event.provider_session_id,
            )
            if order is None or order["state"] != OrderState.AWAITING_PAYMENT.value:
                # Two genuinely different incidents that this branch's single
                # `or` used to record identically: a failure event for a
                # checkout session we have never heard of, and one for an order
                # whose state does not admit it. Different cures, so different
                # recorded reasons.
                await _quarantine(
                    conn,
                    provider_event_id=event.provider_event_id,
                    reason="unmatched_session" if order is None else "unexpected_state",
                )
                return "OP-F03"

            order_id = order["order_id"]
            await conn.execute(
                "UPDATE garuda_orders SET state = 'failed' WHERE order_id = $1 AND state = 'awaiting_payment'",
                order_id,
            )
            event_id = await journal.append_event(
                conn,
                event_name="payment.failed",
                aggregate_type="order",
                aggregate_id=order_id,
                transition_id="OP-03",
                customer_visible=True,
                detail={
                    "outcome": event.failure.outcome.value,
                    "customer_action": event.failure.customer_action.value,
                },
            )
            await journal.enqueue_outbox(
                conn,
                order_id=order_id,
                journal_event_id=event_id,
                job_type="payment_failed_email",
                payload={"customer_action": event.failure.customer_action.value},
            )
            if event.failure.should_page:
                await journal.enqueue_outbox(
                    conn,
                    order_id=order_id,
                    journal_event_id=event_id,
                    job_type="staff_page_payment_failure",
                )
            await conn.execute(
                "UPDATE garuda_payment_inbox SET order_id = $2, outcome = 'committed', processed_at = statement_timestamp() WHERE provider = 'xendit' AND provider_event_id = $1",
                event.provider_event_id,
                order_id,
            )
            return "OP-03"

    async def handle_refund_event(
        self, event: NormalizedRefundEvent, *, canonical_payload_sha256: bytes
    ) -> str:
        async with self._pool.acquire() as conn, conn.transaction():
            inbox_row = await conn.fetchrow(
                """
                INSERT INTO garuda_payment_inbox (provider, provider_event_id, canonical_payload_sha256)
                VALUES ('xendit', $1, $2)
                ON CONFLICT (provider, provider_event_id) DO NOTHING
                RETURNING id
                """,
                event.provider_event_id,
                canonical_payload_sha256,
            )
            if inbox_row is None:
                return "OP-09"

            order = await conn.fetchrow(
                "SELECT order_id, state FROM garuda_orders WHERE provider_session_id = $1 FOR UPDATE",
                event.provider_session_id,
            )
            if order is None or order["state"] not in (
                OrderState.AWAITING_PAYMENT.value,
                OrderState.PAID.value,
            ):
                await _quarantine(
                    conn,
                    provider_event_id=event.provider_event_id,
                    reason="unmatched_session" if order is None else "unexpected_state",
                )
                return "OP-F03"

            order_id, state = order["order_id"], order["state"]
            if state == OrderState.AWAITING_PAYMENT.value:
                transition_id, event_name = "OP-05", "payment.refunded_out_of_order"
            else:
                transition_id, event_name = "OP-06", "payment.refunded"
            await conn.execute(
                "UPDATE garuda_orders SET state = 'refunded' WHERE order_id = $1 AND state = $2",
                order_id,
                state,
            )
            event_id = await journal.append_event(
                conn,
                event_name=event_name,
                aggregate_type="order",
                aggregate_id=order_id,
                transition_id=transition_id,
                customer_visible=True,
                detail={"refund_id": event.provider_refund_id},
            )
            await journal.enqueue_outbox(
                conn, order_id=order_id, journal_event_id=event_id, job_type="refund_email"
            )
            if transition_id == "OP-05":
                await journal.enqueue_outbox(
                    conn,
                    order_id=order_id,
                    journal_event_id=event_id,
                    job_type="staff_page_refund_out_of_order",
                )
            await conn.execute(
                "UPDATE garuda_payment_inbox SET order_id = $2, transition_id = $3, outcome = 'committed', processed_at = statement_timestamp() WHERE provider = 'xendit' AND provider_event_id = $1",
                event.provider_event_id,
                order_id,
                transition_id,
            )
            return transition_id

    # ---- OP-04: reconciliation-driven expiry (see reconciliation.py) ---

    async def expire_if_unpaid(
        self,
        *,
        order_id: str,
        provider_session_id: str,
    ) -> ExpiryOutcome:
        confirmation = await self._provider.confirm_no_successful_charge(
            provider_session_id=provider_session_id
        )
        if not confirmation.confirmed_unpaid:
            late_case_opened = await self._open_late_case_from_reconciliation(
                order_id=order_id,
                provider_charge_id=confirmation.provider_charge_id,
                provider_status=confirmation.provider_status,
            )
            return ExpiryOutcome(
                expired=False,
                late_case_opened=late_case_opened,
            )
        async with self._pool.acquire() as conn, conn.transaction():
            updated = await conn.fetchrow(
                "UPDATE garuda_orders SET state = 'expired' WHERE order_id = $1 AND state = 'awaiting_payment' RETURNING order_id",
                order_id,
            )
            if updated is None:
                # already moved on (webhook won the race) — not an error
                return ExpiryOutcome(expired=False, late_case_opened=False)
            event_id = await journal.append_event(
                conn,
                event_name="payment.expired",
                aggregate_type="order",
                aggregate_id=order_id,
                transition_id="OP-04",
                customer_visible=True,
            )
            await journal.enqueue_outbox(
                conn, order_id=order_id, journal_event_id=event_id, job_type="payment_expired_email"
            )
        return ExpiryOutcome(expired=True, late_case_opened=False)

    async def _open_late_case_from_reconciliation(
        self,
        *,
        order_id: str,
        provider_charge_id: str | None,
        provider_status: str | None,
    ) -> bool:
        """OP-F08 — reconciliation found a charge no webhook ever delivered.

        OP-F04/OP-F05 reach a late case because a signed event arrived LATE.
        This is the case where the event never arrives at all: OP-04 asks the
        provider its own question and the provider answers "there is a
        charge". Before this existed the answer went to a `logger.warning`
        and nowhere else — the order stayed in `awaiting_payment` while the
        provider held the customer's money, and no human was ever told.

        The order KEEPS `awaiting_payment`: only a signed webhook may write
        `paid`, and OP-F01 rejects every other writer, reconciliation
        included. What changes is that the case becomes VISIBLE and
        refundable — `late_case_open` is the field `resolveLateOrder` and the
        staff page already read, and until now nothing ever wrote it from
        this path.

        One alarm per case, never one per scheduler tick: the UPDATE is a
        compare-and-set, and only the tick that actually wins it appends the
        journal event the outbox job hangs off (`UNIQUE(journal_event_id,
        job_type)` does the rest).

        ALL THREE predicates are load-bearing; a cross-family review (Codex
        `gpt-5.6-sol`, read-only) found the first two missing and both were
        reproducible on disk:

        * `state = 'awaiting_payment'` — reconciliation selected this order a
          moment ago, but the real webhook can land in between. Without this
          the tick opens a late case on an order that has meanwhile reached
          `paid`, and `resolve_late_order` does not re-check state before
          refunding: a legitimate, fully reconciled payment becomes
          refundable. SM-G07 already demands every write be a CAS against the
          state it observed; this one was not.
        * `late_case_resolution IS NULL` — after staff close a case as
          `honoured`, the order KEEPS `awaiting_payment` and Xendit keeps
          answering "paid", so the next tick tried to reopen it. Migration
          284's CHECK forbids `(open = TRUE, resolution IS NOT NULL)`, so that
          is not a duplicate page, it is a `check_violation` every tick,
          forever, swallowed by the caller's `except`.
        * `late_case_open = FALSE` — the idempotence this method was written
          for.
        """

        async with self._pool.acquire() as conn, conn.transaction():
            opened = await conn.fetchrow(
                """
                UPDATE garuda_orders
                   SET late_case_open = TRUE, late_case_charge_id = $2
                 WHERE order_id = $1
                   AND state = 'awaiting_payment'
                   AND late_case_open = FALSE
                   AND late_case_resolution IS NULL
                RETURNING order_id
                """,
                order_id,
                provider_charge_id,
            )
            if opened is None:
                return False

            event_id = await journal.append_event(
                conn,
                event_name="payment.charge_detected_without_webhook",
                aggregate_type="order",
                aggregate_id=order_id,
                transition_id="OP-F08",
                customer_visible=False,
                detail={"charge_id": provider_charge_id, "provider_status": provider_status},
            )
            await journal.enqueue_outbox(
                conn,
                order_id=order_id,
                journal_event_id=event_id,
                job_type="staff_page_charge_without_webhook",
            )

        logger.warning(
            "garuda_orders: OP-F08 late case opened for %s — provider status %r reports a charge "
            "and no webhook ever arrived; staff paged",
            order_id,
            provider_status,
        )
        return True

    # ---- resolveLateOrder ------------------------------------------------

    async def resolve_late_order(
        self,
        *,
        order_id: str,
        resolution: str,
        staff_reference: str,
        idempotency_key_sha256: bytes,
        canonical_payload_sha256: bytes,
    ) -> tuple[dict[str, Any], bool]:
        async with self._pool.acquire() as conn:
            outcome = await idempotency.reserve(
                conn, key_sha256=idempotency_key_sha256, payload_sha256=canonical_payload_sha256
            )
            if outcome.replayed:
                assert outcome.response_body is not None
                return outcome.response_body, True

            # CORRECTED (refuter finding): the previous version read the row
            # WITHOUT a lock and closed with an unconditional UPDATE. Two
            # concurrent resolve_late_order calls with two DIFFERENT
            # Idempotency-Keys (two staff members racing the same case)
            # could both pass the `late_case_open` check and both call
            # provider.refund -> a double refund. FOR UPDATE serializes the
            # race at the row, and the closing UPDATE now re-asserts
            # `late_case_open = TRUE` (CAS) rather than writing unconditionally.
            # The lock is deliberately held across the external refund call
            # (a rare staff action, not a hot path) because correctness here
            # matters more than connection-hold time.
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT order_id, state, late_case_open, price_idr, late_case_charge_id "
                    "FROM garuda_orders WHERE order_id = $1 FOR UPDATE",
                    order_id,
                )
                if row is None:
                    raise OrderNotFound(order_id)
                if not row["late_case_open"]:
                    raise NoOpenLateCase(order_id)

                if resolution == "refunded_in_full":
                    try:
                        await self._provider.refund(
                            provider_charge_id=row["late_case_charge_id"],
                            idempotency_key=idempotency_key_sha256.hex(),
                        )
                    except RefundFailed as exc:
                        # Never record a resolution for a refund that did not happen.
                        raise PaymentProviderUnavailable(order_id) from exc

                closed = await conn.fetchrow(
                    """
                    UPDATE garuda_orders
                       SET late_case_open = FALSE, late_case_resolution = $2, late_case_staff_reference = $3
                     WHERE order_id = $1 AND late_case_open = TRUE
                     RETURNING order_id
                    """,
                    order_id,
                    resolution,
                    staff_reference,
                )
                if (
                    closed is None
                ):  # pragma: no cover - defensive, FOR UPDATE above should prevent this
                    raise NoOpenLateCase(order_id)
                event_id = await journal.append_event(
                    conn,
                    event_name="order.late_resolved",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    transition_id="OP-F05",
                    customer_visible=True,
                    detail={"resolution": resolution},
                )
                job_type = (
                    "practice_release"
                    if resolution == "honoured"
                    else "late_refund_confirmation_email"
                )
                await journal.enqueue_outbox(
                    conn, order_id=order_id, journal_event_id=event_id, job_type=job_type
                )

                final_state = row["state"]
                if resolution == "refunded_in_full" and final_state == (
                    OrderState.AWAITING_PAYMENT.value
                ):
                    # THE ORDER MUST LEAVE `awaiting_payment` HERE, and this is
                    # the whole point of the change. Until OP-F08 existed, every
                    # late case sat on an order that had already reached a
                    # terminal state, so a refund could not be followed by
                    # anything. OP-F08 opens a case on a LIVE order — and the
                    # page's own first move is "register the callback URL and
                    # replay the webhook". A fresh Opus gate session measured
                    # what that produces on the pre-cure code: refund, then
                    # replay, and OP-02 welcomes the webhook because the state
                    # it guards on is still `awaiting_payment` -> `paid`,
                    # practice minted, "payment received" emailed, on money we
                    # had just returned (`TRANSITION AFTER REFUND: OP-02 /
                    # PRACTICES: 1`).
                    #
                    # Writing the terminal state the refund actually means
                    # closes it WITHOUT a new guard: `handle_paid_event`'s
                    # OP-F04 branch already knows what a paid webhook for a
                    # refunded order is — keep `refunded`, open a remediation
                    # case carrying the LATE charge id, page staff, never
                    # release the practice. The cure is to let the existing
                    # machinery see the truth, not to add a second rule beside
                    # it.
                    #
                    # OP-05 is `awaiting_payment -> refunded` in this
                    # repository's own state machine (`state_machine.py`), so
                    # no new transition id and no migration: the journal CHECK
                    # already admits it. The event NAME is new because the
                    # existing OP-05 event (`payment.refunded_out_of_order`)
                    # says a refund webhook arrived before its paid event, and
                    # nothing arrived here — staff called the provider.
                    moved = await conn.fetchrow(
                        """
                        UPDATE garuda_orders
                           SET state = 'refunded'
                         WHERE order_id = $1 AND state = 'awaiting_payment'
                        RETURNING order_id
                        """,
                        order_id,
                    )
                    if moved is not None:
                        final_state = OrderState.REFUNDED.value
                        await journal.append_event(
                            conn,
                            event_name="payment.refunded_after_late_case",
                            aggregate_type="order",
                            aggregate_id=order_id,
                            transition_id="OP-05",
                            customer_visible=True,
                            detail={"staff_reference": staff_reference},
                        )

            response_body = {
                "order_id": order_id,
                "order_state": final_state,
                "resolution": resolution,
            }
            await idempotency.complete(
                conn,
                key_sha256=idempotency_key_sha256,
                response_status=200,
                response_body=response_body,
            )
        return response_body, False


__all__ = ["ExpiryOutcome", "GarudaOrderRepository"]
