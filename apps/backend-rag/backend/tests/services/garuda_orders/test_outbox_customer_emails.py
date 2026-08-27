"""Tests for the five customer-email outbox handlers added alongside
`payment_paid_email`: `checkout_ready_email`, `payment_failed_email`,
`payment_expired_email`, `refund_email` and `practice_received_email`.

Sibling to `test_outbox_handlers.py`, which already covers the sender's HTTP
layer and `PaymentPaidEmailHandler` in full — this file exercises only what
is new: each handler's own state guard (a job whose order has moved on since
it was enqueued must resolve WITHOUT sending, never raise) and the shared
"missing order raises" contract. Guilt and innocence for every handler, per
the module's own `_STATES_WORTH_*` reasoning in `outbox_handlers.py`.
"""

from __future__ import annotations

import logging
import os
import uuid

import httpx
import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_orders import journal
from backend.services.garuda_orders.outbox_consumer import KILL_SWITCH_ENV, OutboxJob
from backend.services.garuda_orders.outbox_handlers import (
    CheckoutReadyEmailHandler,
    EmailSendFailed,
    PaymentExpiredEmailHandler,
    PaymentFailedEmailHandler,
    PracticeReceivedEmailHandler,
    RefundEmailHandler,
)
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/garuda_outbox_test_0826"
)

pytestmark = pytest.mark.asyncio

RECIPIENT = "traveller@example.invalid"
LOGGER_NAME = "garuda.orders.outbox_handlers"


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


@pytest.fixture
async def pool():
    try:
        p = await create_prod_shaped_pool(_DSN, min_size=1, max_size=4)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(f"no reachable Postgres in CI at {_DSN}: {exc}")
        pytest.skip(f"no reachable Postgres at {_DSN}: {exc}")
    try:
        async with p.acquire() as conn:
            await conn.execute(
                "TRUNCATE garuda_practices, garuda_order_outbox, "
                "garuda_order_journal, garuda_orders, garuda_voa_check_results "
                "CASCADE"
            )
        yield p
    finally:
        await p.close()


@pytest.fixture(autouse=True)
def armed(monkeypatch):
    monkeypatch.setenv(KILL_SWITCH_ENV, "true")
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-key-not-a-real-secret")


class _Recorder:
    """Captures what the sender actually put on the wire."""

    def __init__(self, status: int = 201) -> None:
        self.status = status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json={"ok": True})


def _sender(recorder: _Recorder):
    from backend.services.garuda_orders.outbox_handlers import BrevoEmailSender

    client = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    return BrevoEmailSender(client, api_url="https://notifications.invalid/send"), client


async def _seed_order(pool, *, state: str, email: str = RECIPIENT) -> str:
    order_id = f"ord_{uuid.uuid4().hex}"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO garuda_orders
                (order_id, result_id_ref, case_type, applicant_full_name,
                 applicant_email, applicant_phone, applicant_passport_number,
                 price_idr, price_catalogue_key, state)
            VALUES ($1, $2, 'issuance', 'SPECIMEN TRAVELLER', $3,
                    '+000000000000', 'X0000000', 790000,
                    'B1 Visa on Arrival (VOA)', $4)
            """,
            order_id,
            f"chk_{uuid.uuid4().hex}",
            email,
            state,
        )
    return order_id


async def _seed_practice(pool, order_id: str) -> str:
    """`garuda_practices.source_paid_journal_event_id` is FK'd to
    `garuda_order_journal`, so a real OP-02 event must exist first — this
    mirrors `mint_received_practice`'s own precondition rather than a
    synthetic id no row backs."""

    practice_id = f"prac_{uuid.uuid4().hex}"
    async with pool.acquire() as conn, conn.transaction():
        event_id = await journal.append_event(
            conn,
            event_name="payment.paid",
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id="OP-02",
            customer_visible=True,
        )
        await conn.execute(
            """
            INSERT INTO garuda_practices (practice_id, order_id, source_paid_journal_event_id)
            VALUES ($1, $2, $3)
            """,
            practice_id,
            order_id,
            event_id,
        )
    return practice_id


def _job(order_id: str, job_type: str, payload: dict | None = None) -> OutboxJob:
    return OutboxJob(
        id=1,
        order_id=order_id,
        journal_event_id="evt_specimen",
        job_type=job_type,
        payload=payload or {},
        attempts=1,
    )


# --------------------------------------------------------------------------
# checkout_ready_email
# --------------------------------------------------------------------------


async def test_checkout_ready_sends_while_awaiting_payment(pool):
    order_id = await _seed_order(pool, state="awaiting_payment")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await CheckoutReadyEmailHandler(pool, sender)(
            _job(order_id, "checkout_ready_email", {"checkout_url": "https://pay.invalid/x"})
        )
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    body = rec.requests[0].read().decode()
    assert RECIPIENT in body
    assert "https://pay.invalid/x" in body


async def test_checkout_ready_resolves_without_sending_once_paid(pool, caplog):
    order_id = await _seed_order(pool, state="paid")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            await CheckoutReadyEmailHandler(pool, sender)(
                _job(order_id, "checkout_ready_email", {"checkout_url": "https://pay.invalid/x"})
            )
    finally:
        await client.aclose()
    assert rec.requests == [], "a paid order must not be re-invited to pay"
    assert any(
        "checkout_ready_email resolved WITHOUT sending" in r.getMessage() for r in caplog.records
    )


async def test_checkout_ready_raises_without_a_checkout_url(pool):
    order_id = await _seed_order(pool, state="awaiting_payment")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await CheckoutReadyEmailHandler(pool, sender)(_job(order_id, "checkout_ready_email"))
    finally:
        await client.aclose()
    assert rec.requests == []


async def test_checkout_ready_raises_on_a_missing_order(pool):
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await CheckoutReadyEmailHandler(pool, sender)(
                _job("ord_not_here", "checkout_ready_email", {"checkout_url": "https://x.invalid"})
            )
    finally:
        await client.aclose()


# --------------------------------------------------------------------------
# payment_failed_email
# --------------------------------------------------------------------------


async def test_payment_failed_sends_while_failed(pool):
    order_id = await _seed_order(pool, state="failed")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await PaymentFailedEmailHandler(pool, sender)(
            _job(order_id, "payment_failed_email", {"customer_action": "TRY_A_DIFFERENT_CARD"})
        )
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    body = rec.requests[0].read().decode()
    assert RECIPIENT in body
    assert "different card" in body.lower()


async def test_payment_failed_resolves_without_sending_when_still_awaiting_payment(pool, caplog):
    """A failure job for an order that is not (or no longer) `failed` — e.g.
    the CAS-guarded state update lost a race — must not tell the customer
    their payment failed."""

    order_id = await _seed_order(pool, state="awaiting_payment")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            await PaymentFailedEmailHandler(pool, sender)(
                _job(order_id, "payment_failed_email", {"customer_action": "TRY_AGAIN_LATER"})
            )
    finally:
        await client.aclose()
    assert rec.requests == []
    assert any(
        "payment_failed_email resolved WITHOUT sending" in r.getMessage() for r in caplog.records
    )


async def test_payment_failed_raises_on_a_missing_order(pool):
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await PaymentFailedEmailHandler(pool, sender)(
                _job("ord_not_here", "payment_failed_email", {"customer_action": "TRY_AGAIN_LATER"})
            )
    finally:
        await client.aclose()


# --------------------------------------------------------------------------
# payment_expired_email
# --------------------------------------------------------------------------


async def test_payment_expired_sends_while_expired(pool):
    order_id = await _seed_order(pool, state="expired")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await PaymentExpiredEmailHandler(pool, sender)(_job(order_id, "payment_expired_email"))
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    assert RECIPIENT in rec.requests[0].read().decode()


async def test_payment_expired_resolves_without_sending_once_paid(pool, caplog):
    """The reconciliation race this guards: `expire_if_unpaid` and the paid
    webhook can both be in flight; if the webhook wins first, the expiry job
    must not tell a paying customer their session expired."""

    order_id = await _seed_order(pool, state="paid")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            await PaymentExpiredEmailHandler(pool, sender)(_job(order_id, "payment_expired_email"))
    finally:
        await client.aclose()
    assert rec.requests == []
    assert any(
        "payment_expired_email resolved WITHOUT sending" in r.getMessage() for r in caplog.records
    )


async def test_payment_expired_raises_on_a_missing_order(pool):
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await PaymentExpiredEmailHandler(pool, sender)(
                _job("ord_not_here", "payment_expired_email")
            )
    finally:
        await client.aclose()


# --------------------------------------------------------------------------
# refund_email
# --------------------------------------------------------------------------


async def test_refund_sends_while_refunded(pool):
    order_id = await _seed_order(pool, state="refunded")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await RefundEmailHandler(pool, sender)(_job(order_id, "refund_email"))
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    body = rec.requests[0].read().decode()
    assert RECIPIENT in body
    assert "790.000" in body


async def test_refund_resolves_without_sending_when_still_paid(pool, caplog):
    """The mirror of `PaymentPaidEmailHandler`'s own refunded-order test: a
    refund job for an order that is (still) `paid` must not tell the customer
    money is coming back that never left."""

    order_id = await _seed_order(pool, state="paid")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            await RefundEmailHandler(pool, sender)(_job(order_id, "refund_email"))
    finally:
        await client.aclose()
    assert rec.requests == []
    assert any("refund_email resolved WITHOUT sending" in r.getMessage() for r in caplog.records)


async def test_refund_raises_on_a_missing_order(pool):
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await RefundEmailHandler(pool, sender)(_job("ord_not_here", "refund_email"))
    finally:
        await client.aclose()


# --------------------------------------------------------------------------
# practice_received_email
# --------------------------------------------------------------------------


async def test_practice_received_sends_for_a_paid_order_with_its_practice(pool):
    order_id = await _seed_order(pool, state="paid")
    await _seed_practice(pool, order_id)
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await PracticeReceivedEmailHandler(pool, sender)(
            _job(order_id, "practice_received_email")
        )
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    assert RECIPIENT in rec.requests[0].read().decode()


async def test_practice_received_resolves_without_sending_once_refunded(pool, caplog):
    """A practice, once minted, is never deleted — but if the order has since
    been refunded, "your application is now open with our team" reads as an
    active-service promise a refund just closed out. Must resolve, not send,
    and must not claim the practice itself was ever wrong."""

    order_id = await _seed_order(pool, state="refunded")
    await _seed_practice(pool, order_id)
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            await PracticeReceivedEmailHandler(pool, sender)(
                _job(order_id, "practice_received_email")
            )
    finally:
        await client.aclose()
    assert rec.requests == []
    assert any(
        "practice_received_email resolved WITHOUT sending" in r.getMessage()
        for r in caplog.records
    )


async def test_practice_received_raises_on_a_missing_order(pool):
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await PracticeReceivedEmailHandler(pool, sender)(
                _job("ord_not_here", "practice_received_email")
            )
    finally:
        await client.aclose()


async def test_practice_received_raises_when_the_practice_row_is_missing(pool):
    """A paid order with NO practice row is the shape `mint_received_practice`
    should never leave behind (the outbox row and the practice INSERT commit
    in the same transaction) — treat it the same as a missing order: raise,
    never mark delivered."""

    order_id = await _seed_order(pool, state="paid")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await PracticeReceivedEmailHandler(pool, sender)(
                _job(order_id, "practice_received_email")
            )
    finally:
        await client.aclose()
    assert rec.requests == []
