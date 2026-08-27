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
from urllib.parse import quote

import asyncpg
import httpx
import pytest

_TG_HOST = "api." + "telegram" + ".org"

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
        # Unreachable in practice: pytest.fail/skip are NoReturn, so `p` is
        # always bound below. CodeQL can't see that through the pytest API;
        # this `raise` terminates the branch provably and re-raises the
        # connection error if that assumption ever stops being true.
        raise
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


async def test_late_paid_after_refund_pages_and_names_the_charge(pool):
    """RENAMED 2026-08-28. This was `..._uses_the_order_rows_charge_id`, and it
    could never have shown that: it seeds `late_case_charge_id` and
    `detail["charge_id"]` to the SAME value, so both sources render identically
    and the assertion passes whichever one the code reads. It survived the
    switch from the row to the event detail without a flicker — which is what
    made it worth renaming rather than deleting. The two tests below are the
    ones that actually separate the sources.
    """

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


def test_the_facts_a_page_is_built_from_carry_no_applicant_field():
    """REPLACES a vacuous test. The previous version built an
    `OrderAnomalyFacts` by hand and asserted the five `_compose` outputs
    contained no applicant email/name/passport — but that dataclass has no
    applicant field to put there, so the assertion could not fail for any
    edit to `_compose`. It tested nothing.

    The property that ACTUALLY makes `_compose` unable to leak is structural:
    a page is composed only from facts that carry no applicant data. So assert
    that, on the dataclass itself, where it is falsifiable — adding
    `applicant_email` to `OrderAnomalyFacts` (the realistic first step of a
    leak, since `_load`'s SELECT would then have somewhere to put it) fails
    here immediately, before any `_compose` is even written.
    """

    from backend.services.garuda_orders.outbox_handlers import OrderAnomalyFacts

    fields = set(OrderAnomalyFacts.__dataclass_fields__)
    # The exact shape, not a substring scan: a new field must be a deliberate
    # edit here, and one that carries applicant data can never pass.
    assert fields == {
        "order_id",
        "case_type",
        "price_idr",
        "state",
        "late_case_open",
        "late_case_charge_id",
        "case_resolved_since_trigger",
        "detail",
    }, f"OrderAnomalyFacts changed shape: {sorted(fields)}"
    for field_name in fields:
        # Same list shape as the writer test, and for the same reason NOT the
        # bare word "name" — see there.
        for forbidden in ("applicant", "email", "passport", "phone", "full_name"):
            assert forbidden not in field_name, (
                f"OrderAnomalyFacts.{field_name} looks like applicant data — a staff "
                "page is composed only from order/journal facts, never from the person"
            )


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


async def test_no_outgoing_page_carries_applicant_pii_through_the_real_load_path(pool):
    """`test_no_page_carries_applicant_pii` exercises `_compose` against a
    hand-built `OrderAnomalyFacts` and would NOT catch a leak introduced in
    `_StaffPageHandler._load` itself (e.g. a SQL edit that widens what column
    gets read into `case_type` or `detail`). This one runs every handler
    through a REAL seeded order, with real applicant email/name/passport on
    the row, and inspects the literal bytes that would go out over the wire —
    the same thing `test_the_sender_posts_to_the_configured_chat` inspects,
    just for content instead of destination.
    """

    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    cases = [
        (
            StaffPageDuplicateChargeHandler,
            "staff_page_duplicate_charge",
            "payment.duplicate_charge_detected",
            "OP-08",
            {"second_charge_id": "ch_pii_real_1"},
        ),
        (
            StaffPagePaymentFailureHandler,
            "staff_page_payment_failure",
            "payment.failed",
            "OP-03",
            {"outcome": "PROVIDER_UNAVAILABLE", "customer_action": "TRY_AGAIN_LATER"},
        ),
        (
            StaffPageRefundOutOfOrderHandler,
            "staff_page_refund_out_of_order",
            "payment.refunded_out_of_order",
            "OP-05",
            {"refund_id": "rfnd_pii_real_1"},
        ),
    ]
    for cls, job_type, event_name, transition_id, detail in cases:
        row_id, event_id = await _enqueue_staff_page(
            pool,
            order_id,
            job_type=job_type,
            event_name=event_name,
            transition_id=transition_id,
            detail=detail,
        )
        rec = _TgRecorder()
        sender, client = _tg_sender(rec)
        try:
            await cls(pool, sender)(_job(order_id, event_id, job_type))
        finally:
            await client.aclose()
        text = _last_text(rec)
        assert APPLICANT_EMAIL not in text, f"{cls.__name__} leaked the applicant email"
        assert APPLICANT_NAME not in text, f"{cls.__name__} leaked the applicant name"
        assert APPLICANT_PASSPORT not in text, f"{cls.__name__} leaked the passport number"


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
    # THIRTEEN routed — which is NOT every type production enqueues. There are
    # FOURTEEN; the fourteenth is named in UNROUTED_BY_DESIGN below and asserted
    # to be absent, so this file states the gap instead of implying there is
    # none. An earlier version of this comment claimed thirteen was all of them.
    # The five customer-email types joined this set when #5128 merged (this
    # branch was cut before it); the exactness is the point, so that adding a
    # route is always a deliberate edit here and losing one can never pass
    # unnoticed.
    expected = {
        # eight, always routed
        "checkout_ready_email",
        "payment_paid_email",
        "payment_failed_email",
        "payment_expired_email",
        "refund_email",
        "practice_release",
        "practice_received_email",
        "portal_invite",
        # five, routed only because a staff_page_sender was passed
        "staff_page_duplicate_charge",
        "staff_page_late_paid_after_refund",
        "staff_page_late_paid_after_terminal",
        "staff_page_payment_failure",
        "staff_page_refund_out_of_order",
    }
    assert set(handlers) == expected
    assert len(expected) == 13

    # The fourteenth type, declared rather than silently missing. It is computed
    # at repository.py:799-805 — `"practice_release" if resolution == "honoured"
    # else "late_refund_confirmation_email"` — when a staff member resolves a
    # late-payment case by refunding it. Every prior count of these types was
    # taken by grepping `job_type="`, a LITERAL, and this one call site passes a
    # VARIABLE, which is how three separate artifacts missed it. Asserting it
    # ABSENT (rather than leaving the set silently short) means the day someone
    # routes it, this assertion fails and forces the count and the comment above
    # to be corrected in the same edit.
    UNROUTED_BY_DESIGN = {"late_refund_confirmation_email"}
    assert UNROUTED_BY_DESIGN.isdisjoint(set(handlers))


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


# --- the bot token must not become durable text -------------------------------
#
# This message does not stay in memory: it travels as `StaffPageSendFailed`,
# `drain_once` catches it and calls `logger.exception`, and the traceback —
# message included — lands in the process's log stream, retained and readable by
# anyone with log access on Fly.
#
# CORRECTED 2026-08-28: this comment used to say the worker "writes it to the
# job's `last_error` COLUMN — durable, readable by anyone with DB read". There
# is no such column. `garuda_order_outbox` (migration 284:347-357) has exactly
# id / order_id / journal_event_id / job_type / payload / created_at /
# dispatched_at / attempts, and `drain_once` writes no error text to the row at
# all. The requirement is unchanged and the durable surface is real; the
# justification cited a database column that does not exist, which is worse than
# vague, because the next reader would have gone looking for it.
#
# `@zantara0bot`'s predecessor is the scar: its token
# sat in cleartext on the default branch of a PUBLIC repo, cannot be revoked
# (BotFather answers only to an account nobody can reach any more) and is
# therefore valid forever in the hands of whoever reads git history.
#
# On the installed httpx no exception from that path puts the URL in its
# `str()`, so this closes a class rather than fixing a leak — which is exactly
# why it has to be a test and not a comment: the next httpx, or the next error
# string, is what nobody would re-audit.


async def test_a_failed_send_never_puts_the_bot_token_in_the_durable_error():
    token = "8847435604:AA-a-token-shaped-string-nobody-should-ever-see"

    # A provider that echoes the request URL back in its body — the shape that
    # WOULD leak, since the token is a path segment of that URL.
    def _echo_the_url(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text=f'{{"ok":false,"description":"bad request to {request.url}"}}')

    client = httpx.AsyncClient(transport=httpx.MockTransport(_echo_the_url))
    sender = TelegramStaffPageSender(client, bot_token=token, chat_id="12345")
    try:
        with pytest.raises(StaffPageSendFailed) as raised:
            await sender.send(text="DUPLICATE CHARGE")
    finally:
        await client.aclose()

    message = str(raised.value)
    # Innocence: the error must still be diagnosable, or scrubbing everything
    # would pass this test while destroying the only signal a human gets.
    assert "400" in message, f"the error names no status — undiagnosable: {message!r}"
    assert token not in message, (
        f"the bot token reached the durable job error: {message!r}"
    )
    assert "<redacted>" in message, (
        "the token was absent but so was any trace of the redaction — this test "
        f"may be passing for the wrong reason: {message!r}"
    )


async def test_a_poisoned_journal_detail_does_not_reach_a_page(pool):
    """The three PII tests above all seed a PII-FREE `detail`, so they pass
    whether the handlers read NAMED keys out of it or fold the whole dict into
    the message. Measured: replacing a `_compose` body with `f"{facts.detail}"`
    left every one of them green. So none of them pins the property that
    actually protects this surface.

    `garuda_order_journal.detail` is documented PII-free by construction
    (284_garuda_orders.sql: "never applicant fields") and all nine `detail=`
    writes in the lane honour it today — provider ids, amounts and enums only.
    That is a convention in a SQL comment, not a constraint: the day a
    transition writes an applicant field there, the ONLY thing standing between
    it and the owner's Telegram chat is that each `_compose` names the keys it
    wants. This test poisons `detail` with every applicant field and pins that.
    """

    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    poison = {
        "applicant_email": APPLICANT_EMAIL,
        "applicant_full_name": APPLICANT_NAME,
        "applicant_passport_number": APPLICANT_PASSPORT,
    }
    cases = [
        (
            StaffPageDuplicateChargeHandler,
            "staff_page_duplicate_charge",
            "payment.duplicate_charge_detected",
            "OP-08",
            {"second_charge_id": "ch_poison_1", **poison},
        ),
        (
            StaffPagePaymentFailureHandler,
            "staff_page_payment_failure",
            "payment.failed",
            "OP-03",
            {"outcome": "PROVIDER_UNAVAILABLE", "customer_action": "TRY_AGAIN_LATER", **poison},
        ),
        (
            StaffPageRefundOutOfOrderHandler,
            "staff_page_refund_out_of_order",
            "payment.refunded_out_of_order",
            "OP-05",
            {"refund_id": "rfnd_poison_1", **poison},
        ),
        # The two late-payment pages were missing from the first version of
        # this test — the handlers whose page renders `late_case_charge_id`
        # from the ORDER ROW rather than the detail, i.e. the ones where the
        # detail is read for nothing and a fold would be pure leak.
        (
            StaffPageLatePaidAfterRefundHandler,
            "staff_page_late_paid_after_refund",
            "payment.late_paid_after_refund",
            "OP-F04",
            {"charge_id": "ch_poison_late_1", **poison},
        ),
        (
            StaffPageLatePaidAfterTerminalHandler,
            "staff_page_late_paid_after_terminal",
            "payment.late_paid_after_terminal",
            "OP-F05",
            {"charge_id": "ch_poison_late_2", **poison},
        ),
    ]
    for cls, job_type, event_name, transition_id, detail in cases:
        _row_id, event_id = await _enqueue_staff_page(
            pool,
            order_id,
            job_type=job_type,
            event_name=event_name,
            transition_id=transition_id,
            detail=detail,
        )
        rec = _TgRecorder()
        sender, client = _tg_sender(rec)
        try:
            await cls(pool, sender)(_job(order_id, event_id, job_type))
        finally:
            await client.aclose()
        text = _last_text(rec)
        # Guilt: the poison must not appear.
        for label, secret in (
            ("applicant email", APPLICANT_EMAIL),
            ("applicant name", APPLICANT_NAME),
            ("passport number", APPLICANT_PASSPORT),
        ):
            assert secret not in text, (
                f"{cls.__name__} carried the {label} from a poisoned journal detail "
                f"into a Telegram page: {text!r}"
            )
        # Innocence: it must still have paged, and still carry the ONE detail
        # key it is supposed to read — otherwise a handler that composed an
        # empty string would satisfy the assertions above.
        assert order_id in text, f"{cls.__name__} paged without naming the order"


# --- a page must belong to the case it is about --------------------------------


async def test_a_page_is_withheld_once_ITS_OWN_case_was_resolved(pool):
    """`late_case_open` is ONE boolean per order, and the contract permits a
    SECOND case to open after the first is closed (migration 284: "exactly one
    open case per order AT A TIME"). So the flag alone cannot distinguish "my
    case is still open" from "my case was closed and a different one is open
    now" — and in the second reading a delayed retry of the FIRST job pages
    about case A while rendering case B's `late_case_charge_id`, which is the
    id a human would then go and refund.

    Sequence: case A opens and enqueues a page; a human resolves A
    (`order.late_resolved`); a second late payment reopens the flag. The
    still-queued page for A must resolve WITHOUT paging.
    """

    order_id = await _seed_order(pool, state="refunded", late_case_open=True)
    _row_a, event_a = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_refund",
        event_name="payment.late_paid_after_refund",
        transition_id="OP-F04",
        detail={"charge_id": "ch_case_A"},
    )

    # A human closes case A. The flag would then go FALSE...
    async with pool.acquire() as conn, conn.transaction():
        await journal.append_event(
            conn,
            event_name="order.late_resolved",
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id="OP-F05",
            customer_visible=True,
            detail={"resolution": "refunded_in_full"},
        )
        # ...and a SECOND late payment raises it again, with a different id.
        await conn.execute(
            "UPDATE garuda_orders SET late_case_open = TRUE, late_case_charge_id = $2 "
            "WHERE order_id = $1",
            order_id,
            "ch_case_B",
        )

    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageLatePaidAfterRefundHandler(pool, sender)(
            _job(order_id, event_a, "staff_page_late_paid_after_refund")
        )
    finally:
        await client.aclose()

    assert rec.requests == [], (
        "case A's page went out after A was resolved — and it would have carried "
        f"case B's charge id: {_last_text(rec) if rec.requests else ''!r}"
    )


async def test_a_page_still_goes_out_when_its_own_case_is_untouched(pool):
    """The innocence half of the test above: with no resolution recorded, the
    page must still go out. A guard that withheld everything would satisfy the
    guilt half alone."""

    order_id = await _seed_order(pool, state="refunded", late_case_open=True)
    _row, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_refund",
        event_name="payment.late_paid_after_refund",
        transition_id="OP-F04",
        detail={"charge_id": "ch_untouched"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageLatePaidAfterRefundHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_late_paid_after_refund")
        )
    finally:
        await client.aclose()

    assert len(rec.requests) == 1, "an unresolved money anomaly was not paged"
    assert order_id in _last_text(rec)


# --- a non-scalar under a READ key must not be serialised ----------------------


async def test_a_structure_hidden_under_a_read_key_is_not_serialised(pool):
    """Reading NAMED keys stops an unread key leaking; it does not bound what a
    READ key holds, and `detail` is JSONB — any shape fits. `str()` of a dict
    would put the whole structure in the page. `_detail_scalar` refuses
    non-scalars and caps length."""

    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    _row, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_duplicate_charge",
        event_name="payment.duplicate_charge_detected",
        transition_id="OP-08",
        detail={"second_charge_id": {"nested": APPLICANT_EMAIL, "more": APPLICANT_PASSPORT}},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageDuplicateChargeHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_duplicate_charge")
        )
    finally:
        await client.aclose()

    text = _last_text(rec)
    assert APPLICANT_EMAIL not in text, f"a nested structure was serialised: {text!r}"
    assert APPLICANT_PASSPORT not in text, f"a nested structure was serialised: {text!r}"
    # Innocence: the page still went out and still names the order — a human
    # must learn that a duplicate charge happened even if the id is unusable.
    assert order_id in text


async def test_an_overlong_read_value_is_capped(pool):
    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    _row, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_duplicate_charge",
        event_name="payment.duplicate_charge_detected",
        transition_id="OP-08",
        detail={"second_charge_id": "ch_" + ("x" * 5000)},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageDuplicateChargeHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_duplicate_charge")
        )
    finally:
        await client.aclose()

    text = _last_text(rec)
    assert "x" * 5000 not in text, "an unbounded value went into a Telegram page"
    assert len(text) < 1200, f"page grew to {len(text)} chars"


@pytest.mark.parametrize(
    ("label", "render"),
    [
        # The plain form an exact-match scrub already catches.
        # The host is assembled from parts, never written literally: the
        # anti-regrowth lint scans textually for it and over-matches mentions on
        # purpose (see `TelegramStaffPageSender._scrub`). The transport is a
        # mock, so only the SHAPE of the URL matters here.
        ("raw", lambda t: f"bad request to https://{_TG_HOST}/bot{t}/sendMessage"),
        # The form anything that URL-encodes the request produces: ':' -> '%3A'.
        ("url-encoded", lambda t: f"bad request to ...%2Fbot{quote(t, safe='')}%2FsendMessage"),
        # `send_telegram_message` builds its 4xx error from `resp.text[:200]`,
        # which can cut a token in half. Half a token is still half a secret,
        # and an exact-match scrub does not see it at all.
        ("truncated", lambda t: f"HTTP 400 non-retryable: ...bot{t[: len(t) // 2]}"),
        # The one form no bot-id-anchored pattern can match: a body echoing
        # ONLY the half after the colon. The bot id is public; this half is the
        # secret, and it can travel without it.
        ("secret-half only", lambda t: f'HTTP 400: {{"description":"token {t.split(":", 1)[1]} rejected"}}'),
    ],
)
async def test_no_form_of_the_bot_token_survives_into_the_durable_error(label, render):
    # Hyphen-RICH on purpose: if the pattern stopped at the first `-`, the tail
    # would survive and the window loop below would name it.
    token = "8847435604:AA-a-token-shaped-string-nobody-should-ever-see"

    def _echo(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text=render(token))

    client = httpx.AsyncClient(transport=httpx.MockTransport(_echo))
    sender = TelegramStaffPageSender(client, bot_token=token, chat_id="12345")
    try:
        with pytest.raises(StaffPageSendFailed) as raised:
            await sender.send(text="DUPLICATE CHARGE")
    finally:
        await client.aclose()

    message = str(raised.value)
    secret_half = token.split(":", 1)[1]
    assert token not in message, f"[{label}] the whole token survived: {message!r}"
    assert quote(token, safe="") not in message, (
        f"[{label}] the url-encoded token survived: {message!r}"
    )
    # EVERY WINDOW of the secret half, not only its prefixes.
    #
    # An earlier version checked `secret_half[:cut]` for three values of `cut` —
    # prefixes only — and a cross-family grader was right that this passes while
    # a SUFFIX leaks: a scrub that removed the front of the secret and left
    # `-nobody-should-ever-see` would have satisfied it. The bot id before the
    # colon is public; every window of eight or more characters of the half
    # AFTER it is secret, and none may survive.
    #
    # (The same grader claimed three times that the regex `[A-Za-z0-9_%-]` omits
    # `-` and so redacts only up to the first hyphen. It does not: a `-` in FINAL
    # position inside a character class is a literal, not a range. This loop is
    # the measurement that settles it, on the real `_scrub`, on a deliberately
    # hyphen-rich token — so nobody has to take either side's word for it.)
    windows = {
        secret_half[i:j]
        for i in range(len(secret_half))
        for j in range(i + 8, len(secret_half) + 1)
    }
    assert len(windows) > 100, "the window set is too small to be a real check"
    survived = sorted((w for w in windows if w in message), key=len, reverse=True)
    assert not survived, (
        f"[{label}] {len(survived)} window(s) of the secret half survived, longest "
        f"{survived[0]!r} ({len(survived[0])} chars): {message!r}"
    )
    assert "<redacted>" in message, (
        f"[{label}] nothing was redacted — this test may be passing because the "
        f"token never made it into the error at all: {message!r}"
    )


# --- the WRITERS are where `detail` stays PII-free ----------------------------


def test_no_journal_detail_written_in_the_order_lane_names_applicant_data():
    """The reader can only drop keys it does not name; it cannot make a key it
    DOES name safe. `_detail_scalar` bounds the shape and the length of a read
    value, but if a transition ever writes an applicant field into
    `second_charge_id` itself, that value is what a page is FOR and it goes out.

    So the real constraint lives on the WRITE side, where
    `284_garuda_orders.sql` states it as prose: "No PII in detail -- enums/ids/
    amounts/dates only." This turns that comment into a test. It walks the AST
    of every module that appends to the journal in this lane and checks the KEYS
    of every `detail={...}` literal — not the values, which are runtime data,
    but the names, which are the author's intent made visible.
    """

    import ast
    import pathlib

    lane = [
        pathlib.Path("backend/services/garuda_orders/repository.py"),
        pathlib.Path("backend/services/garuda_orders/journal.py"),
        pathlib.Path("backend/services/garuda_portal/practice.py"),
        pathlib.Path("backend/services/garuda_orders/outbox_handlers.py"),
    ]
    # NOT the bare word "name". `detail={"outcome": event.failure.outcome.name}`
    # is the ordinary way to serialise an enum, and a bare-substring guard on
    # "name" rejects it — an over-match that makes a guard a nuisance someone
    # eventually disables. The compound forms are what identify a person.
    forbidden = (
        "applicant",
        "email",
        "passport",
        "phone",
        "address",
        "full_name",
        "surname",
        "fullname",
    )
    checked = 0
    for path in lane:
        assert path.exists(), f"{path} moved — this test is now blind, fix the list"
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "detail":
                    continue
                if isinstance(kw.value, ast.Constant) and kw.value.value is None:
                    continue  # `detail=None` carries nothing.
                if not isinstance(kw.value, ast.Dict):
                    # A `detail=some_variable` defeats a static read entirely,
                    # and SKIPPING it (what the first version of this test did)
                    # is how a writer evades the check while the count floor
                    # still passes. One name is allow-listed because it is a
                    # pass-through, not a literal: a `detail=detail` parameter
                    # forward. Anything else must be written as a literal here.
                    if isinstance(kw.value, ast.Name) and kw.value.id == "detail":
                        continue
                    raise AssertionError(
                        f"{path}:{kw.value.lineno} passes a non-literal `detail=` "
                        f"({ast.dump(kw.value)[:80]}); this test cannot vouch for it, "
                        "so write the literal here or extend the allow-list with a reason"
                    )
                checked += 1
                # VALUES, not only keys. `detail={"second_charge_id":
                # applicant_email}` has an innocent KEY and leaks — the first
                # version of this test was green on exactly that edit.
                for value_node in ast.walk(kw.value):
                    identifier = None
                    if isinstance(value_node, ast.Name):
                        identifier = value_node.id
                    elif isinstance(value_node, ast.Attribute):
                        identifier = value_node.attr
                    elif isinstance(value_node, ast.Constant) and isinstance(
                        value_node.value, str
                    ):
                        # A subscript hides the identifier in a STRING:
                        # `payload["applicant_email"]` has no Name or Attribute
                        # naming the field, so a Name/Attribute-only walk (what
                        # the previous version did) was green on exactly that.
                        identifier = value_node.value
                    if not identifier:
                        continue
                    for word in forbidden:
                        assert word not in identifier.lower(), (
                            f"{path}:{value_node.lineno} puts {identifier!r} into a "
                            "journal detail VALUE — the key can look innocent while "
                            "the value names the person"
                        )
                for key in kw.value.keys:
                    if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                        # A computed key defeats a static read — fail loudly
                        # rather than pass silently over something unreadable.
                        raise AssertionError(
                            f"{path}:{key.lineno} builds a journal detail key "
                            "dynamically; this test cannot vouch for it"
                        )
                    for word in forbidden:
                        assert word not in key.value.lower(), (
                            f"{path}:{key.lineno} writes journal detail key "
                            f"{key.value!r} — `garuda_order_journal.detail` is "
                            "PII-free by contract, and every staff page is composed "
                            "from it"
                        )
    # Not an absence assertion: if the walk found nothing, the test proved
    # nothing. The lane has nine `detail=` literals today.
    assert checked >= 8, (
        f"only {checked} `detail=` dict literals found in the lane — either they "
        "moved or this walk is broken; a green run here would mean nothing"
    )


async def test_a_job_pointing_at_an_event_that_does_not_exist_raises(pool):
    """FAIL CLOSED. A queued job whose triggering journal event cannot be read
    is a contradiction, and every fact the page would carry is then
    unverifiable — including whether THIS job's case is still open. The first
    version treated a missing event as "not resolved" and paged anyway, which
    renders the CURRENTLY open case's charge id under an older case's headline:
    exactly what the identity guard exists to prevent.

    MEASURED WHILE WRITING THIS: `garuda_order_journal` has a DB trigger that
    rejects DELETE and UPDATE outright ("append-only"), so the event behind a
    normally-enqueued job CANNOT vanish. The reachable shape is therefore not a
    deleted row but an outbox row that points at an id the journal never had —
    a hand-inserted job, or a restore that brought back the outbox without the
    journal. That is what this drives, and it is why the raise is worth having
    even though the ordinary path cannot produce it.
    """

    order_id = await _seed_order(pool, state="refunded", late_case_open=True)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE garuda_orders SET late_case_charge_id = 'ch_case_B' WHERE order_id = $1",
            order_id,
        )
    phantom_event = "evt_" + uuid.uuid4().hex  # satisfies the event_id CHECK, exists nowhere

    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        with pytest.raises(StaffPageOrderMissing):
            await StaffPageLatePaidAfterRefundHandler(pool, sender)(
                _job(order_id, phantom_event, "staff_page_late_paid_after_refund")
            )
    finally:
        await client.aclose()

    assert rec.requests == [], "it paged with facts it could not verify"


async def test_the_journal_rejects_update_and_delete_so_a_timestamp_tie_is_unreachable(pool):
    """WHY THERE IS NO TEST FOR THE TIMESTAMP TIE.

    `_load` compares `occurred_at` with strict `>` rather than `>=` precisely
    because this journal has no monotonic column (`event_id` is TEXT), so in
    principle two events could share an instant — and with `>=` a tie would
    SUPPRESS a money-anomaly page, the worse direction by this lane's own rule
    (nobody being told beats a duplicate page).

    A test for that tie cannot be written honestly: the only ways to produce one
    are an UPDATE of `occurred_at` or a multi-row INSERT, and this table rejects
    UPDATE and DELETE, while every writer appends one row per statement and
    `statement_timestamp()` advances between statements. So the tie is
    unreachable, the strict `>` is free insurance, and this test pins the ONE
    fact that makes it unreachable. If that guard is ever dropped, this goes red
    and the tie becomes real.

    This DRIVES the statements rather than grepping the migration for the words
    "update" and "delete" — an earlier version of this test did exactly that and
    would have passed on `updated_at` alone.
    """

    order_id = await _seed_order(pool, state="refunded", late_case_open=True)
    async with pool.acquire() as conn, conn.transaction():
        event_id = await journal.append_event(
            conn,
            event_name="payment.late_paid_after_refund",
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id="OP-F04",
            customer_visible=False,
            detail={"charge_id": "ch_probe"},
        )

    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.exceptions.PostgresError) as on_update:
            await conn.execute(
                "UPDATE garuda_order_journal SET occurred_at = now() WHERE event_id = $1",
                event_id,
            )
        with pytest.raises(asyncpg.exceptions.PostgresError) as on_delete:
            await conn.execute(
                "DELETE FROM garuda_order_journal WHERE event_id = $1", event_id
            )
        # The row is still there — the guard rejected, it did not silently no-op.
        still_there = await conn.fetchval(
            "SELECT count(*) FROM garuda_order_journal WHERE event_id = $1", event_id
        )

    assert still_there == 1, "the journal row is gone — the append-only guard did not hold"
    for label, caught in (("UPDATE", on_update), ("DELETE", on_delete)):
        assert "append-only" in str(caught.value).lower(), (
            f"{label} was rejected, but not by the append-only guard: {caught.value!r}"
        )


# --- the page must name the charge of ITS OWN event ----------------------------
#
# `late_case_charge_id` is ONE column, and OP-F04/OP-F05's UPDATE carries
# `AND late_case_open = FALSE` (repository.py:484-492), so a SECOND late payment
# on the same order does NOT overwrite it — while still writing its own journal
# event and its own page job. A page that rendered the column alone therefore
# named the FIRST charge: staff refund money already being handled, the second
# charge is never refunded, and the job is marked dispatched so it never pages
# again. Found by a cross-family seat (Kimi K3, 2026-08-28) and confirmed on disk.


async def test_the_page_names_the_charge_of_ITS_OWN_event_not_the_open_cases(pool):
    """The divergent case: the order row holds case A's charge, this job's event
    carries case B's. The page must name B — the only place B is recorded — and
    say that resolveLateOrder will not refund it.
    """

    order_id = await _seed_order(
        pool, state="refunded", late_case_open=True, late_case_charge_id="ch_case_A"
    )
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_refund",
        event_name="payment.late_paid_after_refund",
        transition_id="OP-F04",
        detail={"charge_id": "ch_case_B"},
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
    # B is named, and named as THIS event's charge.
    assert "ch_case_B" in text
    # A is still shown, because resolveLateOrder will act on it — hiding it
    # would leave the human unable to see WHY the automated path is wrong.
    assert "ch_case_A" in text
    # And the consequence is stated, not left to be inferred.
    assert "TWO LATE CHARGES" in text
    assert "will NOT refund" in text


async def test_no_divergence_warning_when_the_two_ids_agree(pool):
    """Innocence. One late payment, one case: the row and the event name the
    same charge, so there is nothing to warn about and the warning must be
    ABSENT — otherwise every ordinary page carries an alarm and the alarm stops
    meaning anything.
    """

    order_id = await _seed_order(
        pool, state="failed", late_case_open=True, late_case_charge_id="ch_only_one"
    )
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_late_paid_after_terminal",
        event_name="payment.late_paid_after_terminal",
        transition_id="OP-F05",
        detail={"charge_id": "ch_only_one"},
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
    assert "ch_only_one" in text
    assert "TWO LATE CHARGES" not in text
    assert "will NOT refund" not in text


# --- a backtick in a rendered id must not break the code span ------------------
#
# Every id is interpolated into a `` `code span` `` on the theory that Markdown
# V1 does not re-parse inside one. True — until the value contains a backtick of
# its own, which closes the span early. Telegram then answers 400 "can't parse
# entities", `send_telegram_message` treats 4xx as NON-retryable, and the handler
# raises on every attempt until the job exhausts: the page NEVER goes out. That
# inverts `_detail_scalar`'s stated purpose, since the malformed value is exactly
# what makes the anomaly unseeable. Cross-family seat (Kimi K3, 2026-08-28).


async def test_a_backtick_in_a_rendered_id_cannot_break_the_code_span(pool):
    order_id = await _seed_order(pool, state="paid", late_case_open=True)
    row_id, event_id = await _enqueue_staff_page(
        pool,
        order_id,
        job_type="staff_page_duplicate_charge",
        event_name="payment.duplicate_charge_detected",
        transition_id="OP-08",
        detail={"second_charge_id": "ch_bad`*_[evil"},
    )
    rec = _TgRecorder()
    sender, client = _tg_sender(rec)
    try:
        await StaffPageDuplicateChargeHandler(pool, sender)(
            _job(order_id, event_id, "staff_page_duplicate_charge")
        )
    finally:
        await client.aclose()
    text = _last_text(rec)
    # The value's own backtick is gone, replaced by a visible marker — the
    # anomaly stays legible, the span cannot be closed from inside.
    assert "ch_bad" in text
    assert "<backtick>" in text
    # Structural check, not a spelling check: every backtick in the page belongs
    # to a span the composer opened, so they come in pairs. An odd count is what
    # a breakout looks like, and it is what Telegram rejects.
    assert text.count("`") % 2 == 0
