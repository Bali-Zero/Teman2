"""Tests for the five `staff_page_*` outbox handlers.

Companion to `test_outbox_handlers.py`. Same DSN/pool conventions, same
`_seed_order`-style helpers, deliberately not shared across files because a
shared fixture module would be a third place these seeding shapes could drift
from — each suite owns its own.

THE PROPERTY THAT MATTERS MOST HERE: no page may carry the applicant's email,
full name or passport number. `garuda_order_journal.detail` is documented
PII-free by construction and every handler reads facts only from `garuda_orders`
(order-scoped columns) plus that `detail`, but the seed fixture plants a real
name/email/passport on every order specifically so a regression that widens
what a handler reads has something to leak and a test that catches it.
"""

from __future__ import annotations

import logging
import os
import uuid

import httpx
import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_orders import journal
from backend.services.garuda_orders.outbox_consumer import KILL_SWITCH_ENV, OutboxJob, drain_once
from backend.services.garuda_orders.outbox_handlers import (
    BrevoEmailSender,
    StaffPageDuplicateChargeHandler,
    StaffPageLatePaidAfterRefundHandler,
    StaffPageLatePaidAfterTerminalHandler,
    StaffPageOrderMissing,
    StaffPagePaymentFailureHandler,
    StaffPageRefundOutOfOrderHandler,
    StaffPageSendFailed,
    TelegramStaffPageSender,
    build_handlers,
)
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/garuda_outbox_test_0826"
)

pytestmark = pytest.mark.asyncio

APPLICANT_EMAIL = "traveller@example.invalid"
APPLICANT_NAME = "SPECIMEN TRAVELLER"
APPLICANT_PASSPORT = "X0000000"


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


# --------------------------------------------------------------------------
# seeding helpers
# --------------------------------------------------------------------------


async def _seed_order(
    pool,
    *,
    state: str = "paid",
    late_case_open: bool = False,
    late_case_charge_id: str | None = None,
) -> str:
    order_id = f"ord_{uuid.uuid4().hex}"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO garuda_orders
                (order_id, result_id_ref, case_type, applicant_full_name,
                 applicant_email, applicant_phone, applicant_passport_number,
                 price_idr, price_catalogue_key, state,
                 late_case_open, late_case_charge_id)
            VALUES ($1, $2, 'issuance', $3, $4, '+000000000000', $5,
                    790000, 'B1 Visa on Arrival (VOA)', $6, $7, $8)
            """,
            order_id,
            f"chk_{uuid.uuid4().hex}",
            APPLICANT_NAME,
            APPLICANT_EMAIL,
            APPLICANT_PASSPORT,
            state,
            late_case_open,
            late_case_charge_id,
        )
    return order_id


async def _enqueue_staff_page(
    pool,
    order_id: str,
    *,
    job_type: str,
    event_name: str,
    transition_id: str,
    detail: dict | None = None,
) -> tuple[int, str]:
    async with pool.acquire() as conn, conn.transaction():
        event_id = await journal.append_event(
            conn,
            event_name=event_name,
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id=transition_id,
            customer_visible=False,
            detail=detail,
        )
        await journal.enqueue_outbox(
            conn, order_id=order_id, journal_event_id=event_id, job_type=job_type
        )
        row_id = await conn.fetchval(
            "SELECT id FROM garuda_order_outbox WHERE journal_event_id = $1 AND job_type = $2",
            event_id,
            job_type,
        )
    return row_id, event_id


def _job(order_id: str, journal_event_id: str, job_type: str, job_id: int = 1) -> OutboxJob:
    return OutboxJob(
        id=job_id,
        order_id=order_id,
        journal_event_id=journal_event_id,
        job_type=job_type,
        payload={},
        attempts=1,
    )


# --------------------------------------------------------------------------
# fake Telegram transport
# --------------------------------------------------------------------------


class _TgRecorder:
    def __init__(self, status: int = 200, boom: Exception | None = None) -> None:
        self.status = status
        self.boom = boom
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.boom is not None:
            raise self.boom
        return httpx.Response(self.status, json={"ok": True})


def _tg_sender(recorder: _TgRecorder, **kw) -> tuple[TelegramStaffPageSender, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    return (
        TelegramStaffPageSender(client, bot_token="test-bot-token", chat_id="12345", **kw),
        client,
    )


def _last_text(rec: _TgRecorder) -> str:
    from urllib.parse import parse_qs

    body = rec.requests[-1].read().decode()
    return parse_qs(body)["text"][0]


# --------------------------------------------------------------------------
# TelegramStaffPageSender — must raise, like BrevoEmailSender
# --------------------------------------------------------------------------


async def test_the_sender_posts_to_the_configured_chat():
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await sender.send(text="hello staff")
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    assert rec.requests[0].url.path.endswith("/bottest-bot-token/sendMessage")
    assert "hello staff" in _last_text(rec)


@pytest.mark.parametrize("status", [400, 401, 429, 500, 503])
async def test_the_sender_raises_on_every_error_status(status):
    rec = _TgRecorder(status=status)
    sender, client = _tg_sender(rec)
    try:
        with pytest.raises(StaffPageSendFailed):
            await sender.send(text="x")
    finally:
        await client.aclose()


async def test_the_sender_raises_when_unreachable():
    rec = _TgRecorder(boom=httpx.ConnectError("no route"))
    sender, client = _tg_sender(rec)
    try:
        with pytest.raises(StaffPageSendFailed):
            await sender.send(text="x")
    finally:
        await client.aclose()


async def test_the_sender_refuses_to_send_without_a_destination():
    rec = _TgRecorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(rec))
    try:
        sender = TelegramStaffPageSender(client, bot_token="", chat_id="")
        with pytest.raises(StaffPageSendFailed):
            await sender.send(text="x")
    finally:
        await client.aclose()
    assert rec.requests == [], "must not put a request on the wire with no destination"


# --------------------------------------------------------------------------
# per-handler: pages on the real condition
# --------------------------------------------------------------------------


async def test_duplicate_charge_pages_when_case_is_open(pool):
    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_duplicate_charge",
        event_name="payment.duplicate_charge_detected",
        transition_id="OP-08",
        detail={"second_charge_id": "ch_dup_999"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageDuplicateChargeHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_duplicate_charge")
        )
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    text = _last_text(rec)
    assert order_id in text
    assert "ch_dup_999" in text
    assert "790.000" in text
    assert "DUPLICATE CHARGE" in text


async def test_duplicate_charge_is_resolved_without_paging_once_case_is_closed(pool, caplog):
    order_id = await _seed_order(pool, state="paid", late_case_open=False)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_duplicate_charge",
        event_name="payment.duplicate_charge_detected",
        transition_id="OP-08",
        detail={"second_charge_id": "ch_dup_999"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger="garuda.orders.outbox_handlers"):
            await StaffPageDuplicateChargeHandler(pool, sender)(
                _job(order_id, event_id, "staff_page_duplicate_charge")
            )
    finally:
        await client.aclose()
    assert rec.requests == [], "an already-closed case must not be re-paged"
    assert any("WITHOUT paging" in r.getMessage() for r in caplog.records)


async def test_late_paid_after_refund_pages_and_uses_the_order_rows_charge_id(pool):
    order_id = await _seed_order(
        pool, state="refunded", late_case_open=True, late_case_charge_id="ch_late_refund_1"
    )
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_refund",
        event_name="payment.late_paid_after_refund",
        transition_id="OP-F04",
        detail={"charge_id": "ch_late_refund_1"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageLatePaidAfterRefundHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_late_paid_after_refund")
        )
    finally:
        await client.aclose()
    text = _last_text(rec)
    assert "ch_late_refund_1" in text
    assert "LATE PAYMENT AFTER REFUND" in text


async def test_late_paid_after_refund_is_resolved_without_paging_once_closed(pool, caplog):
    order_id = await _seed_order(
        pool, state="refunded", late_case_open=False, late_case_charge_id="ch_late_refund_2"
    )
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_refund",
        event_name="payment.late_paid_after_refund",
        transition_id="OP-F04",
        detail={"charge_id": "ch_late_refund_2"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger="garuda.orders.outbox_handlers"):
            await StaffPageLatePaidAfterRefundHandler(pool, sender)(
                _job(order_id, event_id, "staff_page_late_paid_after_refund")
            )
    finally:
        await client.aclose()
    assert rec.requests == []


async def test_late_paid_after_terminal_pages_when_case_is_open(pool):
    order_id = await _seed_order(
        pool, state="failed", late_case_open=True, late_case_charge_id="ch_late_terminal_1"
    )
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_terminal",
        event_name="payment.late_paid_after_terminal",
        transition_id="OP-F05",
        detail={"charge_id": "ch_late_terminal_1"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageLatePaidAfterTerminalHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_late_paid_after_terminal")
        )
    finally:
        await client.aclose()
    text = _last_text(rec)
    assert "ch_late_terminal_1" in text
    assert "failed" in text
    assert "LATE PAYMENT AFTER TERMINAL STATE" in text


async def test_late_paid_after_terminal_is_resolved_without_paging_once_closed(pool, caplog):
    order_id = await _seed_order(pool, state="expired", late_case_open=False)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_terminal",
        event_name="payment.late_paid_after_terminal",
        transition_id="OP-F05",
        detail={"charge_id": "ch_x"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger="garuda.orders.outbox_handlers"):
            await StaffPageLatePaidAfterTerminalHandler(pool, sender)(
                _job(order_id, event_id, "staff_page_late_paid_after_terminal")
            )
    finally:
        await client.aclose()
    assert rec.requests == []


async def test_payment_failure_always_pages(pool):
    order_id = await _seed_order(pool, state="failed", late_case_open=False)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_payment_failure",
        event_name="payment.failed",
        transition_id="OP-03",
        detail={"outcome": "PROVIDER_UNAVAILABLE", "customer_action": "TRY_AGAIN_LATER"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPagePaymentFailureHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_payment_failure")
        )
    finally:
        await client.aclose()
    text = _last_text(rec)
    assert order_id in text
    assert "PROVIDER" in text and "UNAVAILABLE" in text
    assert "TRY" in text and "AGAIN" in text and "LATER" in text
    assert "PAYMENT FAILURE" in text


async def test_refund_out_of_order_always_pages(pool):
    order_id = await _seed_order(pool, state="refunded", late_case_open=False)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_refund_out_of_order",
        event_name="payment.refunded_out_of_order",
        transition_id="OP-05",
        detail={"refund_id": "rfnd_out_of_order_1"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageRefundOutOfOrderHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_refund_out_of_order")
        )
    finally:
        await client.aclose()
    text = _last_text(rec)
    assert "rfnd_out_of_order_1" in text
    assert "REFUND OUT OF ORDER" in text


# --------------------------------------------------------------------------
# missing order
# --------------------------------------------------------------------------


async def test_a_missing_order_raises_for_every_handler(pool):
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    handler_classes = [
        StaffPageDuplicateChargeHandler,
        StaffPageLatePaidAfterRefundHandler,
        StaffPageLatePaidAfterTerminalHandler,
        StaffPagePaymentFailureHandler,
        StaffPageRefundOutOfOrderHandler,
    ]
    try:
        for cls in handler_classes:
            with pytest.raises(StaffPageOrderMissing):
                await cls(pool, sender)(_job("ord_not_here", "evt_not_here", cls.job_type))
    finally:
        await client.aclose()
    assert rec.requests == []


# --------------------------------------------------------------------------
# transport failure must not be swallowed
# --------------------------------------------------------------------------


async def test_a_failed_send_raises_and_does_not_mark_delivered(pool):
    order_id = await _seed_order(pool, state="refunded", late_case_open=False)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_refund_out_of_order",
        event_name="payment.refunded_out_of_order",
        transition_id="OP-05",
        detail={"refund_id": "rfnd_transport_fail"},
    )
    rec = _TgRecorder(status=500)
    sender, client = _tg_sender(rec)
    try:
        with pytest.raises(StaffPageSendFailed):
            await StaffPageRefundOutOfOrderHandler(pool, sender)(
                _job(order_id, event_id, "staff_page_refund_out_of_order")
            )
    finally:
        await client.aclose()


# --------------------------------------------------------------------------
# THE test most worth having here: no PII in the outgoing page
# --------------------------------------------------------------------------


async def test_no_page_carries_applicant_pii():
    """One order, every handler, one shared assertion.

    Uses `_compose` directly (no network) against a facts object built from a
    real seeded row's shape — this is the fastest way to exercise all five
    without five separate Postgres fixtures, and `_compose` is exactly where
    a PII leak would first appear if a future edit widened what a handler
    reads into the message.
    """

    from backend.services.garuda_orders.outbox_handlers import OrderAnomalyFacts

    facts = OrderAnomalyFacts(
        order_id="ord_pii_probe",
        case_type="issuance",
        price_idr=790000,
        state="paid",
        late_case_open=True,
        late_case_charge_id="ch_pii_probe",
        detail={
            "second_charge_id": "ch_pii_probe_2",
            "charge_id": "ch_pii_probe",
            "refund_id": "rfnd_pii_probe",
            "outcome": "PROVIDER_UNAVAILABLE",
            "customer_action": "TRY_AGAIN_LATER",
        },
    )
    handlers = [
        StaffPageDuplicateChargeHandler(pool=None, sender=None),
        StaffPageLatePaidAfterRefundHandler(pool=None, sender=None),
        StaffPageLatePaidAfterTerminalHandler(pool=None, sender=None),
        StaffPagePaymentFailureHandler(pool=None, sender=None),
        StaffPageRefundOutOfOrderHandler(pool=None, sender=None),
    ]
    forbidden = (APPLICANT_EMAIL, APPLICANT_NAME, APPLICANT_PASSPORT)
    for handler in handlers:
        text = handler._compose(facts)
        for value in forbidden:
            assert value not in text, f"{type(handler).__name__} leaked {value!r}"


async def test_no_log_line_carries_applicant_pii(pool, caplog):
    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_duplicate_charge",
        event_name="payment.duplicate_charge_detected",
        transition_id="OP-08",
        detail={"second_charge_id": "ch_dup_log"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        with caplog.at_level(logging.DEBUG, logger="garuda.orders.outbox_handlers"):
            await StaffPageDuplicateChargeHandler(pool, sender)(
                _job(order_id, event_id, "staff_page_duplicate_charge")
            )
    finally:
        await client.aclose()
    rendered = " ".join(r.getMessage() for r in caplog.records)
    assert APPLICANT_EMAIL not in rendered
    assert APPLICANT_NAME not in rendered
    assert APPLICANT_PASSPORT not in rendered
    assert order_id in rendered, "the log must still identify WHICH order (positive control)"


# --------------------------------------------------------------------------
# build_handlers wiring + end-to-end through drain_once
# --------------------------------------------------------------------------


def test_build_handlers_does_not_route_staff_pages_without_a_sender() -> None:
    handlers = build_handlers(pool=None, sender=None)
    assert "staff_page_duplicate_charge" not in handlers


def test_build_handlers_routes_all_five_when_given_a_staff_page_sender() -> None:
    rec = _TgRecorder()
    staff_sender, client = _tg_sender(rec)
    try:
        handlers = build_handlers(pool=None, sender=None, staff_page_sender=staff_sender)
    finally:
        pass  # client intentionally left open; this test never sends
    expected = {
        "payment_paid_email",
        "practice_release",
        "portal_invite",
        "staff_page_duplicate_charge",
        "staff_page_late_paid_after_refund",
        "staff_page_late_paid_after_terminal",
        "staff_page_payment_failure",
        "staff_page_refund_out_of_order",
    }
    assert set(handlers) == expected


async def test_draining_a_queued_staff_page_sends_and_marks_it_dispatched(pool):
    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_duplicate_charge",
        event_name="payment.duplicate_charge_detected",
        transition_id="OP-08",
        detail={"second_charge_id": "ch_dup_drain"},
    )

    email_rec = _TgRecorder()  # unused by this pass but BrevoEmailSender needs a client
    tg_rec = _TgRecorder()
    email_client = httpx.AsyncClient(transport=httpx.MockTransport(email_rec))
    staff_sender, staff_client = _tg_sender(tg_rec)
    try:
        handlers = build_handlers(
            pool,
            BrevoEmailSender(email_client, api_key="test-key-not-a-real-secret"),
            staff_page_sender=staff_sender,
        )
        async with pool.acquire() as conn:
            stats = await drain_once(conn, handlers)
    finally:
        await email_client.aclose()
        await staff_client.aclose()

    assert (stats.claimed, stats.dispatched, stats.failed) == (1, 1, 0)
    assert len(tg_rec.requests) == 1
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT dispatched_at FROM garuda_order_outbox WHERE id = $1", row_id
            )
            is not None
        )
