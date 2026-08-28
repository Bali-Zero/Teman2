"""Tests for `LateRefundConfirmationEmailHandler` — the FOURTEENTH job type.

The one behaviour worth stating up front, because it is what the handler is
shaped around: `resolve_late_order` writes `late_case_resolution` as ONE column
per order, and migration 284 allows a SECOND late case to open once the first
is closed. So the current column cannot answer "what was MY case resolved as".
The handler reads the resolution out of the TRIGGERING journal event instead,
and `test_a_delayed_job_renders_its_own_cases_resolution_not_a_later_one` is
the test that would go red if anyone changed that back.
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
    EmailSendFailed,
    LateRefundConfirmationEmailHandler,
)
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/garuda_outbox_test_0826"
)

pytestmark = pytest.mark.asyncio

RECIPIENT = "traveller@example.invalid"
APPLICANT_NAME = "SPECIMEN TRAVELLER"
APPLICANT_PHONE = "+000000000000"
APPLICANT_PASSPORT = "X0000000"
PRICE_IDR = 790000
LOGGER_NAME = "garuda.orders.outbox_handlers"


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
                "garuda_order_journal, garuda_orders, garuda_voa_check_results CASCADE"
            )
        yield p
    finally:
        await p.close()


@pytest.fixture(autouse=True)
def armed(monkeypatch):
    monkeypatch.setenv(KILL_SWITCH_ENV, "true")
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-key-not-a-real-secret")


class _Recorder:
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


async def _seed_order(pool, *, state: str = "refunded") -> str:
    order_id = f"ord_{uuid.uuid4().hex}"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO garuda_orders
                (order_id, result_id_ref, case_type, applicant_full_name,
                 applicant_email, applicant_phone, applicant_passport_number,
                 price_idr, price_catalogue_key, state, late_case_open)
            VALUES ($1, $2, 'issuance', $3, $4, $5, $6, $7,
                    'B1 Visa on Arrival (VOA)', $8, FALSE)
            """,
            order_id,
            f"chk_{uuid.uuid4().hex}",
            APPLICANT_NAME,
            RECIPIENT,
            APPLICANT_PHONE,
            APPLICANT_PASSPORT,
            PRICE_IDR,
            state,
        )
    return order_id


async def _seed_resolution_event(pool, order_id: str, resolution: str) -> str:
    """One real `order.late_resolved` event, exactly as OP-F05 writes it."""

    async with pool.acquire() as conn, conn.transaction():
        return await journal.append_event(
            conn,
            event_name="order.late_resolved",
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id="OP-F05",
            customer_visible=True,
            detail={"resolution": resolution},
        )


def _job(order_id: str, event_id: str) -> OutboxJob:
    return OutboxJob(
        id=1,
        order_id=order_id,
        journal_event_id=event_id,
        job_type="late_refund_confirmation_email",
        payload={},
        attempts=1,
    )


# --------------------------------------------------------------------------
# guilt
# --------------------------------------------------------------------------


async def test_sends_when_the_triggering_event_says_refunded_in_full(pool):
    order_id = await _seed_order(pool)
    event_id = await _seed_resolution_event(pool, order_id, "refunded_in_full")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await LateRefundConfirmationEmailHandler(pool, sender)(_job(order_id, event_id))
    finally:
        await client.aclose()

    assert len(rec.requests) == 1
    body = rec.requests[0].content.decode()
    assert RECIPIENT in body
    assert "returned it" in body


async def test_the_body_never_claims_a_SECOND_payment(pool):
    """The first draft of this copy said "A second payment was taken". That is
    true for OP-08 (a duplicate charge on an already-`paid` order) and FALSE for
    OP-F05, which fires from `failed`/`expired` — an order that never had a
    successful payment at all ("`provider_charge_id` is NULL here (a
    failed/expired order never reached OP-02)", repository.py:509-512).

    This handler is triggered by `order.late_resolved`, whose `detail` carries
    only `{"resolution": ...}`, so it CANNOT tell the three opening transitions
    apart. Any wording that commits to one of them is therefore a claim the code
    cannot support, and this mail asserts money movement to a customer.
    """

    order_id = await _seed_order(pool)
    event_id = await _seed_resolution_event(pool, order_id, "refunded_in_full")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await LateRefundConfirmationEmailHandler(pool, sender)(_job(order_id, event_id))
    finally:
        await client.aclose()

    body = rec.requests[0].content.decode().lower()
    for forbidden in ("second payment", "duplicate payment", "twice", "extra payment"):
        assert forbidden not in body, (
            f"the copy claims {forbidden!r}, which is false for a late payment on a "
            f"failed/expired order — the path with no earlier payment"
        )
    # And it must not claim the application is unaffected: for OP-F05 it is
    # genuinely failed or expired.
    assert "not affected" not in body


# --------------------------------------------------------------------------
# innocence
# --------------------------------------------------------------------------


async def test_does_not_send_when_the_case_was_honoured(pool, caplog):
    order_id = await _seed_order(pool)
    event_id = await _seed_resolution_event(pool, order_id, "honoured")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            await LateRefundConfirmationEmailHandler(pool, sender)(_job(order_id, event_id))
    finally:
        await client.aclose()

    assert rec.requests == [], "a refund confirmation for a case we KEPT the money on"
    assert any("honoured" in r.getMessage() for r in caplog.records), (
        "the withholding branch must name the value it read — it is the only "
        "durable trace, since garuda_order_outbox has no last_error column and "
        "nothing pages on unroutable"
    )


async def test_raises_when_the_triggering_event_does_not_exist(pool):
    order_id = await _seed_order(pool)
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed) as excinfo:
            await LateRefundConfirmationEmailHandler(pool, sender)(
                _job(order_id, "evt_does_not_exist")
            )
    finally:
        await client.aclose()

    assert rec.requests == []
    message = str(excinfo.value)
    for secret in (APPLICANT_NAME, RECIPIENT, APPLICANT_PHONE, APPLICANT_PASSPORT):
        assert secret not in message, f"applicant PII leaked into the raised error: {secret!r}"


async def test_raises_when_the_order_does_not_exist(pool):
    """An order id nothing backs, rather than a deleted row: `garuda_orders` is
    FK'd from the append-only journal, whose own trigger answers
    "garuda_order_journal is append-only -- DELETE is forbidden". Building this
    case by deletion is not possible against the real schema, and faking it
    against a stub would be testing the stub."""

    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await LateRefundConfirmationEmailHandler(pool, sender)(
                _job(f"ord_{uuid.uuid4().hex}", "evt_also_absent")
            )
    finally:
        await client.aclose()
    assert rec.requests == []


# --------------------------------------------------------------------------
# the reason the handler reads the EVENT and not the column
# --------------------------------------------------------------------------


async def test_a_delayed_job_renders_its_own_cases_resolution_not_a_later_one(pool):
    """Two late cases on one order. Case A was HONOURED, case B was REFUNDED.

    `garuda_orders.late_case_resolution` now holds case B's value, and a
    handler keying on that column would email case A's customer-facing job
    saying money came back — when for case A it did not. Reading the
    triggering event keeps each job on its own case.
    """

    order_id = await _seed_order(pool)
    case_a = await _seed_resolution_event(pool, order_id, "honoured")
    case_b = await _seed_resolution_event(pool, order_id, "refunded_in_full")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE garuda_orders SET late_case_resolution = 'refunded_in_full' "
            "WHERE order_id = $1",
            order_id,
        )

    rec = _Recorder()
    sender, client = _sender(rec)
    handler = LateRefundConfirmationEmailHandler(pool, sender)
    try:
        await handler(_job(order_id, case_a))
        assert rec.requests == [], (
            "case A was HONOURED — this mail is about case B's refund and would "
            "tell the wrong customer their money came back"
        )
        await handler(_job(order_id, case_b))
        assert len(rec.requests) == 1, "case B's own job must still send"
    finally:
        await client.aclose()


# --------------------------------------------------------------------------
# the money statement
# --------------------------------------------------------------------------


async def test_the_body_quotes_no_amount(pool):
    """Nothing records what the EXTRA charge was — `late_case_charge_id` is a
    provider id, not a figure. Naming `price_idr` would name a number that is
    wrong, not merely unproven."""

    order_id = await _seed_order(pool)
    event_id = await _seed_resolution_event(pool, order_id, "refunded_in_full")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await LateRefundConfirmationEmailHandler(pool, sender)(_job(order_id, event_id))
    finally:
        await client.aclose()

    body = rec.requests[0].content.decode()
    for rendering in (str(PRICE_IDR), f"{PRICE_IDR:,}", f"{PRICE_IDR:,}".replace(",", ".")):
        assert rendering not in body, f"an amount reached the customer: {rendering!r}"


async def test_no_applicant_pii_but_the_address_reaches_the_log(pool, caplog):
    order_id = await _seed_order(pool)
    event_id = await _seed_resolution_event(pool, order_id, "refunded_in_full")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            await LateRefundConfirmationEmailHandler(pool, sender)(_job(order_id, event_id))
    finally:
        await client.aclose()

    logged = " ".join(r.getMessage() for r in caplog.records)
    for secret in (APPLICANT_NAME, RECIPIENT, APPLICANT_PHONE, APPLICANT_PASSPORT):
        assert secret not in logged, f"applicant PII reached a log line: {secret!r}"


@pytest.mark.parametrize("poisoned", [{"resolution": {"nested": "object"}}, {}, {"resolution": 7}])
async def test_a_non_string_resolution_is_never_treated_as_a_refund(pool, poisoned):
    """`detail` is JSONB and admits any shape. Anything that is not the exact
    sentinel string must withhold, never send."""

    order_id = await _seed_order(pool)
    async with pool.acquire() as conn, conn.transaction():
        event_id = await journal.append_event(
            conn,
            event_name="order.late_resolved",
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id="OP-F05",
            customer_visible=True,
            detail=poisoned,
        )
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await LateRefundConfirmationEmailHandler(pool, sender)(_job(order_id, event_id))
    finally:
        await client.aclose()
    assert rec.requests == []
