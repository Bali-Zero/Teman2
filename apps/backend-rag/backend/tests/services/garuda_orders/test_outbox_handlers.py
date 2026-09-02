"""Tests for the payment-confirmation outbox handler.

Two things are exercised for real rather than mocked away:

* **The HTTP layer**, through `httpx.MockTransport` — so `BrevoEmailSender`'s
  own request construction, status handling and exception translation are the
  code under test, not a stand-in for it.
* **The consumer integration**, against real Postgres — because the single
  most important property here is a boundary property: a failed send must
  leave `dispatched_at` NULL. A unit test of the handler alone cannot see
  that; only running it through `drain_once` can.

The defining risk this file guards is inherited from the neighbour it must NOT
imitate: `_default_send_magic_link_email` swallows every exception by design.
If anyone "harmonises" this handler with it, `test_a_failed_send_leaves_the_job_
undispatched` goes red — and that is the whole point of writing it.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid

import httpx
import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_orders import journal
from backend.services.garuda_orders.outbox_consumer import KILL_SWITCH_ENV, drain_once
from backend.services.garuda_orders.outbox_handlers import (
    BrevoEmailSender,
    EmailSendFailed,
    OrderEmailFacts,
    PaymentPaidEmailHandler,
    PracticeReleaseHandler,
    build_handlers,
)
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

# `_seed_full_case` and `_reset_suite_rows` are imported rather than
# re-implemented ON PURPOSE. Seeding a usable case means check -> order ->
# journal -> practice PLUS an active GARUDA_CHECK retention policy, because
# `garuda_voa_check_results` is fail-closed by trigger. A second copy of
# either would drift from the first, and this suite would start proving
# something the adapter suite no longer does — which is exactly what had
# already happened to the cleanup half: this file's `pool` fixture used to
# carry its own hand-copied TRUNCATE/DELETE block with no post-yield call,
# so the release-job tests below (which mint real `practices` rows keyed to
# `visa_b1_voa` via `PostgresCrmWriter`) could leave the LAST such row
# committed for whatever runs next on this worker. See `_reset_suite_rows`'s
# docstring for the cross-file FK violation that caused
# (`test_migration_303_voa_price_roundtrip.py`'s DELETE on the same code).
from backend.tests.services.garuda_ops.test_adapters_pg import (
    _reset_suite_rows,
    _seed_full_case,
)

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/garuda_outbox_test_0826"
)

pytestmark = pytest.mark.asyncio

RECIPIENT = "traveller@example.invalid"


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
        # The weld tests below write real CRM rows (via `PostgresCrmWriter`,
        # every such row carries a key), so cleanup has to reach the CRM side
        # too, not just this file's own garuda_* tables — exactly what
        # `_reset_suite_rows` already does for `test_adapters_pg.py`. Called
        # both before AND after the yield: the second call is what closes the
        # cross-file leak (see that function's docstring) — without it, the
        # LAST release-job test in this file left a `practices` row keyed to
        # `visa_b1_voa` committed for whatever ran next on this worker.
        await _reset_suite_rows(p)
        yield p
        await _reset_suite_rows(p)
    finally:
        await p.close()


@pytest.fixture(autouse=True)
def armed(monkeypatch):
    monkeypatch.setenv(KILL_SWITCH_ENV, "true")
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-key-not-a-real-secret")


class _Recorder:
    """Captures what the sender actually put on the wire."""

    def __init__(self, status: int = 201, boom: Exception | None = None) -> None:
        self.status = status
        self.boom = boom
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.boom is not None:
            raise self.boom
        return httpx.Response(self.status, json={"ok": True})


def _sender(recorder: _Recorder, **kw) -> tuple[BrevoEmailSender, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    return BrevoEmailSender(client, api_url="https://notifications.invalid/send", **kw), client


async def _seed_order(pool, *, state: str = "paid", email: str = RECIPIENT) -> str:
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


async def _enqueue_paid_email(pool, order_id: str) -> int:
    async with pool.acquire() as conn, conn.transaction():
        event_id = await journal.append_event(
            conn,
            event_name="payment.paid",
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id="OP-02",
            customer_visible=True,
        )
        await journal.enqueue_outbox(
            conn, order_id=order_id, journal_event_id=event_id, job_type="payment_paid_email"
        )
        return await conn.fetchval(
            "SELECT id FROM garuda_order_outbox WHERE journal_event_id = $1", event_id
        )


def _facts(**over) -> OrderEmailFacts:
    base = {
        "order_id": "ord_specimen",
        "email": RECIPIENT,
        "case_type": "issuance",
        "price_idr": 790000,
        "state": "paid",
        # OP-F04/OP-F05 flag. Required on the dataclass on purpose: a `_load`
        # that forgets the column must fail loudly rather than default to
        # "no late payment" and let a terminal notice go out to a charged
        # customer. This factory's default is the ordinary case.
        "late_case_open": False,
    }
    base.update(over)
    return OrderEmailFacts(**base)


# --------------------------------------------------------------------------
# the sender: it must RAISE, unlike the neighbour it resembles
# --------------------------------------------------------------------------


async def test_the_sender_posts_the_expected_request():
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await sender.send(to=RECIPIENT, subject="Subject line", html_body="<b>hi</b>")
    finally:
        await client.aclose()

    assert len(rec.requests) == 1
    req = rec.requests[0]
    assert req.headers["X-API-Key"] == "test-key-not-a-real-secret"
    body = req.read().decode()
    assert RECIPIENT in body
    assert "Subject line" in body
    # The from-address is applied by the endpoint; this class must never name
    # one, or the fixed-sender rule gains a second place to drift.
    assert "zantara@balizero.com" not in body


@pytest.mark.parametrize("status", [400, 401, 429, 500, 503])
async def test_the_sender_raises_on_every_error_status(status):
    rec = _Recorder(status=status)
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await sender.send(to=RECIPIENT, subject="s", html_body="b")
    finally:
        await client.aclose()


async def test_the_sender_raises_when_the_endpoint_is_unreachable():
    rec = _Recorder(boom=httpx.ConnectError("no route"))
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await sender.send(to=RECIPIENT, subject="s", html_body="b")
    finally:
        await client.aclose()


async def test_the_sender_refuses_to_send_without_an_api_key():
    rec = _Recorder()
    sender, client = _sender(rec, api_key="")
    try:
        with pytest.raises(EmailSendFailed):
            await sender.send(to=RECIPIENT, subject="s", html_body="b")
    finally:
        await client.aclose()
    assert rec.requests == [], "must not put an unauthenticated request on the wire"


async def test_an_error_message_never_carries_the_recipient():
    """A raised message is logged by the consumer — it must stay PII-free."""

    rec = _Recorder(status=500)
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed) as caught:
            await sender.send(to=RECIPIENT, subject="s", html_body="b")
    finally:
        await client.aclose()
    assert RECIPIENT not in str(caught.value)


# --------------------------------------------------------------------------
# the body: one price, no split, a working tracker link
# --------------------------------------------------------------------------


def test_the_body_shows_one_all_inclusive_figure():
    body = PaymentPaidEmailHandler._body(_facts())
    assert "790.000" in body
    # SM-G04: never a fee/PNBP decomposition in front of a customer.
    for forbidden in ("PNBP", "fee", "service charge", "breakdown"):
        assert forbidden.lower() not in body.lower()


def test_the_body_links_to_this_orders_tracker(monkeypatch):
    monkeypatch.setenv("GARUDA_TRACKER_BASE_URL", "https://example.invalid/t")
    body = PaymentPaidEmailHandler._body(_facts(order_id="ord_abc"))
    assert 'href="https://example.invalid/t/ord_abc"' in body


def test_the_body_carries_no_passport_or_name():
    body = PaymentPaidEmailHandler._body(_facts())
    assert "X0000000" not in body
    assert "SPECIMEN" not in body


# --------------------------------------------------------------------------
# the handler, against real order rows
# --------------------------------------------------------------------------


async def test_a_paid_order_gets_exactly_one_email(pool):
    order_id = await _seed_order(pool)
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        await PaymentPaidEmailHandler(pool, sender)(_job(order_id))
    finally:
        await client.aclose()
    assert len(rec.requests) == 1
    assert RECIPIENT in rec.requests[0].read().decode()


async def test_a_refunded_order_is_resolved_without_sending(pool, caplog):
    """Resolved, not failed, and NOT silent — the WARNING is the only trace.

    Returning marks the job dispatched; that is correct, because the decision
    cannot change on a retry. Goes red if someone makes it send anyway, or
    makes it raise (which would retry a settled question five times).
    """

    order_id = await _seed_order(pool, state="refunded")
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.WARNING, logger="garuda.orders.outbox_handlers"):
            await PaymentPaidEmailHandler(pool, sender)(_job(order_id))
    finally:
        await client.aclose()

    assert rec.requests == [], "a refunded order must not be told its payment succeeded"
    assert any("WITHOUT sending" in r.getMessage() for r in caplog.records)


async def test_a_missing_order_raises(pool):
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with pytest.raises(EmailSendFailed):
            await PaymentPaidEmailHandler(pool, sender)(_job("ord_not_here"))
    finally:
        await client.aclose()


async def test_no_log_line_carries_the_recipient(pool, caplog):
    order_id = await _seed_order(pool)
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        with caplog.at_level(logging.DEBUG, logger="garuda.orders.outbox_handlers"):
            await PaymentPaidEmailHandler(pool, sender)(_job(order_id))
    finally:
        await client.aclose()
    rendered = " ".join(r.getMessage() for r in caplog.records)
    assert RECIPIENT not in rendered
    assert "SPECIMEN" not in rendered
    assert order_id in rendered, "the log must still identify WHICH order (positive control)"


# --------------------------------------------------------------------------
# end to end through the real consumer — the boundary property
# --------------------------------------------------------------------------


async def test_draining_a_queued_job_sends_and_marks_it_dispatched(pool):
    order_id = await _seed_order(pool)
    row_id = await _enqueue_paid_email(pool, order_id)

    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        async with pool.acquire() as conn:
            stats = await drain_once(conn, build_handlers(pool, sender))
    finally:
        await client.aclose()

    assert (stats.claimed, stats.dispatched, stats.failed) == (1, 1, 0)
    assert len(rec.requests) == 1
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT dispatched_at FROM garuda_order_outbox WHERE id = $1", row_id
            )
            is not None
        )


async def test_a_failed_send_leaves_the_job_undispatched(pool):
    """THE regression pin against swallowing exceptions.

    If this handler ever adopts the magic-link sender's `try/except Exception:
    log` shape, the email is lost AND the job is marked delivered. Here the
    endpoint 500s: the job must stay claimable with one attempt spent.
    """

    order_id = await _seed_order(pool)
    row_id = await _enqueue_paid_email(pool, order_id)

    rec = _Recorder(status=500)
    sender, client = _sender(rec)
    try:
        async with pool.acquire() as conn:
            stats = await drain_once(conn, build_handlers(pool, sender))
    finally:
        await client.aclose()

    assert (stats.dispatched, stats.failed) == (0, 1)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dispatched_at, attempts FROM garuda_order_outbox WHERE id = $1", row_id
        )
    assert row["dispatched_at"] is None, "a lost email must never look delivered"
    assert row["attempts"] == 1


async def test_a_retry_after_a_transient_failure_delivers(pool):
    order_id = await _seed_order(pool)
    row_id = await _enqueue_paid_email(pool, order_id)

    failing = _Recorder(status=503)
    sender_a, client_a = _sender(failing)
    try:
        async with pool.acquire() as conn:
            await drain_once(conn, build_handlers(pool, sender_a))
    finally:
        await client_a.aclose()

    ok = _Recorder()
    sender_b, client_b = _sender(ok)
    try:
        async with pool.acquire() as conn:
            stats = await drain_once(conn, build_handlers(pool, sender_b))
    finally:
        await client_b.aclose()

    assert stats.dispatched == 1
    assert len(ok.requests) == 1
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dispatched_at, attempts FROM garuda_order_outbox WHERE id = $1", row_id
        )
    assert row["dispatched_at"] is not None
    assert row["attempts"] == 2


async def test_unrouted_job_types_are_reported_not_delivered(pool):
    """A job type with no registered handler must show as unroutable.

    This used to assert on `practice_release`, then on `refund_email` — both
    acquired handlers as the outbox drain grew. The specimen is now
    `staff_page_duplicate_charge`, one of the five `staff_page_*` jobs
    `build_handlers` deliberately never routes (module docstring). Repointing
    rather than deleting keeps the property under test: `build_handlers` must
    report what it cannot route instead of consuming it.
    """

    order_id = await _seed_order(pool)
    async with pool.acquire() as conn, conn.transaction():
        event_id = await journal.append_event(
            conn,
            event_name="payment.paid",
            aggregate_type="order",
            aggregate_id=order_id,
            transition_id="OP-02",
            customer_visible=True,
        )
        await journal.enqueue_outbox(
            conn,
            order_id=order_id,
            journal_event_id=event_id,
            job_type="staff_page_duplicate_charge",
        )

    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        async with pool.acquire() as conn:
            stats = await drain_once(conn, build_handlers(pool, sender))
    finally:
        await client.aclose()

    assert stats.unroutable == 1
    assert "staff_page_duplicate_charge" in stats.unroutable_types
    assert rec.requests == []


# --------------------------------------------------------------------------
# the weld: practice_release -> CRM
# --------------------------------------------------------------------------


def test_build_handlers_routes_practice_release() -> None:
    """RED-if-wrong, and needs no database.

    Until the weld landed, `build_handlers` held exactly one key and
    `practice_release` — enqueued by the SAME transaction as the confirmation
    email — was reported `unroutable` on every drain pass forever. The customer
    got their email and the team got no work item. This asserts the registry
    itself, so the regression cannot hide behind an unreachable DB fixture.
    """

    handlers = build_handlers(pool=None, sender=None)  # type: ignore[arg-type]
    # The set is EXACT on purpose: adding a route must be a deliberate edit
    # here, and removing one can never pass unnoticed. `portal_invite` joined
    # it when a paid order started producing a portal account as well as a
    # practice; the five customer-email jobs joined when the outbox grew to
    # cover checkout/failure/expiry/refund/receipt;
    # `late_refund_confirmation_email` joined last — the type three separate
    # counts missed because its call site passes `job_type` as a VARIABLE and
    # every count was a `job_type="` grep.
    #
    # This hand-maintained set is a SECOND opinion. The primary check is
    # `test_outbox_job_type_coverage.py`, which reads the enqueued types out of
    # the AST — the only shape that can see a non-literal argument.
    assert set(handlers) == {
        "checkout_ready_email",
        "payment_paid_email",
        "payment_failed_email",
        "payment_expired_email",
        "refund_email",
        "late_refund_confirmation_email",
        "practice_release",
        "practice_received_email",
        "portal_invite",
        # step 8 (round 3, item E): the 7 staff-transition customer emails,
        # `staff_transitions.py::apply_transition`'s own job_type if/elif
        # chain — see that module and PracticeTransitionEmailHandler above.
        "practice_in_review_email",
        "practice_blocked_email",
        "practice_submitted_email",
        "practice_approved_email",
        "practice_rejected_email",
        "practice_resumed_email",
        "practice_delivered_email",
    }
    assert isinstance(handlers["practice_release"], PracticeReleaseHandler)


def test_the_pr01_envelope_digest_is_deterministic_and_contract_shaped() -> None:
    """The digest is what the DB dedups on, so it must be a pure function of
    the payment event. RED if anything random, clock-derived or id-derived
    creeps in: two deliveries of the same payment would mint two practices.

    Shape is checked too — `events.yaml` types `key_digest` as `^[a-f0-9]{64}$`
    and `PostgresCrmWriter` stores it in a partial UNIQUE index; a value of any
    other shape would not be caught until production.
    """

    job_a = _release_job(journal_event_id="evt_paid_1", job_id=1)
    job_b = _release_job(journal_event_id="evt_paid_1", job_id=999)
    job_c = _release_job(journal_event_id="evt_paid_2", job_id=1)

    env_a = PracticeReleaseHandler._envelope(job_a, "practice-1")
    env_b = PracticeReleaseHandler._envelope(job_b, "practice-1")
    env_c = PracticeReleaseHandler._envelope(job_c, "practice-1")

    assert env_a.idempotency_identity.key_digest == env_b.idempotency_identity.key_digest
    assert env_a.idempotency_identity.key_digest != env_c.idempotency_identity.key_digest
    assert re.fullmatch(r"[a-f0-9]{64}", env_a.idempotency_identity.key_digest)
    assert env_a.transition_id == "PR-01"
    assert env_a.aggregate_type == "practice"
    assert env_a.aggregate_id == "practice-1"


def test_the_envelope_event_id_is_the_delivery_not_the_payment() -> None:
    """ports.py gap 1: deduping on the event's own id catches an outbox
    redelivery but NOT a journal-level retry. Keeping `event_id` distinct from
    the idempotency digest is what makes that distinction visible instead of
    accidentally identical."""

    env = PracticeReleaseHandler._envelope(_release_job("evt_paid_1", 7), "practice-1")
    assert env.event_id == "outbox:7"
    assert env.event_id != env.idempotency_identity.key_digest


async def _order_of(pool, practice_id: str) -> str:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT order_id FROM garuda_practices WHERE practice_id = $1", practice_id
        )


async def _enqueue_release(pool, order_id: str, event_id: str) -> int:
    async with pool.acquire() as conn, conn.transaction():
        await journal.enqueue_outbox(
            conn, order_id=order_id, journal_event_id=event_id, job_type="practice_release"
        )
        return await conn.fetchval(
            "SELECT id FROM garuda_order_outbox "
            "WHERE journal_event_id = $1 AND job_type = 'practice_release'",
            event_id,
        )


async def _drain(pool):
    rec = _Recorder()
    sender, client = _sender(rec)
    try:
        async with pool.acquire() as conn:
            return await drain_once(conn, build_handlers(pool, sender))
    finally:
        await client.aclose()


async def test_a_release_job_creates_the_crm_practice_and_marks_itself_dispatched(pool):
    """The whole weld, end to end against real Postgres, asserted on the ROW.

    The first version of this test asserted `stats.dispatched == 1` and
    `stats.unroutable == 0` and was wrong twice, which is why it now reads the
    database instead. `stats.unroutable == 0` is not a property of a healthy
    weld at all — `mint_received_practice` enqueues its own
    `practice_received_email`, which has no handler and is CORRECTLY reported
    unroutable — and counting dispatches says nothing about whether a usable
    CRM row exists. What matters is the practice: that it is there, that it
    carries Zero's ruling, and that it is reachable by the person who has to
    work it.
    """

    practice_id, event_id = await _seed_full_case(pool)
    order_id = await _order_of(pool, practice_id)
    job_id = await _enqueue_release(pool, order_id, event_id)

    await _drain(pool)

    digest = hashlib.sha256(event_id.encode()).hexdigest()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT dispatched_at, attempts FROM garuda_order_outbox WHERE id = $1", job_id
        )
        row = await conn.fetchrow(
            """
            SELECT p.status, p.payment_status, p.practice_type_code,
                   p.actual_price, p.paid_amount, p.assigned_to, p.created_by
              FROM practices p
             WHERE p.source_idempotency_key = $1
            """,
            digest,
        )

    assert job["dispatched_at"] is not None, "the release job must be marked delivered"
    assert row is not None, "no CRM practice was created for a paid order"
    assert row["status"] == "on_process"
    assert row["payment_status"] == "paid"
    assert row["practice_type_code"] == "visa_b1_voa"  # issuance, per the case_type mapping
    assert int(row["actual_price"]) == 790000
    assert int(row["paid_amount"]) == 790000
    assert row["created_by"] is not None


async def test_a_second_delivery_of_the_same_payment_creates_no_second_practice(pool):
    """Idempotency where it actually has to hold: the DATABASE.

    Two deliveries of the same payment event produce the same digest, and the
    partial UNIQUE index on `practices.source_idempotency_key` — not this
    handler — is what refuses the duplicate. RED if the digest ever stops being
    a pure function of the journal event id."""

    practice_id, event_id = await _seed_full_case(pool)
    order_id = await _order_of(pool, practice_id)

    await _enqueue_release(pool, order_id, event_id)
    await _drain(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE garuda_order_outbox SET dispatched_at = NULL, attempts = 0 "
            "WHERE job_type = 'practice_release'"
        )
    await _drain(pool)

    digest = hashlib.sha256(event_id.encode()).hexdigest()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM practices WHERE source_idempotency_key = $1", digest
        )
    assert count == 1


async def test_a_release_job_without_its_practice_row_raises_and_stays_undispatched(pool):
    """`mint_received_practice` runs in the same transaction that enqueues this
    job, so a missing row means something deleted a practice out from under a
    queued release. It must exhaust visibly, never be marked delivered."""

    practice_id, event_id = await _seed_full_case(pool)
    order_id = await _order_of(pool, practice_id)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM garuda_practices WHERE practice_id = $1", practice_id)
    job_id = await _enqueue_release(pool, order_id, event_id)

    stats = await _drain(pool)

    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT dispatched_at FROM garuda_order_outbox WHERE id = $1", job_id
        )
    assert stats.failed == 1
    assert job["dispatched_at"] is None


def _job(order_id: str):
    from backend.services.garuda_orders.outbox_consumer import OutboxJob

    return OutboxJob(
        id=1,
        order_id=order_id,
        journal_event_id="evt_specimen",
        job_type="payment_paid_email",
        payload={},
        attempts=1,
    )


def _release_job(journal_event_id: str, job_id: int = 1):
    from backend.services.garuda_orders.outbox_consumer import OutboxJob

    return OutboxJob(
        id=job_id,
        order_id="ord_specimen",
        journal_event_id=journal_event_id,
        job_type="practice_release",
        payload={},
        attempts=1,
    )
