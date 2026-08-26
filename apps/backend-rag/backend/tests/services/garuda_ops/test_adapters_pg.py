"""Real-database tests for the concrete L7 handoff adapters.

The point of this suite is the one thing an in-memory fake structurally cannot
check. `ports.py::CrmWriter` requires a real adapter to move idempotency INTO
the database, because `CrmHandoffService` does check-then-act across two awaits
and two concurrent deliveries can both observe `None`. A single-threaded fake
satisfies every other test in the repo while being wide open to that race, so
`test_two_concurrent_writers_racing_the_same_key_create_exactly_one_practice`
runs two genuinely concurrent writers on two connections and counts rows. If
`ON CONFLICT` were dropped from the insert, that test — and only that test —
goes red.

DSN: `INTAKE_TEST_DSN` (what CI sets), `GARUDA_L3_TEST_DSN` as a local
override, matching the sibling garuda suites. In CI a connection failure fails
rather than skips: a skip in a gate is a fail-open.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_ops.adapters_pg import (
    MissingCustomerName,
    PostgresCrmWriter,
    PostgresOrderSnapshotProvider,
)
from backend.services.garuda_ops.ports import OrderSnapshot

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/garuda_outbox_test_0826"
)

pytestmark = pytest.mark.asyncio

PRACTICE_TYPE = "VOA"


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(_DSN, min_size=2, max_size=6)
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
            await conn.execute("DELETE FROM practices WHERE source_idempotency_key IS NOT NULL")
            await conn.execute("DELETE FROM clients WHERE email LIKE '%@example.invalid'")
        yield p
    finally:
        await p.close()


# --------------------------------------------------------------------------
# seeding: the real tables, the real column names
# --------------------------------------------------------------------------


async def _seed_full_case(
    pool, *, email: str = "traveller@example.invalid", full_name: str = "SPECIMEN TRAVELLER"
) -> tuple[str, str]:
    """Create check -> order -> journal event -> practice. Returns (practice_id, event_id)."""

    result_id = f"chk_{uuid.uuid4().hex}"  # also seeds session_secret_hash (UNIQUE)
    order_id = f"ord_{uuid.uuid4().hex}"
    practice_id = f"prc_{uuid.uuid4().hex}"
    event_id = f"evt_{uuid.uuid4().hex}"

    async with pool.acquire() as conn:
        # The check-results table is fail-closed by design (D2): a trigger
        # refuses any INSERT that has no active retention policy for its scope,
        # which is why L2 could not build a check store before L1 shipped one.
        # A test fixture must therefore seed a policy rather than work around
        # the trigger — disabling it would be testing a table that does not
        # exist in production. `environment = 'test'` matches the check row.
        await conn.execute(
            """
            INSERT INTO visa_decision_retention_policies
                (environment, policy_version, retention_interval,
                 idempotency_retention_interval, legal_hold_review_interval,
                 retention_anchor, effective_period, approved_by,
                 approval_reference, policy_scope)
            SELECT 'TEST', 'test-fixture-' || gen_random_uuid(), INTERVAL '30 days',
                   -- A UNIQUE (environment, policy_scope, policy_version)
                   -- exists, and sibling suites CLOSE the periods they
                   -- seeded rather than deleting the rows. A fixed version
                   -- string therefore collides with a closed policy from an
                   -- earlier module in the same run, even though the guard
                   -- below correctly found no ACTIVE one.
                   INTERVAL '30 days', INTERVAL '7 days',
                   'CREATED_AT', tstzrange(now(), NULL, '[)'),
                   -- Starts at now(), NOT in the past: an exclusion
                   -- constraint forbids overlapping periods per
                   -- (environment, scope), and this table is full of
                   -- closed ranges left by sibling suites. `[)` includes
                   -- the lower bound, and the check row's created_at is
                   -- the same transaction clock, so it lands inside.
                   'test-fixture', 'adapters_pg test fixture', 'GARUDA_CHECK'
             WHERE NOT EXISTS (
                SELECT 1 FROM visa_decision_retention_policies
                 WHERE policy_scope = 'GARUDA_CHECK' AND environment = 'TEST'
                   -- `@> now()` is load-bearing, not defensive padding. Sibling
                   -- garuda suites seed policies and then CLOSE their effective
                   -- period, so this table routinely holds dozens of rows that
                   -- match scope+environment and satisfy the trigger for none
                   -- of them. Without this clause the guard sees "a policy
                   -- exists", skips the insert, and every check-result INSERT
                   -- then fails with "no active Zero-approved retention policy".
                   AND effective_period @> now()
             )
            """
        )
        await conn.execute(
            """
            INSERT INTO garuda_voa_check_results
                (result_id, session_secret_hash, environment, case_type, nationality,
                 entry_date, passport_expiry_date, extension_already_used, purpose,
                 travellers, self_pay, decision, reason_codes,
                 published_filing_deadline, price_idr, price_source,
                 retention_notice_acknowledged_at)
            VALUES ($1, substr(md5($1) || md5($1 || 'x'), 1, 64), 'TEST', 'issuance', 'ITA',
                    DATE '2026-09-20', DATE '2031-01-01', false, 'tourism',
                    1, true, 'ACCEPT', '[]'::jsonb,
                    DATE '2026-10-13', 790000, 'B1 Visa on Arrival (VOA)',
                    -- `created_at` is deliberately left to its default: a
                    -- trigger on this table rejects any value that is not the
                    -- transaction clock, so passing statement_timestamp()
                    -- here fails with "must use the database transaction clock".
                    transaction_timestamp())
            """,
            result_id,
        )
        await conn.execute(
            """
            INSERT INTO garuda_orders
                (order_id, result_id_ref, case_type, applicant_full_name,
                 applicant_email, applicant_phone, applicant_passport_number,
                 price_idr, price_catalogue_key, state)
            VALUES ($1, $2, 'issuance', $3, $4, '+000000000000', 'X0000000',
                    790000, 'B1 Visa on Arrival (VOA)', 'paid')
            """,
            order_id,
            result_id,
            full_name,
            email,
        )
        await conn.execute(
            """
            INSERT INTO garuda_order_journal
                (event_id, event_name, aggregate_type, aggregate_id,
                 transition_id, customer_visible)
            VALUES ($1, 'payment.paid', 'order', $2, 'OP-02', true)
            """,
            event_id,
            order_id,
        )
        await conn.execute(
            """
            INSERT INTO garuda_practices
                (practice_id, order_id, state, source_paid_journal_event_id)
            VALUES ($1, $2, 'Received', $3)
            """,
            practice_id,
            order_id,
            event_id,
        )
    return practice_id, event_id


def _snapshot(**over) -> OrderSnapshot:
    base = {
        "order_aggregate_id": f"ord_{uuid.uuid4().hex}",
        "customer_email": "traveller@example.invalid",
        "customer_full_name": "SPECIMEN TRAVELLER",
        "case_type": "issuance",
        "purpose": "tourism",
        "nationality": "ITA",
        "entry_date": date(2026, 9, 20),
        "price_idr": 790000,
        "submit_by_date": None,
    }
    base.update(over)
    return OrderSnapshot(**base)


# --------------------------------------------------------------------------
# the snapshot provider
# --------------------------------------------------------------------------


async def test_the_provider_walks_practice_to_order_to_check(pool):
    practice_id, _ = await _seed_full_case(pool)

    snap = await PostgresOrderSnapshotProvider(pool).get(practice_id)

    assert snap is not None
    assert snap.customer_email == "traveller@example.invalid"
    assert snap.customer_full_name == "SPECIMEN TRAVELLER"
    assert snap.case_type == "issuance"
    assert snap.price_idr == 790000
    # These three live on the CHECK row, not the order — the middle hop of the
    # join is what supplies them, so this pins that the join is real.
    assert snap.purpose == "tourism"
    assert snap.nationality == "ITA"
    assert snap.entry_date == date(2026, 9, 20)


async def test_the_provider_returns_none_for_an_unknown_practice(pool):
    assert await PostgresOrderSnapshotProvider(pool).get("prc_does_not_exist_0000") is None


async def test_the_provider_refuses_to_invent_fields_when_the_check_is_gone(pool):
    """`result_id_ref` is a soft cross-lane reference: the check CAN disappear.

    Retention deletion is the expected cause. The adapter must return None
    rather than a snapshot with guessed purpose/nationality/entry_date — this
    test goes red if someone "helpfully" defaults those.
    """

    practice_id, _ = await _seed_full_case(pool)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM garuda_voa_check_results")

    assert await PostgresOrderSnapshotProvider(pool).get(practice_id) is None


async def test_submit_by_date_is_none_and_not_the_published_deadline(pool):
    """The seeded check carries published_filing_deadline = 2026-10-13.

    Silently reusing it as the operating-calendar commitment would be a
    plausible invention: they are different dates. Pin that we do not.
    """

    practice_id, _ = await _seed_full_case(pool)
    snap = await PostgresOrderSnapshotProvider(pool).get(practice_id)
    assert snap is not None
    assert snap.submit_by_date is None


# --------------------------------------------------------------------------
# the CRM writer
# --------------------------------------------------------------------------


async def test_a_write_creates_one_client_and_one_practice(pool):
    writer = PostgresCrmWriter(pool)
    key = f"evt_{uuid.uuid4().hex}"

    practice_id = await writer.create_client_and_practice(
        _snapshot(), source_idempotency_key=key, practice_type_code=PRACTICE_TYPE
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT client_id, practice_type_code, quoted_price, currency, "
            "source_idempotency_key FROM practices WHERE id = $1",
            practice_id,
        )
        assert row["source_idempotency_key"] == key
        assert row["practice_type_code"] == PRACTICE_TYPE
        assert int(row["quoted_price"]) == 790000
        assert row["currency"] == "IDR"
        client_email = await conn.fetchval(
            "SELECT email FROM clients WHERE id = $1", row["client_id"]
        )
        assert client_email == "traveller@example.invalid"

    assert await writer.find_practice_by_source_idempotency_key(key) == practice_id


async def test_the_practice_title_carries_no_applicant_identity(pool):
    """SYMBIOSIS Law 2: the CRM title must not transcribe the traveller."""

    writer = PostgresCrmWriter(pool)
    key = f"evt_{uuid.uuid4().hex}"
    practice_id = await writer.create_client_and_practice(
        _snapshot(customer_full_name="Jane Q Specimen"),
        source_idempotency_key=key,
        practice_type_code=PRACTICE_TYPE,
    )
    async with pool.acquire() as conn:
        title = await conn.fetchval("SELECT title FROM practices WHERE id = $1", practice_id)
    assert "Specimen" not in title
    assert "Jane" not in title


async def test_a_sequential_retry_returns_the_same_practice(pool):
    writer = PostgresCrmWriter(pool)
    key = f"evt_{uuid.uuid4().hex}"

    first = await writer.create_client_and_practice(
        _snapshot(), source_idempotency_key=key, practice_type_code=PRACTICE_TYPE
    )
    second = await writer.create_client_and_practice(
        _snapshot(), source_idempotency_key=key, practice_type_code=PRACTICE_TYPE
    )

    assert first == second
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices WHERE source_idempotency_key = $1", key
            )
            == 1
        )


async def test_two_concurrent_writers_racing_the_same_key_create_exactly_one_practice(
    pool,
):
    """THE test this whole module exists for.

    `CrmHandoffService` does check-then-act across two awaits, so two
    deliveries of the same payment event can both see "no practice yet". The
    port's docstring demands the database settle it. Both writers run on their
    own pooled connections, started together — remove the `ON CONFLICT` from
    `create_client_and_practice` and this produces two practices for one
    payment while every sequential test above stays green.
    """

    writer_a = PostgresCrmWriter(pool)
    writer_b = PostgresCrmWriter(pool)
    key = f"evt_{uuid.uuid4().hex}"

    a, b = await asyncio.gather(
        writer_a.create_client_and_practice(
            _snapshot(), source_idempotency_key=key, practice_type_code=PRACTICE_TYPE
        ),
        writer_b.create_client_and_practice(
            _snapshot(), source_idempotency_key=key, practice_type_code=PRACTICE_TYPE
        ),
    )

    assert a == b, "both deliveries must resolve to the SAME practice"
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices WHERE source_idempotency_key = $1", key
            )
            == 1
        ), "one payment must never produce two CRM practices"


async def test_two_concurrent_orders_from_one_customer_create_one_client(pool):
    """The same race, one level down: the client row must not double either."""

    writer = PostgresCrmWriter(pool)
    email = "repeat.customer@example.invalid"

    await asyncio.gather(
        writer.create_client_and_practice(
            _snapshot(customer_email=email),
            source_idempotency_key=f"evt_{uuid.uuid4().hex}",
            practice_type_code=PRACTICE_TYPE,
        ),
        writer.create_client_and_practice(
            _snapshot(customer_email=email),
            source_idempotency_key=f"evt_{uuid.uuid4().hex}",
            practice_type_code=PRACTICE_TYPE,
        ),
    )

    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM clients WHERE LOWER(BTRIM(email)) = $1", email
            )
            == 1
        )


async def test_email_case_and_whitespace_resolve_to_the_same_client(pool):
    """Matches `uq_clients_email_lower_not_blank` (migration 166) exactly.

    A lookup on bare `LOWER(email)` would miss a stored address with trailing
    whitespace and create a duplicate client — the mismatch this normalization
    exists to close.
    """

    writer = PostgresCrmWriter(pool)
    await writer.create_client_and_practice(
        _snapshot(customer_email="  Mixed.Case@Example.invalid "),
        source_idempotency_key=f"evt_{uuid.uuid4().hex}",
        practice_type_code=PRACTICE_TYPE,
    )
    await writer.create_client_and_practice(
        _snapshot(customer_email="mixed.case@example.invalid"),
        source_idempotency_key=f"evt_{uuid.uuid4().hex}",
        practice_type_code=PRACTICE_TYPE,
    )

    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM clients WHERE LOWER(BTRIM(email)) = $1",
                "mixed.case@example.invalid",
            )
            == 1
        )


async def test_a_nameless_snapshot_is_refused_and_writes_nothing(pool):
    """`clients.full_name` is NOT NULL; a placeholder would look like data."""

    writer = PostgresCrmWriter(pool)
    key = f"evt_{uuid.uuid4().hex}"

    with pytest.raises(MissingCustomerName):
        await writer.create_client_and_practice(
            _snapshot(customer_full_name=None),
            source_idempotency_key=key,
            practice_type_code=PRACTICE_TYPE,
        )

    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices WHERE source_idempotency_key = $1", key
            )
            == 0
        )


async def test_a_blank_name_is_refused_too(pool):
    with pytest.raises(MissingCustomerName):
        await PostgresCrmWriter(pool).create_client_and_practice(
            _snapshot(customer_full_name="   "),
            source_idempotency_key=f"evt_{uuid.uuid4().hex}",
            practice_type_code=PRACTICE_TYPE,
        )


async def test_find_returns_none_for_an_unknown_key(pool):
    assert (
        await PostgresCrmWriter(pool).find_practice_by_source_idempotency_key("evt_never_written")
        is None
    )


async def test_pre_existing_human_created_practices_are_untouched_by_the_index(pool):
    """The partial unique index must not constrain the CRM's own rows.

    Every practice created by a human has a NULL key. Two of them must coexist
    — a non-partial unique index over a NOT NULL column would forbid this, and
    the migration's whole nullable/partial design exists for it.
    """

    async with pool.acquire() as conn:
        client_id = await conn.fetchval(
            "INSERT INTO clients (full_name, email) VALUES "
            "('HUMAN ENTERED', 'human@example.invalid') RETURNING id"
        )
        first = await conn.fetchval(
            "INSERT INTO practices (client_id, title) VALUES ($1, 'manual A') RETURNING id",
            client_id,
        )
        second = await conn.fetchval(
            "INSERT INTO practices (client_id, title) VALUES ($1, 'manual B') RETURNING id",
            client_id,
        )
        assert first != second
        await conn.execute("DELETE FROM practices WHERE id = ANY($1::int[])", [first, second])
