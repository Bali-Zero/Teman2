"""Crossing test: the two independent producers of a `garuda_practices`
`Received` row.

**Correction to the mandate this file was written against — verified on disk
this session, recorded here because it changes what the file actually
compares.** The dispatch asked to cross `PracticeReleaseHandler`
(`garuda_orders/outbox_handlers.py`) against
`PracticeRepository.get_order_and_practice_view` as the two producers of a
`Received` GARUDA practice. That is not what the code does.
`PracticeReleaseHandler.__call__` (`outbox_handlers.py:279-311`) starts with
`_practice_id_for`, a plain `SELECT ... FROM garuda_practices` — it RAISES
`PracticeNotMinted` if no row exists yet (`outbox_handlers.py:281-289`: "no
`garuda_practices` row ... Raise: it must exhaust ... never be marked
delivered"). It never inserts into `garuda_practices`. Its write target is
`practices` (the CRM table `PostgresCrmWriter` owns) — a different table
with a different schema (`status`, `payment_status`, `practice_type_code`,
`actual_price`, `paid_amount`, `assigned_to`, `created_by`; see
`test_outbox_handlers.py::
test_a_release_job_creates_the_crm_practice_and_marks_itself_dispatched`),
joined to the payment only via
`practices.source_idempotency_key = sha256(journal_event_id)`. It is a
downstream CONSUMER of an already-minted `garuda_practices` row, not a
second producer of one. Comparing its output field-by-field against
`garuda_practices` would be comparing two unrelated schemas — not a real
crossing test, a category error.

**The two real, independent call sites** that mint a `garuda_practices`
`Received` row both funnel into the SAME function,
`garuda_portal.practice.mint_received_practice` — from genuinely different
callers with different transactional context:

  * EAGER — `GarudaOrderRepository.handle_paid_event` (`repository.py:451`)
    calls it directly, inside the SAME transaction that flips
    `garuda_orders.state` to `paid` and appends the `payment.paid`/OP-02
    journal event.
  * LAZY  — `PracticeRepository._create_received_practice` (`practice.py`),
    reached from `get_order_and_practice_view` (`practice.py:163-168`) when
    a caller reads a paid order that has no practice row yet.

In the current wiring EAGER always wins for a normally-paid order — the
sibling suite (`test_practice.py::
test_a_paid_order_that_the_customer_never_looks_at_still_gets_a_practice`
and `::test_concurrent_reads_of_a_paid_order_never_duplicate_pr01`) already
establishes this, because `garuda_orders.state = 'paid'` and the
`garuda_practices` row are written in the SAME transaction — so LAZY is a
dead branch on the happy path, reachable only if a `garuda_practices` row
for an already-paid order goes missing. That is exactly the condition
`PracticeReleaseHandler` itself treats as a hard failure
(`test_outbox_handlers.py::
test_a_release_job_without_its_practice_row_raises_and_stays_undispatched`).
This file forces that gap open on purpose — deleting the eagerly-minted row
for one order, the same scenario the codebase already contemplates as a
real failure mode — so BOTH producers can be observed writing for real, on
their own orders, and their output compared.
"""

from __future__ import annotations

import asyncio
import os

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_orders.repository import GarudaOrderRepository
from backend.services.garuda_portal.practice import PracticeRepository
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

# Reused verbatim rather than re-implemented (scar W96 / the sibling file's
# own comment on why): a policy row is a Zero-approved business decision,
# never a migration default, and `create_order_and_checkout` gates on it.
from backend.tests.services.garuda_portal.test_practice import (
    _close_garuda_order_test_policy,
    _create_and_pay_order,
    _ensure_garuda_order_test_policy,
    _FakeLookup,
    _FakeProvider,
)

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)

pytestmark = pytest.mark.asyncio

# Columns this file does NOT compare across the two orders, and why each is
# legitimately excluded:
#   practice_id                  -- minted fresh (`journal.new_opaque_id`)
#                                    per INSERT; equality across two
#                                    different orders would be a collision,
#                                    not agreement.
#   order_id                     -- each row belongs to its own order by
#                                    construction (UNIQUE FK); comparing
#                                    these across orders is meaningless.
#   created_at / updated_at      -- `statement_timestamp()` defaults;
#                                    genuinely time-varying, never equal
#                                    across two separate transactions.
#   source_paid_journal_event_id -- differs by order (one OP-02 event per
#                                    order) but is NOT skipped: each row is
#                                    checked against ITS OWN order's OP-02
#                                    event id below, which is a stronger
#                                    check than blanket exclusion.
_EXCLUDED_COLUMNS = {
    "practice_id",
    "order_id",
    "created_at",
    "updated_at",
    "source_paid_journal_event_id",
}


@pytest.fixture
async def pool():
    try:
        p = await create_prod_shaped_pool(_DSN, min_size=1, max_size=4)
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for INTAKE_TEST_DSN "
                f"(or GARUDA_L3_TEST_DSN override) -- {_DSN!r} unreachable: {exc}. "
                f"This surface creates rows for a paid order; it must never "
                f"silently pass by skipping."
            )
        pytest.skip(f"no local Postgres reachable at {_DSN}: {exc}")
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE garuda_practices, garuda_order_outbox, garuda_order_journal, "
            "garuda_payment_inbox, garuda_order_idempotency, garuda_orders CASCADE"
        )
        policy_version = await _ensure_garuda_order_test_policy(conn)
    yield p
    async with p.acquire() as conn:
        await _close_garuda_order_test_policy(conn, policy_version)
    await p.close()


@pytest.fixture
def order_repository(pool, monkeypatch):
    import backend.services.garuda_orders.repository as repository_module

    monkeypatch.setattr(
        repository_module.pricing,
        "price_for_case",
        lambda case_type, *, today: (790_000, "B1 Visa on Arrival (VOA)"),
    )
    return GarudaOrderRepository(
        pool, eligibility_lookup=_FakeLookup(), provider=_FakeProvider(), environment="TEST"
    )


@pytest.fixture
def practice_repository(pool) -> PracticeRepository:
    return PracticeRepository(pool)


async def _op02_event_id(pool, order_id: str) -> str:
    """The order's own `payment.paid`/OP-02 journal event id -- the
    idempotency anchor both producers must key their practice row to."""
    event_id = await pool.fetchval(
        """
        SELECT event_id FROM garuda_order_journal
        WHERE aggregate_type = 'order' AND aggregate_id = $1 AND transition_id = 'OP-02'
        ORDER BY occurred_at ASC LIMIT 1
        """,
        order_id,
    )
    assert event_id is not None, f"no OP-02 event recorded for order {order_id}"
    return event_id


async def _practice_row(pool, order_id: str):
    row = await pool.fetchrow("SELECT * FROM garuda_practices WHERE order_id = $1", order_id)
    assert row is not None, f"no garuda_practices row for order {order_id}"
    return dict(row)


def _normalized(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in _EXCLUDED_COLUMNS}


@pytest.mark.asyncio
async def test_eager_and_lazy_producers_write_equivalent_practice_rows(
    pool, order_repository, practice_repository
):
    """PATH A (eager): `handle_paid_event` mints the row -- nobody ever
    calls `PracticeRepository` for this order.

    PATH B (lazy): `handle_paid_event` also mints eagerly (it always does,
    per the module docstrings above), so the eagerly-minted row is deleted
    to reopen the exact gap `PracticeReleaseHandler` treats as fatal --
    then `get_order_and_practice_view` is called, which is the ONLY other
    code path in this repository that can mint a `garuda_practices` row.
    """
    # --- Path A: eager only, order never read through PracticeRepository ---
    order_a = await _create_and_pay_order(
        order_repository, result_id="result-eager-000000000", provider_event_id="evt-eager-1"
    )
    row_a = await _practice_row(pool, order_a)
    event_a = await _op02_event_id(pool, order_a)

    # --- Path B: eager fires too (unavoidable), then the row is deleted to
    # force the lazy branch to actually run, exactly the scenario
    # `PracticeRepository._create_received_practice`'s docstring defends
    # against ("this should be unreachable for a genuinely paid order ...
    # Logged, not raised").
    order_b = await _create_and_pay_order(
        order_repository, result_id="result-lazy-0000000000", provider_event_id="evt-lazy-1"
    )
    event_b = await _op02_event_id(pool, order_b)
    async with pool.acquire() as conn:
        deleted = await conn.execute(
            "DELETE FROM garuda_practices WHERE order_id = $1", order_b
        )
    assert deleted == "DELETE 1", "setup failed: eager path did not mint a row to delete"

    count_before_lazy = await pool.fetchval(
        "SELECT count(*) FROM garuda_practices WHERE order_id = $1", order_b
    )
    assert count_before_lazy == 0, "gap not actually open before invoking the lazy path"

    view_b = await practice_repository.get_order_and_practice_view(
        order_id=order_b, result_id_ref="result-lazy-0000000000"
    )
    assert view_b is not None
    assert view_b["practice"] is not None, "lazy path did not mint a replacement practice"
    row_b = await _practice_row(pool, order_b)

    # --- The actual cross-check: both rows carry the SAME shape. ---
    normalized_a = _normalized(row_a)
    normalized_b = _normalized(row_b)
    assert normalized_a == normalized_b, (
        f"eager and lazy producers disagree on practice row shape: "
        f"eager={normalized_a!r} lazy={normalized_b!r}"
    )
    assert normalized_a["state"] == "Received"
    assert normalized_a["artifact_available"] is False
    assert normalized_a["customer_reason_key"] is None
    assert normalized_a["required_action_key"] is None
    assert normalized_a["private_staff_note"] is None
    assert normalized_a["resume_target"] is None
    assert normalized_a["artifact_id"] is None
    assert normalized_a["artifact_digest"] is None

    # --- Each row's idempotency anchor is checked against ITS OWN order's
    # OP-02 event, not against each other (excluded from the blanket
    # comparison above precisely because it must differ across orders). ---
    assert row_a["source_paid_journal_event_id"] == event_a
    assert row_b["source_paid_journal_event_id"] == event_b
    # And the lazy path re-used the SAME OP-02 event that already existed
    # (it looked it up, never minted a new payment event) -- this is what
    # makes the replacement row idempotency-anchored to the original
    # payment rather than a fabricated do-over.
    assert row_b["source_paid_journal_event_id"] == event_b

    # --- Both producers must have appended their own PR-01 journal event
    # and enqueued their own confirmation-email job -- on their own
    # practice_id, not a shared/leaked one. ---
    for row, order_id in ((row_a, order_a), (row_b, order_b)):
        journal_row = await pool.fetchrow(
            "SELECT event_id FROM garuda_order_journal "
            "WHERE aggregate_type = 'practice' AND transition_id = 'PR-01' AND aggregate_id = $1",
            row["practice_id"],
        )
        assert journal_row is not None, f"no PR-01 journal event for {order_id}'s practice"
        outbox_row = await pool.fetchrow(
            "SELECT job_type FROM garuda_order_outbox "
            "WHERE order_id = $1 AND job_type = 'practice_received_email'",
            order_id,
        )
        assert outbox_row is not None, f"no confirmation-email job enqueued for {order_id}"


@pytest.mark.asyncio
async def test_handler_then_read_same_order_never_duplicates(
    pool, order_repository, practice_repository
):
    """Ordering case 1: EAGER fires (payment), then LAZY reads the SAME
    order repeatedly. Must observe the eager row, never mint a second
    one."""
    order_id = await _create_and_pay_order(
        order_repository, result_id="result-order1-00000000", provider_event_id="evt-order1"
    )
    row_before = await _practice_row(pool, order_id)

    for _ in range(3):
        view = await practice_repository.get_order_and_practice_view(
            order_id=order_id, result_id_ref="result-order1-00000000"
        )
        assert view["practice"]["practice_id"] == row_before["practice_id"]

    count = await pool.fetchval(
        "SELECT count(*) FROM garuda_practices WHERE order_id = $1", order_id
    )
    assert count == 1
    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal "
        "WHERE aggregate_type = 'practice' AND transition_id = 'PR-01' AND aggregate_id = $1",
        row_before["practice_id"],
    )
    assert journal_count == 1


@pytest.mark.asyncio
async def test_read_then_handler_gap_recovery_never_duplicates(pool, order_repository, practice_repository):
    """Ordering case 2: EAGER already ran (payment), its row is then LOST
    (the same fatal condition `PracticeReleaseHandler` guards against),
    and LAZY reads repeatedly -- concurrently -- to refill the gap. Exactly
    one winner, exactly one row, exactly one PR-01 journal event must
    survive, no matter how many lazy readers race to fill the same gap.
    This is the scenario `source_paid_journal_event_id`'s UNIQUE constraint
    (migration 287) exists to make structural."""
    order_id = await _create_and_pay_order(
        order_repository, result_id="result-order2-00000000", provider_event_id="evt-order2"
    )
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM garuda_practices WHERE order_id = $1", order_id)

    results = await asyncio.gather(
        *(
            practice_repository.get_order_and_practice_view(
                order_id=order_id, result_id_ref="result-order2-00000000"
            )
            for _ in range(5)
        )
    )
    practice_ids = {r["practice"]["practice_id"] for r in results if r and r["practice"]}
    assert len(practice_ids) == 1, f"racing lazy refills minted more than one practice: {practice_ids}"

    count = await pool.fetchval(
        "SELECT count(*) FROM garuda_practices WHERE order_id = $1", order_id
    )
    assert count == 1
    journal_count = await pool.fetchval(
        "SELECT count(*) FROM garuda_order_journal "
        "WHERE aggregate_type = 'practice' AND transition_id = 'PR-01' AND aggregate_id = $1",
        practice_ids.pop(),
    )
    assert journal_count == 1
