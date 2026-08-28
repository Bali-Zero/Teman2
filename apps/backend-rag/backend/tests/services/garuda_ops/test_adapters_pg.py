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

import ast
import asyncio
import inspect
import os
import textwrap
import uuid
from datetime import date

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.services.garuda_ops.adapters_pg import (
    CREATED_BY_GARUDA,
    MissingCustomerEmail,
    MissingCustomerIdentity,
    MissingCustomerName,
    PostgresCrmWriter,
    PostgresOrderSnapshotProvider,
    UnknownPracticeType,
)
from backend.services.garuda_ops.ports import OrderSnapshot

_DSN = (
    os.environ.get("GARUDA_L3_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/garuda_outbox_test_0826"
)

pytestmark = pytest.mark.asyncio

#: A code that is really in the `practice_types` catalogue (migration 221).
#: It used to be the string "VOA", which matches NO row — so every test wrote a
#: practice whose type could not be resolved, and the suite could not have
#: noticed that the adapter left `practice_type_id` NULL.
PRACTICE_TYPE = "visa_b1_voa"


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
            # Two deletes, in this order, and the SECOND is not redundant.
            # The first clears rows this suite's adapter wrote (they all carry a
            # key). The second clears rows a test wrote with a NULL key — which
            # the first cannot see — and it must run BEFORE the client delete or
            # `practices_client_id_fkey` rejects it. Found the hard way: a test
            # that inserts a NULL-key practice to demonstrate what the partial
            # index does NOT constrain left the client undeletable, and every
            # later test in the file errored in teardown rather than in its own
            # body, which points the blame at the wrong test.
            await conn.execute("DELETE FROM practices WHERE source_idempotency_key IS NOT NULL")
            await conn.execute(
                "DELETE FROM practices WHERE client_id IN "
                "(SELECT id FROM clients WHERE email LIKE '%@example.invalid')"
            )
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


async def test_a_missing_email_raises_its_OWN_exception_not_the_name_one(pool):
    """The exception must name the field that is actually absent.

    Both refusals used to raise `MissingCustomerName`, including the one for a
    missing EMAIL — so a caller or an alert branching on the class could not
    tell the two apart without parsing the message string, and the class name
    was false at half its raise sites. The assertion that carries the weight is
    the NEGATIVE one: raising the base class alone would satisfy `pytest.raises`
    on a subclass check, but not `not isinstance(..., MissingCustomerName)`.
    """

    key = f"evt_{uuid.uuid4().hex}"

    with pytest.raises(MissingCustomerEmail) as caught:
        await PostgresCrmWriter(pool).create_client_and_practice(
            _snapshot(customer_full_name="SPECIMEN TRAVELLER", customer_email="   "),
            source_idempotency_key=key,
            practice_type_code=PRACTICE_TYPE,
        )

    assert not isinstance(caught.value, MissingCustomerName), (
        "a missing email must not be reported as a missing name"
    )
    assert isinstance(caught.value, MissingCustomerIdentity), (
        "both refusals must stay catchable as one 'snapshot not identifiable' class"
    )

    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices WHERE source_idempotency_key = $1", key
            )
            == 0
        ), "a refused snapshot must leave no half-written practice"
        # The CLIENT assertion is the one that carries weight here, and it was
        # missing: unlike the name and key guards, the email guard raises INSIDE
        # the open transaction, so this is the only refusal path where a client
        # row could survive a rollback that did not happen.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM clients WHERE email LIKE $1",
                "%@example.invalid",
            )
            == 0
        ), "a refusal inside the transaction must roll the client back too"


@pytest.mark.parametrize("bad_key", ["", "   "])
async def test_an_empty_idempotency_key_is_refused_before_it_can_duplicate(pool, bad_key):
    """A blank key defeats the whole point of the adapter, silently.

    A falsy key fails in TWO directions, and the guard refuses both. NULL is
    outside the partial index (`WHERE source_idempotency_key IS NOT NULL`), so
    it arbitrates against nothing and one payment retried three times becomes
    three CRM practices. A blank STRING is INSIDE that index, so it does
    arbitrate — and every blank-key order in the system collapses onto one
    shared practice, which is silent and lossy. The `str` annotation catches
    neither: it is a hint, not a check.
    """

    with pytest.raises(ValueError, match="source_idempotency_key"):
        await PostgresCrmWriter(pool).create_client_and_practice(
            _snapshot(),
            source_idempotency_key=bad_key,
            practice_type_code=PRACTICE_TYPE,
        )


async def test_only_a_NULL_key_escapes_the_index_a_blank_STRING_collides(pool):
    """What a falsy key actually does — measured, because the first version of
    this test asserted the opposite and was wrong.

    The guard's original rationale said a blank key "inserts every single time"
    and duplicates. False for a blank STRING: `''` satisfies `IS NOT NULL`, so
    it is INSIDE the partial index and IS arbitrated — two blank-string keys
    collapse onto ONE practice. Only NULL escapes the index and duplicates.

    So the hazard has two faces and the guard is right for both: NULL
    duplicates (one payment, many practices), a blank string COLLIDES (many
    different payments, one shared practice, which is worse because it is
    silent and lossy). This test pins both directions, in raw SQL, because the
    adapter now refuses to produce either.
    """

    async with pool.acquire() as conn:
        client_id = await conn.fetchval(
            "INSERT INTO clients (full_name, email) VALUES ($1, $2) RETURNING id",
            "SPECIMEN TRAVELLER",
            f"blank-key-{uuid.uuid4().hex}@example.invalid",
        )
        type_id = await conn.fetchval(
            "SELECT id FROM practice_types WHERE code = $1", PRACTICE_TYPE
        )
        insert = """
            INSERT INTO practices
                (client_id, practice_type_id, practice_type_code, title,
                 quoted_price, currency, source_idempotency_key)
            VALUES ($1, $2, $3, 'falsy key probe', 1, 'IDR', $4)
            ON CONFLICT (source_idempotency_key)
                WHERE source_idempotency_key IS NOT NULL
                DO NOTHING
        """

        for _ in range(2):
            await conn.execute(insert, client_id, type_id, PRACTICE_TYPE, None)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices "
                "WHERE client_id = $1 AND source_idempotency_key IS NULL",
                client_id,
            )
            == 2
        ), "NULL is outside the partial index, so it DUPLICATES"

        for _ in range(2):
            await conn.execute(insert, client_id, type_id, PRACTICE_TYPE, "")
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices "
                "WHERE client_id = $1 AND source_idempotency_key = ''",
                client_id,
            )
            == 1
        ), "a blank STRING is inside the index, so it COLLIDES onto one row"


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
        # `practice_type_id` is supplied because a real human-created practice
        # has one: `crm/models.py` declares the column NOT NULL and every live
        # writer passes it. Omitting it here worked only because
        # `scripts/ci_bootstrap_schema.py` drops that constraint for CI — this
        # test was the SECOND place in the file resting on a constraint CI
        # removes, and it failed the moment the constraint was restored.
        type_id = await conn.fetchval(
            "SELECT id FROM practice_types WHERE code = $1", PRACTICE_TYPE
        )
        first = await conn.fetchval(
            "INSERT INTO practices (client_id, practice_type_id, title) "
            "VALUES ($1, $2, 'manual A') RETURNING id",
            client_id,
            type_id,
        )
        second = await conn.fetchval(
            "INSERT INTO practices (client_id, practice_type_id, title) "
            "VALUES ($1, $2, 'manual B') RETURNING id",
            client_id,
            type_id,
        )
        assert first != second
        await conn.execute("DELETE FROM practices WHERE id = ANY($1::int[])", [first, second])


# --------------------------------------------------------------------------
# the practice must be VISIBLE, not merely present
# --------------------------------------------------------------------------


async def test_the_practice_carries_a_resolved_practice_type_id(pool):
    """A NULL `practice_type_id` makes the row invisible, not merely incomplete.

    The CRM joins `practice_types` on `p.practice_type_id = pt.id` with an INNER
    join in its list, analytics, dashboard and shared-memory queries
    (crm_practices, crm_clients, crm_analytics, crm_enhanced, crm_interactions,
    crm_shared_memory). A practice with NULL there is silently dropped from all
    of them: the customer paid, the row exists, and no surface shows it.

    The first draft of this adapter wrote only `practice_type_code`. No test in
    this file could have caught it, because `scripts/ci_bootstrap_schema.py`
    runs `ALTER TABLE practices ALTER COLUMN practice_type_id DROP NOT NULL`
    while `crm/models.py` declares the column NOT NULL — so the green suite was
    resting on a constraint CI removes.
    """

    key = f"evt_{uuid.uuid4().hex}"
    practice_id = await PostgresCrmWriter(pool).create_client_and_practice(
        _snapshot(), source_idempotency_key=key, practice_type_code=PRACTICE_TYPE
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT practice_type_id, practice_type_code FROM practices WHERE id = $1",
            practice_id,
        )
        assert row["practice_type_id"] is not None, (
            "a NULL practice_type_id drops this row out of every CRM inner join"
        )
        expected = await conn.fetchval(
            "SELECT id FROM practice_types WHERE code = $1", PRACTICE_TYPE
        )
        assert row["practice_type_id"] == expected
        assert row["practice_type_code"] == PRACTICE_TYPE

        # The assertion that actually proves visibility: the row survives the
        # same INNER join the CRM's own list query uses.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices p "
                "JOIN practice_types pt ON p.practice_type_id = pt.id "
                "WHERE p.id = $1",
                practice_id,
            )
            == 1
        ), "the practice must survive the CRM's inner join, not just exist"


async def test_an_unknown_practice_type_is_refused_and_writes_nothing(pool):
    """Refusing beats writing an invisible row.

    A code absent from the catalogue used to be accepted (the suite's own
    constant was "VOA", which matches no row in migration 221), producing a
    practice that no CRM surface could display. It now raises before any INSERT.
    """

    key = f"evt_{uuid.uuid4().hex}"

    with pytest.raises(UnknownPracticeType, match="practice_types catalogue"):
        await PostgresCrmWriter(pool).create_client_and_practice(
            _snapshot(),
            source_idempotency_key=key,
            practice_type_code="definitely_not_a_real_code",
        )

    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices WHERE source_idempotency_key = $1", key
            )
            == 0
        )


async def test_the_practice_is_reachable_by_a_non_admin_team_member(pool):
    """`assigned_to` and `created_by` are RBAC columns, not metadata.

    `crm_practices.py` gates every non-admin read and write on
    `created_by = me OR assigned_to = me` (:1225, :1749, :2259, :2357, :2422,
    plus the list filter at :1834). A practice with both NULL is reachable by
    the three CRM admins and by nobody else — so the team member who has to act
    on the paid order cannot see it. That is the same invisibility as a NULL
    `practice_type_id`, one column over, and it is why this asserts the actual
    RBAC predicate rather than just `IS NOT NULL`.
    """

    writer = PostgresCrmWriter(pool)
    practice_id = await writer.create_client_and_practice(
        _snapshot(assigned_to="ari@balizero.com"),
        source_idempotency_key=f"evt_{uuid.uuid4().hex}",
        practice_type_code=PRACTICE_TYPE,
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT assigned_to, created_by, inquiry_date FROM practices WHERE id = $1",
            practice_id,
        )
        assert row["assigned_to"] == "ari@balizero.com"
        assert row["created_by"] == CREATED_BY_GARUDA
        assert row["inquiry_date"] is not None

        # The predicate a non-admin actually runs.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM practices "
                "WHERE id = $1 AND (created_by = $2 OR assigned_to = $2)",
                practice_id,
                "ari@balizero.com",
            )
            == 1
        ), "the assigned team member must be able to see their own practice"


async def test_an_unassigned_order_inherits_the_clients_owner(pool):
    """Same fallback the canonical writer uses, so GARUDA rows are not special."""

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO clients (full_name, email, assigned_to) "
            "VALUES ('SPECIMEN TRAVELLER', 'owned@example.invalid', 'sahira@balizero.com')"
        )

    practice_id = await PostgresCrmWriter(pool).create_client_and_practice(
        _snapshot(customer_email="owned@example.invalid", assigned_to=None),
        source_idempotency_key=f"evt_{uuid.uuid4().hex}",
        practice_type_code=PRACTICE_TYPE,
    )

    async with pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT assigned_to FROM practices WHERE id = $1", practice_id)
            == "sahira@balizero.com"
        )


def test_the_race_refusal_raises_INSIDE_the_transaction():
    """Structural, and structural ON PURPOSE — say so rather than imply more.

    `IdempotencyRaceLost` is documented-unreachable under READ COMMITTED (the
    only isolation this adapter supports), so no behavioural test in this file
    can drive it. That is exactly what let the bug live: the `if existing is
    None:` sat one indent level OUTSIDE the `async with conn.transaction()`, so
    the transaction COMMITTED — persisting the client created moments earlier —
    and only then raised. A committed customer record with no practice, on the
    one path the exception exists for.

    An indentation regression is invisible to every runtime assertion here and
    obvious to the parser, so the parser is the right instrument. What this
    does NOT prove: that the rollback itself works, or that the raise is
    correct. It proves the raise cannot happen after a commit.
    """

    src = textwrap.dedent(inspect.getsource(PostgresCrmWriter.create_client_and_practice))
    tree = ast.parse(src)

    async_withs = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncWith)]
    assert async_withs, "create_client_and_practice no longer opens a transaction block"

    def raises_race_lost(node):
        return [
            r
            for r in ast.walk(node)
            if isinstance(r, ast.Raise)
            and isinstance(r.exc, ast.Call)
            and isinstance(r.exc.func, ast.Name)
            and r.exc.func.id == "IdempotencyRaceLost"
        ]

    in_module = raises_race_lost(tree)
    assert len(in_module) == 1, f"expected exactly one raise site, found {len(in_module)}"

    inside = [r for w in async_withs for r in raises_race_lost(w)]
    assert inside, (
        "the IdempotencyRaceLost raise is OUTSIDE the transaction block — the "
        "transaction will have committed the client before it fires, leaving "
        "an orphan customer record"
    )


# --------------------------------------------------------------------------
# Zero ruling 2026-08-26: a paid VOA is born paid and in progress
# --------------------------------------------------------------------------


def _practices_insert_sql() -> str:
    """The INSERT statement text, read out of the real source.

    Structural rather than DB-backed on purpose: this property must hold on a
    machine with no Postgres, because the failure it guards is a WRONG LITERAL,
    not a schema violation, and a suite that skips is a suite that never
    objects.
    """

    src = textwrap.dedent(inspect.getsource(PostgresCrmWriter.create_client_and_practice))
    tree = ast.parse(src)
    statements = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "INSERT INTO practices" in node.value
    ]
    assert len(statements) == 1, f"expected exactly one practices INSERT, found {len(statements)}"
    return " ".join(statements[0].split())


def test_a_paid_garuda_practice_is_never_born_inquiry_or_unpaid() -> None:
    """RED-if-wrong. Before this ruling the adapter set neither column, so the
    row took the table defaults — `status='inquiry'` and
    `payment_status='unpaid'` — on a practice created FROM a committed
    payment.paid event. Both statements were false about a customer who had
    already paid and already uploaded documents."""

    sql = _practices_insert_sql()
    assert "'on_process'" in sql
    assert "'paid'" in sql
    assert "'inquiry'" not in sql
    assert "'unpaid'" not in sql


def test_the_status_values_written_exist_in_the_crm_vocabulary() -> None:
    """No new state is coined. Reads the router's own sets rather than
    restating them here, so a future narrowing of either vocabulary reddens
    this instead of silently permitting an invalid write."""

    from backend.app.routers.crm_practices import PAYMENT_STATUS_VALUES, STATUS_VALUES

    assert "on_process" in STATUS_VALUES
    assert "paid" in PAYMENT_STATUS_VALUES


def test_a_paid_practice_carries_an_amount_the_revenue_report_can_see() -> None:
    """The consequence the ruling implies but does not state.

    `crm_practices.py`'s revenue query ends `WHERE actual_price IS NOT NULL`,
    so a practice marked `payment_status='paid'` with a NULL actual price does
    not merely look inconsistent — it VANISHES from revenue. RED if either
    column is dropped from the insert while `'paid'` stays."""

    sql = _practices_insert_sql()
    assert "actual_price" in sql
    assert "paid_amount" in sql
