"""Real-database tests for the `garuda_order_outbox` consumer.

Real Postgres, not a fake, and deliberately so: every claim this consumer makes
lives in SQL, not in Python. `FOR UPDATE SKIP LOCKED`, the attempt bump that must
survive a handled exception, the rollback that must NOT let an unroutable job
spend its budget — a hand-written double would test the author's mental model of
Postgres rather than Postgres, which is how a fake and the code it stands in for
come to share the same imagination (W114).

DSN resolution follows the sibling money-path suite (`test_repository_integration.py`):
`INTAKE_TEST_DSN` is what CI actually sets, `GARUDA_L3_TEST_DSN` is an optional
local override. In CI a connection failure FAILS rather than skips — a skip in a
gate is a fail-open.

Rows are written through the production writers (`journal.append_event`,
`journal.enqueue_outbox`) rather than by hand, so a schema change that breaks the
real enqueue path breaks these tests too instead of leaving them green against a
shape that no longer exists.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_orders import journal
from backend.services.garuda_orders.outbox_consumer import (
    DEFAULT_MAX_ATTEMPTS,
    KILL_SWITCH_ENV,
    OutboxJob,
    count_undrained,
    drain_once,
    is_consumer_enabled,
)

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/garuda_outbox_test_0826"
)

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


async def _connect() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(_DSN)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(f"no reachable Postgres in CI at {_DSN}: {exc}")
        pytest.skip(f"no reachable Postgres at {_DSN}: {exc}")


@pytest.fixture
async def conn():
    c = await _connect()
    try:
        await c.execute("TRUNCATE garuda_order_outbox, garuda_order_journal, garuda_orders CASCADE")
        yield c
    finally:
        await c.close()


@pytest.fixture(autouse=True)
def armed(monkeypatch):
    """Every test but the disarmed ones runs with the kill switch ON."""

    monkeypatch.setenv(KILL_SWITCH_ENV, "true")


async def _seed_order(conn: asyncpg.Connection) -> str:
    order_id = f"ord_{uuid.uuid4().hex}"
    await conn.execute(
        """
        INSERT INTO garuda_orders
            (order_id, result_id_ref, case_type, applicant_full_name,
             applicant_email, applicant_phone, applicant_passport_number,
             price_idr, price_catalogue_key)
        VALUES ($1, $2, 'issuance', 'SPECIMEN TRAVELLER',
                'specimen@example.invalid', '+000000000000', 'X0000000',
                790000, 'B1 Visa on Arrival (VOA)')
        """,
        order_id,
        f"chk_{uuid.uuid4().hex}",
    )
    return order_id


async def _enqueue(conn: asyncpg.Connection, order_id: str, job_type: str, payload=None) -> int:
    """Enqueue through the PRODUCTION writers, then return the outbox row id."""

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
        job_type=job_type,
        payload=payload,
    )
    return await conn.fetchval(
        "SELECT id FROM garuda_order_outbox WHERE journal_event_id = $1", event_id
    )


async def _row(conn: asyncpg.Connection, row_id: int):
    return await conn.fetchrow(
        "SELECT attempts, dispatched_at FROM garuda_order_outbox WHERE id = $1", row_id
    )


def _recording_handler(seen: list[OutboxJob]):
    async def handler(job: OutboxJob) -> None:
        seen.append(job)

    return handler


async def _always_fails(job: OutboxJob) -> None:
    raise RuntimeError("handler blew up")


# --------------------------------------------------------------------------
# the kill switch
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "yes", "TRUE", "True", "", "false", " true"])
def test_kill_switch_accepts_only_the_literal_true(value):
    assert is_consumer_enabled({KILL_SWITCH_ENV: value}) is False


def test_kill_switch_arms_on_exactly_true():
    assert is_consumer_enabled({KILL_SWITCH_ENV: "true"}) is True


def test_kill_switch_is_off_when_unset():
    assert is_consumer_enabled({}) is False


async def test_a_disarmed_consumer_does_not_touch_a_single_row(conn, monkeypatch):
    """Disarmed must mean disarmed: no claim, no attempt bump, no dispatch.

    Goes red if `drain_once` ever consults the database before checking the
    switch — which is the difference between a kill switch and a log line.
    """

    monkeypatch.delenv(KILL_SWITCH_ENV, raising=False)
    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "payment_paid_email")

    seen: list[OutboxJob] = []
    stats = await drain_once(conn, {"payment_paid_email": _recording_handler(seen)})

    assert (stats.claimed, stats.dispatched, stats.accounted) == (0, 0, 0)
    assert seen == []
    row = await _row(conn, row_id)
    assert row["attempts"] == 0
    assert row["dispatched_at"] is None


# --------------------------------------------------------------------------
# the happy path, and the fact that it happens exactly once
# --------------------------------------------------------------------------


async def test_a_handled_job_is_marked_dispatched_and_never_claimed_again(conn):
    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "payment_paid_email", {"to": "redacted"})

    seen: list[OutboxJob] = []
    first = await drain_once(conn, {"payment_paid_email": _recording_handler(seen)})

    assert (first.claimed, first.dispatched, first.failed) == (1, 1, 0)
    assert [j.job_type for j in seen] == ["payment_paid_email"]
    assert seen[0].payload == {"to": "redacted"}, "payload must arrive decoded"
    assert seen[0].order_id == order_id

    row = await _row(conn, row_id)
    assert row["dispatched_at"] is not None
    assert row["attempts"] == 1

    second = await drain_once(conn, {"payment_paid_email": _recording_handler(seen)})
    assert (second.claimed, second.dispatched) == (0, 0)
    assert len(seen) == 1, "a dispatched job must never be handed to a handler twice"


async def test_batch_size_bounds_one_pass(conn):
    order_id = await _seed_order(conn)
    for _ in range(5):
        await _enqueue(conn, order_id, "payment_paid_email")

    seen: list[OutboxJob] = []
    stats = await drain_once(conn, {"payment_paid_email": _recording_handler(seen)}, batch_size=2)
    assert (stats.claimed, stats.dispatched) == (2, 2)
    assert len(seen) == 2


# --------------------------------------------------------------------------
# failure: the attempt must be SPENT, or exhaustion can never be reached
# --------------------------------------------------------------------------


async def test_a_failing_handler_spends_the_attempt_and_leaves_the_job_pending(conn):
    """The single most load-bearing behaviour in the module.

    The `except` sits INSIDE the transaction so the attempt bump commits. If it
    were moved outside — the natural-looking refactor — the bump would roll back
    with the exception, `attempts` would stay 0 forever, and a permanently
    poisoned job would retry until the end of time while `count_undrained`
    reported zero exhausted rows. This test goes red the moment that happens.
    """

    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "payment_paid_email")

    stats = await drain_once(conn, {"payment_paid_email": _always_fails})

    assert (stats.claimed, stats.dispatched, stats.failed) == (1, 0, 1)
    row = await _row(conn, row_id)
    assert row["dispatched_at"] is None, "a failed job must stay claimable"
    assert row["attempts"] == 1, "the attempt must be recorded, not rolled back"


async def test_a_failing_job_spends_ONE_attempt_per_pass_not_its_whole_budget(conn):
    """The retry limit must bound attempts over TIME, not over one loop.

    This is a regression pin for a defect this suite caught on its first run: a
    failed row stays claimable the moment its transaction ends, so with no
    per-pass exclusion the same job was re-claimed on every iteration and burned
    all five attempts in 0.03 seconds. The batch is sized deliberately larger
    than `DEFAULT_MAX_ATTEMPTS` so that removing the exclusion fails here.
    """

    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "payment_paid_email")

    stats = await drain_once(
        conn,
        {"payment_paid_email": _always_fails},
        batch_size=DEFAULT_MAX_ATTEMPTS + 3,
    )

    assert stats.claimed == 1, "one pass must claim a given job at most once"
    assert stats.failed == 1
    assert (await _row(conn, row_id))["attempts"] == 1


async def test_a_job_stops_being_claimed_at_max_attempts_and_is_reported_exhausted(
    conn,
):
    """Exhaustion is visible, not silent. W81b: corpses nobody could see."""

    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "payment_paid_email")

    for expected in range(1, DEFAULT_MAX_ATTEMPTS + 1):
        stats = await drain_once(conn, {"payment_paid_email": _always_fails})
        assert stats.failed == 1
        assert (await _row(conn, row_id))["attempts"] == expected

    spent = await drain_once(conn, {"payment_paid_email": _always_fails})
    assert spent.claimed == 0, "an exhausted job must stop being retried"

    counts = await count_undrained(conn)
    assert counts["exhausted"] == 1, "an exhausted job must remain COUNTABLE"
    assert counts["undispatched"] == 1

    still_there = await _row(conn, row_id)
    assert still_there is not None, "counting must never delete"
    assert still_there["dispatched_at"] is None, "counting must never mark dispatched"


async def test_one_poison_job_does_not_roll_back_a_sibling_that_succeeded(conn):
    """One transaction per job. A shared batch transaction fails this."""

    order_id = await _seed_order(conn)
    poison_id = await _enqueue(conn, order_id, "payment_paid_email")
    good_id = await _enqueue(conn, order_id, "refund_email")

    seen: list[OutboxJob] = []
    stats = await drain_once(
        conn,
        {
            "payment_paid_email": _always_fails,
            "refund_email": _recording_handler(seen),
        },
    )

    assert (stats.claimed, stats.dispatched, stats.failed) == (2, 1, 1)
    assert (await _row(conn, poison_id))["dispatched_at"] is None
    assert (await _row(conn, good_id))["dispatched_at"] is not None
    assert [j.job_type for j in seen] == ["refund_email"]


# --------------------------------------------------------------------------
# cancellation is not a handler failure
# --------------------------------------------------------------------------


async def test_a_raised_cancellation_leaves_the_batch_and_charges_no_attempt(conn):
    """`except Exception` must not swallow a `CancelledError`.

    Widening that catch to `BaseException` would look harmless in review and be
    wrong twice over: the interrupted job would be charged an attempt for work
    nobody asked it to finish, and a worker told to shut down would carry on
    delivering customer email for the rest of the batch. Both are pinned here.

    This raises the error rather than cancelling the task, so it proves the
    `except` clause's reach, not the behaviour of a real cancellation while an
    await is in flight — that is the next test.
    """

    order_id = await _seed_order(conn)
    first = await _enqueue(conn, order_id, "payment_paid_email")
    second = await _enqueue(conn, order_id, "payment_paid_email")

    seen: list[OutboxJob] = []

    async def cancels(job: OutboxJob) -> None:
        seen.append(job)
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await drain_once(conn, {"payment_paid_email": cancels})

    assert len(seen) == 1, "the pass must stop at the cancelled job, not continue"

    for row_id in (first, second):
        row = await _row(conn, row_id)
        assert row["attempts"] == 0, "a cancelled attempt is rolled back, not spent"
        assert row["dispatched_at"] is None


async def test_a_real_task_cancellation_rolls_the_attempt_back(conn):
    """The same property under an actual `task.cancel()` mid-await.

    The row is observed from a SECOND connection: the cancelled one is unwinding
    its own transaction, and asking it about the row would be asking the suspect
    to describe the crime. A `wait_for` bounds the read so a row left locked
    fails the test instead of hanging the suite.
    """

    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "payment_paid_email")

    entered = asyncio.Event()

    async def blocks(job: OutboxJob) -> None:
        entered.set()
        await asyncio.sleep(3600)

    task = asyncio.create_task(drain_once(conn, {"payment_paid_email": blocks}))
    await asyncio.wait_for(entered.wait(), timeout=10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    observer = await _connect()
    try:
        row = await asyncio.wait_for(
            observer.fetchrow(
                "SELECT attempts, dispatched_at FROM garuda_order_outbox WHERE id = $1",
                row_id,
            ),
            timeout=10,
        )
    finally:
        await observer.close()

    assert row["attempts"] == 0, "the interrupted attempt must not be charged"
    assert row["dispatched_at"] is None


# --------------------------------------------------------------------------
# unroutable: counted and named, never consumed, budget untouched
# --------------------------------------------------------------------------


async def test_an_unroutable_job_is_reported_and_keeps_its_whole_attempt_budget(conn):
    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "practice_release")

    stats = await drain_once(conn, {})

    assert stats.unroutable == 1
    assert stats.dispatched == 0
    assert "practice_release" in stats.unroutable_types
    row = await _row(conn, row_id)
    assert row["dispatched_at"] is None, "an unrouted job must never look delivered"
    assert row["attempts"] == 0, (
        "the attempt bump must be rolled back — a job nobody tried to deliver "
        "must not burn its budget while waiting for its handler to be written"
    )


async def test_an_unroutable_job_does_not_starve_the_rest_of_the_batch(conn):
    """Goes red if the unroutable row is re-claimed for the whole batch."""

    order_id = await _seed_order(conn)
    await _enqueue(conn, order_id, "practice_release")
    await _enqueue(conn, order_id, "payment_paid_email")

    seen: list[OutboxJob] = []
    stats = await drain_once(conn, {"payment_paid_email": _recording_handler(seen)}, batch_size=5)

    assert stats.unroutable == 1
    assert stats.dispatched == 1
    assert [j.job_type for j in seen] == ["payment_paid_email"]


async def test_registering_the_handler_later_delivers_the_previously_unroutable_job(
    conn,
):
    order_id = await _seed_order(conn)
    row_id = await _enqueue(conn, order_id, "practice_release")

    await drain_once(conn, {})
    seen: list[OutboxJob] = []
    stats = await drain_once(conn, {"practice_release": _recording_handler(seen)})

    assert stats.dispatched == 1
    assert (await _row(conn, row_id))["attempts"] == 1, (
        "the delivered attempt is the FIRST one — earlier unrouted passes must "
        "not have counted against it"
    )


# --------------------------------------------------------------------------
# concurrency: the "email once" claim, actually exercised
# --------------------------------------------------------------------------


async def test_a_job_locked_by_another_worker_is_skipped_not_waited_on(conn):
    """`FOR UPDATE SKIP LOCKED`, proven rather than asserted in a docstring.

    Worker A holds an open transaction on the only job. Worker B must come back
    empty-handed IMMEDIATELY and must not hand that job to its handler — if the
    lock were a plain `FOR UPDATE`, B would block until A finished and this test
    would hang; if there were no lock at all, B would dispatch a second copy of
    a customer email and `seen` would be non-empty.
    """

    order_id = await _seed_order(conn)
    await _enqueue(conn, order_id, "payment_paid_email")

    other = await _connect()
    try:
        tx = other.transaction()
        await tx.start()
        held = await other.fetchrow(
            """
            SELECT id FROM garuda_order_outbox
             WHERE dispatched_at IS NULL
             ORDER BY created_at ASC, id ASC
             LIMIT 1 FOR UPDATE SKIP LOCKED
            """
        )
        assert held is not None, "worker A should have taken the only job"

        seen: list[OutboxJob] = []
        stats = await drain_once(conn, {"payment_paid_email": _recording_handler(seen)})
        assert stats.claimed == 0
        assert seen == [], "the same job must never be dispatched twice"

        await tx.rollback()
    finally:
        await other.close()

    seen_after: list[OutboxJob] = []
    after = await drain_once(conn, {"payment_paid_email": _recording_handler(seen_after)})
    assert after.dispatched == 1, "once released, the job is claimable again"
    assert len(seen_after) == 1


# --------------------------------------------------------------------------
# the probe itself
# --------------------------------------------------------------------------


async def test_count_undrained_reports_every_bucket_and_deletes_nothing(conn):
    order_id = await _seed_order(conn)
    await _enqueue(conn, order_id, "payment_paid_email")
    await _enqueue(conn, order_id, "refund_email")

    before = await count_undrained(conn)
    assert before["undispatched"] == 2
    assert before["exhausted"] == 0
    assert before["older_than_1h"] == 0
    assert before["older_than_24h"] == 0

    seen: list[OutboxJob] = []
    await drain_once(conn, {"payment_paid_email": _recording_handler(seen)})

    after = await count_undrained(conn)
    assert after["undispatched"] == 1, "a dispatched job leaves the undispatched count"
    assert await conn.fetchval("SELECT count(*) FROM garuda_order_outbox") == 2, (
        "reporting must never remove a row"
    )
