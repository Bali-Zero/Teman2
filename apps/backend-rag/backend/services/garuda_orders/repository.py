"""GARUDA VOA order/payment repository — STATE-MACHINE.md order half.

Every write here follows SM-G07: compare-and-set against the source state,
append an immutable journal event, and enqueue outbox work, ALL inside one
transaction. `garuda_orders`'s own trigger (`guard_garuda_order_state_
transition`) is defense-in-depth behind the CAS `WHERE state = $expected`,
not a substitute for it — the CAS is what makes a concurrent duplicate
webhook see 0 rows updated instead of racing the trigger.
"""

from __future__ import annotations

import logging
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
from backend.services.payments.port import (
    NormalizedFailureEvent,
    NormalizedPaidEvent,
    NormalizedRefundEvent,
    PaymentProvider,
    RefundFailed,
)

logger = logging.getLogger(__name__)

_CHECKOUT_TTL_MINUTES = 60


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
                    order_id = journal.new_opaque_id("ord")
                    async with conn.transaction():
                        await conn.execute(
                            """
                            INSERT INTO garuda_orders
                                (order_id, result_id_ref, case_type, applicant_full_name,
                                 applicant_email, applicant_phone, applicant_passport_number,
                                 price_idr, price_catalogue_key)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            """,
                            order_id,
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
                            aggregate_id=order_id,
                            transition_id="OP-00",
                            customer_visible=False,
                            idempotency_key_digest=idempotency_key_sha256,
                            canonical_payload_digest=canonical_payload_sha256,
                            detail={"price_idr": price_idr, "price_catalogue_key": price_key},
                        )
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
        else:
            # Resume path: OP-01 already committed by a previous attempt.
            checkout_row = await self._pool.fetchrow(
                "SELECT provider_session_id FROM garuda_orders WHERE order_id = $1", order_id
            )
            # Sandbox-safe placeholder: the real checkout_url isn't persisted
            # (it's a provider capability, never journal/DB content per
            # SM-G03) — a genuine resume-after-crash re-fetches it from the
            # provider by provider_session_id. Kept minimal here; flagged in
            # the PR report as a follow-up rather than guessed.
            checkout_url = (
                f"pending-resume:{checkout_row['provider_session_id']}" if checkout_row else ""
            )

        response_body = {
            "order_id": order_id,
            "order_state": "awaiting_payment",
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

    async def record_browser_return_observation(self, *, order_id: str, return_nonce: str) -> None:
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE garuda_orders
                   SET browser_observation = 'browser_return_observed', browser_return_nonce = $2
                 WHERE order_id = $1 AND browser_return_nonce IS DISTINCT FROM $2
                 RETURNING order_id
                """,
                order_id,
                return_nonce,
            )
            if row is None:
                exists = await conn.fetchval(
                    "SELECT 1 FROM garuda_orders WHERE order_id = $1", order_id
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
                await conn.execute(
                    "UPDATE garuda_payment_inbox SET outcome = 'quarantined', processed_at = statement_timestamp() WHERE provider = 'xendit' AND provider_event_id = $1",
                    event.provider_event_id,
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
                await conn.execute(
                    "UPDATE garuda_payment_inbox SET outcome = 'quarantined', processed_at = statement_timestamp() WHERE provider = 'xendit' AND provider_event_id = $1",
                    event.provider_event_id,
                )
                return "OP-F03"

            if state == OrderState.AWAITING_PAYMENT.value:
                await conn.execute(
                    """
                    UPDATE garuda_orders SET state = 'paid', provider_charge_id = $2
                     WHERE order_id = $1 AND state = 'awaiting_payment'
                    """,
                    order_id,
                    event.provider_charge_id,
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
                await conn.execute(
                    "UPDATE garuda_orders SET late_case_open = TRUE WHERE order_id = $1 AND late_case_open = FALSE",
                    order_id,
                )
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
                await conn.execute(
                    """
                    UPDATE garuda_orders
                       SET late_case_open = TRUE, late_case_charge_id = $2
                     WHERE order_id = $1 AND late_case_open = FALSE
                    """,
                    order_id,
                    event.provider_charge_id,
                )
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
                await conn.execute(
                    """
                    UPDATE garuda_orders
                       SET late_case_open = TRUE, late_case_charge_id = $2
                     WHERE order_id = $1 AND late_case_open = FALSE
                    """,
                    order_id,
                    event.provider_charge_id,
                )
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
                await conn.execute(
                    "UPDATE garuda_payment_inbox SET outcome = 'quarantined', processed_at = statement_timestamp() WHERE provider = 'xendit' AND provider_event_id = $1",
                    event.provider_event_id,
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
                await conn.execute(
                    "UPDATE garuda_payment_inbox SET outcome = 'quarantined', processed_at = statement_timestamp() WHERE provider = 'xendit' AND provider_event_id = $1",
                    event.provider_event_id,
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
                await conn.execute(
                    "UPDATE garuda_payment_inbox SET outcome = 'quarantined', processed_at = statement_timestamp() WHERE provider = 'xendit' AND provider_event_id = $1",
                    event.provider_event_id,
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

    async def expire_if_unpaid(self, *, order_id: str, provider_session_id: str) -> bool:
        confirmed_unpaid = await self._provider.confirm_no_successful_charge(
            provider_session_id=provider_session_id
        )
        if not confirmed_unpaid:
            logger.warning(
                "garuda_orders: reconciliation found a possible drift for %s — provider reports a charge, "
                "our webhook has not arrived; leaving state alone for the webhook to reconcile",
                order_id,
            )
            return False
        async with self._pool.acquire() as conn, conn.transaction():
            updated = await conn.fetchrow(
                "UPDATE garuda_orders SET state = 'expired' WHERE order_id = $1 AND state = 'awaiting_payment' RETURNING order_id",
                order_id,
            )
            if updated is None:
                return False  # already moved on (webhook won the race) — not an error
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

            response_body = {
                "order_id": order_id,
                "order_state": row["state"],
                "resolution": resolution,
            }
            await idempotency.complete(
                conn,
                key_sha256=idempotency_key_sha256,
                response_status=200,
                response_body=response_body,
            )
        return response_body, False


__all__ = ["GarudaOrderRepository"]
