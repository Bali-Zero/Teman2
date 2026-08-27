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
    BrevoEmailSender,
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


async def _seed_order(
    pool, *, state: str, email: str = RECIPIENT, late_case_open: bool = False
) -> str:
    order_id = f"ord_{uuid.uuid4().hex}"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO garuda_orders
                (order_id, result_id_ref, case_type, applicant_full_name,
                 applicant_email, applicant_phone, applicant_passport_number,
                 price_idr, price_catalogue_key, state, late_case_open)
            VALUES ($1, $2, 'issuance', 'SPECIMEN TRAVELLER', $3,
                    '+000000000000', 'X0000000', 790000,
                    'B1 Visa on Arrival (VOA)', $4, $5)
            """,
            order_id,
            f"chk_{uuid.uuid4().hex}",
            email,
            state,
            late_case_open,
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


async def test_refund_sends_while_refunded_and_quotes_NO_amount(pool):
    """CORRECTED after a cross-family gate: the first version of this test
    asserted `"790.000" in body`, i.e. it REQUIRED the handler to state a
    refunded amount — and `price_idr` is the ORDER price, not a refunded one.
    Nothing in `garuda_orders` records what the provider actually returned, and
    OP-05 reaches `refunded` from `awaiting_payment`, an order this flow never
    marked as charged. So the assertion is inverted: the refund email confirms
    the refund and names the order, and quotes no figure at all.

    This is NOT the fee/PNBP split rule (that forbids BREAKING the one price
    into components) — it is the narrower "do not assert a number the code
    cannot establish"."""

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
    assert order_id in body
    for rendering in ("790.000", "790,000", "790000"):
        assert rendering not in body, (
            f"the refund email quoted {rendering!r} — that is the order price, "
            "not a refunded amount the code can establish"
        )


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


# --------------------------------------------------------------------------
# PII tripwire — the logs, not the wire
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("handler_cls", "job_type", "state", "needs_practice", "payload"),
    [
        # checkout_ready is the one job whose payload is load-bearing: the
        # handler raises without a `checkout_url` (see
        # `test_checkout_ready_raises_without_a_checkout_url`), so a payload-less
        # case here would fail on that instead of testing the logs.
        (
            CheckoutReadyEmailHandler,
            "checkout_ready_email",
            "awaiting_payment",
            False,
            {"checkout_url": "https://checkout.invalid/inv_specimen"},
        ),
        (PaymentFailedEmailHandler, "payment_failed_email", "failed", False, None),
        (PaymentExpiredEmailHandler, "payment_expired_email", "expired", False, None),
        (RefundEmailHandler, "refund_email", "refunded", False, None),
        (PracticeReceivedEmailHandler, "practice_received_email", "paid", True, None),
    ],
)
async def test_no_handler_writes_applicant_pii_into_a_log_line(
    pool, caplog, handler_cls, job_type, state, needs_practice, payload
):
    """The bodies necessarily carry the customer's details; the LOGS must not.

    Every handler here logs, and `logger.info("... for order %s")` is the shape
    they are supposed to use. Nothing structural stops a future edit from
    widening one of those calls to `%s` the whole `facts` object, or adding the
    address "to make the log useful" — and by the time that ships, the value is
    already in Fly's log stream and in Sentry, which is not a place PII can be
    withdrawn from. Inspection caught this today; this test is what keeps
    catching it.

    Asserts on the SEEDED values rather than a regex for anything
    email-shaped: a pattern search would also flag the notifications endpoint
    URL and would miss the applicant NAME entirely, which is the field a
    well-meaning "log who we emailed" edit is most likely to reach for.
    """

    marker_email = f"pii-tripwire-{uuid.uuid4().hex}@example.invalid"
    order_id = await _seed_order(pool, state=state, email=marker_email)
    if needs_practice:
        await _seed_practice(pool, order_id)

    recorder = _Recorder()
    sender, client = _sender(recorder)
    try:
        with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
            await handler_cls(pool, sender)(_job(order_id, job_type, payload))
    finally:
        await client.aclose()

    # Innocence first: if it did not send, the test below proves nothing.
    assert len(recorder.requests) == 1, (
        f"{handler_cls.__name__} did not send in state {state!r} — the PII assertion "
        "below would pass vacuously"
    )

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert logged.strip(), f"{handler_cls.__name__} logged nothing — nothing to check"

    for label, secret in (
        ("applicant email", marker_email),
        ("applicant name", "SPECIMEN TRAVELLER"),
        ("passport number", "X0000000"),
        ("phone", "+000000000000"),
    ):
        assert secret not in logged, (
            f"{handler_cls.__name__} wrote the {label} into a log line: {logged!r}"
        )

    # And the thing that SHOULD be there, so this is not satisfied by silence.
    assert order_id in logged, (
        f"{handler_cls.__name__} logged without the order id — the log is unusable"
    )


# --- OP-F05: a late `paid` webhook leaves the terminal state in place ----------
#
# `handle_late_paid_event` sets `late_case_open = TRUE` and does NOT move
# `state` (repository.py:487/517, migration 284). A `payment_failed_email` or
# `payment_expired_email` job already sitting in the outbox therefore still
# reads `failed`/`expired` — and both bodies tell the customer no money was
# taken. It was. These two tests are the guilt half of that guard; the two
# below them are its innocence half, so the guard cannot be satisfied by
# refusing to send at all.


@pytest.mark.parametrize(
    ("handler_cls", "job_type", "state"),
    [
        (PaymentFailedEmailHandler, "payment_failed_email", "failed"),
        (PaymentExpiredEmailHandler, "payment_expired_email", "expired"),
    ],
)
async def test_terminal_notice_is_withheld_when_a_late_payment_case_is_open(
    pool, caplog, handler_cls, job_type, state
):
    order_id = await _seed_order(pool, state=state, late_case_open=True)
    recorder = _Recorder()
    sender, client = _sender(recorder)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            await handler_cls(pool, sender)(_job(order_id, job_type))
    finally:
        await client.aclose()

    assert recorder.requests == [], (
        f"{handler_cls.__name__} told a CHARGED customer no payment was taken "
        f"(order in state {state!r} with an open late-payment case)"
    )
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "late-payment case" in logged, (
        f"{handler_cls.__name__} withheld the email but left no trail naming why: {logged!r}"
    )
    assert order_id in logged


@pytest.mark.parametrize(
    ("handler_cls", "job_type", "state"),
    [
        (PaymentFailedEmailHandler, "payment_failed_email", "failed"),
        (PaymentExpiredEmailHandler, "payment_expired_email", "expired"),
    ],
)
async def test_terminal_notice_is_still_sent_when_no_late_payment_case_is_open(
    pool, handler_cls, job_type, state
):
    order_id = await _seed_order(pool, state=state, late_case_open=False)
    recorder = _Recorder()
    sender, client = _sender(recorder)
    try:
        await handler_cls(pool, sender)(_job(order_id, job_type))
    finally:
        await client.aclose()

    assert len(recorder.requests) == 1, (
        f"{handler_cls.__name__} withheld a LEGITIMATE notice — the late-payment "
        "guard must narrow the send, not replace it"
    )


# --- PII tripwire, second and third branches ----------------------------------
#
# The tripwire above only exercises the SUCCESSFUL send. Two other branches log
# and were uncovered: the stale-state early return, and a sender failure. A
# well-meaning "log who we failed to email" edit lands in exactly those two.


@pytest.mark.parametrize(
    ("handler_cls", "job_type"),
    [
        (PaymentFailedEmailHandler, "payment_failed_email"),
        (PaymentExpiredEmailHandler, "payment_expired_email"),
        (RefundEmailHandler, "refund_email"),
    ],
)
async def test_the_stale_state_branch_logs_no_applicant_pii(
    pool, caplog, handler_cls, job_type
):
    marker_email = f"pii-stale-{uuid.uuid4().hex}@example.invalid"
    # `paid` warrants none of these three notices, so each takes its stale-state
    # early return.
    order_id = await _seed_order(pool, state="paid", email=marker_email)
    recorder = _Recorder()
    sender, client = _sender(recorder)
    try:
        with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
            await handler_cls(pool, sender)(_job(order_id, job_type))
    finally:
        await client.aclose()

    assert recorder.requests == [], f"{handler_cls.__name__} sent a stale notice"
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert order_id in logged, f"{handler_cls.__name__} returned silently — no trail"
    for label, secret in (
        ("applicant email", marker_email),
        ("applicant name", "SPECIMEN TRAVELLER"),
        ("passport number", "X0000000"),
        ("phone", "+000000000000"),
    ):
        assert secret not in logged, (
            f"{handler_cls.__name__} wrote the {label} into its stale-state log line: {logged!r}"
        )


async def test_a_sender_failure_leaks_no_applicant_pii_into_its_error(pool, caplog):
    """The failure path logs NOTHING — so a caplog-only assertion here would be
    satisfied by silence and prove nothing. The surface that actually carries
    text out of this path is the raised `EmailSendFailed` MESSAGE: `drain_once`
    catches it and calls `logger.exception`, so the message lands in the
    process's log stream. (Corrected 2026-08-28: this said the worker "persists
    it as the job's `last_error`". There is no `last_error` column —
    `garuda_order_outbox`, migration 284:347-357, has only id / order_id /
    journal_event_id / job_type / payload / created_at / dispatched_at /
    attempts. The tripwire is unchanged; the named surface was wrong.) `send`
    keeps the
    response body out of that message on purpose ("it can echo the recipient");
    this is the tripwire on that comment.
    """

    marker_email = f"pii-senderr-{uuid.uuid4().hex}@example.invalid"
    order_id = await _seed_order(pool, state="expired", email=marker_email)

    def _boom(request: httpx.Request) -> httpx.Response:
        # A provider that echoes the request back — the realistic worst case.
        return httpx.Response(500, json={"error": "rejected", "echo": request.read().decode()})

    client = httpx.AsyncClient(transport=httpx.MockTransport(_boom))
    sender = BrevoEmailSender(client, api_url="https://notifications.invalid/send")
    try:
        with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
            with pytest.raises(EmailSendFailed) as raised:
                await PaymentExpiredEmailHandler(pool, sender)(
                    _job(order_id, "payment_expired_email")
                )
    finally:
        await client.aclose()

    surfaced = str(raised.value) + "\n".join(r.getMessage() for r in caplog.records)
    assert surfaced.strip(), "the failure surfaced no text at all — nothing to diagnose from"
    assert "500" in surfaced, (
        "the error names neither the status nor anything else actionable: "
        f"{surfaced!r}"
    )
    for label, secret in (
        ("applicant email", marker_email),
        ("applicant name", "SPECIMEN TRAVELLER"),
        ("passport number", "X0000000"),
        ("phone", "+000000000000"),
    ):
        assert secret not in surfaced, (
            f"the sender-failure path surfaced the {label}: {surfaced!r}"
        )
