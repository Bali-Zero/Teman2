"""Integration tests for migration 281 -- GARUDA VOA retention extension.

Reproduces the retention-fail-closed.feature scenarios
(products/garuda-voa/journeys/retention-fail-closed.feature) against a real,
throwaway Postgres database, in the same spirit as
test_retention_binding_security_definer.py's throwaway-database pattern:
this migration is the L1 GARUDA VOA lane's contract, and every one of its
fail-closed properties is proven here against a real database, not asserted
in prose.

Applies the FULL forward-migration chain from 250 through 281 (inclusive),
by number range rather than a hand-picked subset -- 281 depends on 261
(garuda_voa_checks) which the Visa Engine smoke's own MIGRATION_NUMBERS
tuple deliberately skips (250-257,262-268 only), so this file cannot reuse
that tuple directly.

Run manually (creates+drops its own throwaway database and role via an
admin connection derived from ``TEST_DATABASE_URL``, swapped to the
``postgres`` maintenance database; never touches ``nuzantara_dev``/
``nuzantara_test`` themselves):

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \\
    PYTHONPATH=. pytest \\
      backend/tests/scripts/visa_engine/test_garuda_voa_retention.py -v
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.scripts.visa_engine import fullstack_smoke

pytestmark = pytest.mark.asyncio

_ADMIN_URL = (
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://nuzantara@localhost:5432/nuzantara_test",
    ).rsplit("/", 1)[0]
    + "/postgres"
)


def _db_url_for(db_name: str) -> str:
    return _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"


def _resolve_migration(number: int):
    backend_root = fullstack_smoke._backend_root()
    migrations_dir = backend_root / "backend" / "db" / "migrations_v2"
    matches = sorted(migrations_dir.glob(f"{number}_*.sql"))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one migration {number}, found {[p.name for p in matches]}"
        )
    return matches[0]


# The full migrations_v2 chain is NOT standalone-applicable to an empty
# database: many numbers (e.g. 108/132) assume a legacy baseline schema
# that real CI creates via scripts/ci_bootstrap_schema.py before running
# `migrate apply-all` (see migrations_v2/LEGACY_PROMOTION_README.md).
# fullstack_smoke.MIGRATION_NUMBERS already proves out a self-contained
# Visa Engine subset (250-257, 262-268); this test needs 261
# (garuda_voa_checks, a standalone CREATE TABLE) and 276 (comment-only,
# both harmless additions to that same self-contained set) plus 281 itself.
GARUDA_MIGRATION_NUMBERS: tuple[int, ...] = (
    250, 251, 252, 253, 254, 255, 256, 257,
    261, 262, 263, 264, 265, 266, 267, 268,
    276, 281,
)


async def _apply_migrations_through(database_dsn: str, *, through: int) -> None:
    connection = await asyncpg.connect(database_dsn)
    try:
        for number in GARUDA_MIGRATION_NUMBERS:
            if number > through:
                continue
            migration_path = _resolve_migration(number)
            forward_sql, _rollback_sql = split_migration_sql(
                migration_path.read_text(encoding="utf-8")
            )
            async with connection.transaction():
                await connection.execute(forward_sql)
    finally:
        await connection.close()


class _Sandbox(NamedTuple):
    database_dsn: str
    lowpriv_role: str


@pytest_asyncio.fixture
async def garuda_281_sandbox() -> AsyncIterator[_Sandbox]:
    db_name = f"nuzantara_test_garuda_m281_{uuid.uuid4().hex[:16]}"
    role_name = f"garuda281_lowpriv_{uuid.uuid4().hex[:12]}"
    admin_conn = await asyncpg.connect(_ADMIN_URL)
    try:
        await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin_conn.close()

    try:
        yield _Sandbox(database_dsn=_db_url_for(db_name), lowpriv_role=role_name)
    finally:
        admin_conn = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin_conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                db_name,
            )
            await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            await admin_conn.execute(f'DROP ROLE IF EXISTS "{role_name}"')
        finally:
            await admin_conn.close()


# ---------------------------------------------------------------------------
# Fixtures for inserting a GARUDA_CHECK policy row and a garuda_voa_checks row
# ---------------------------------------------------------------------------


async def _insert_garuda_check_policy(
    connection: asyncpg.Connection,
    *,
    policy_version: str,
    retention_interval: str = "INTERVAL '90 days'",
    idempotency_retention_interval: str = "INTERVAL '1 hour'",
    lower_bound: str = "clock_timestamp() - INTERVAL '1 day'",
    upper_bound: str | None = None,
) -> None:
    upper_sql = "NULL" if upper_bound is None else upper_bound
    await connection.execute(
        f"""
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', 'GARUDA_CHECK', $1, {retention_interval},
            {idempotency_retention_interval}, INTERVAL '30 days',
            'CREATED_AT', tstzrange({lower_bound}, {upper_sql}, '[)'),
            'zero-test-approver', 'ZERO-GARUDA-RETENTION-TEST-APPROVAL'
        )
        """,
        policy_version,
    )


def _garuda_check_insert_sql(*, with_ack: bool = True) -> tuple[str, tuple]:
    ack_col = ", retention_notice_acknowledged_at" if with_ack else ""
    ack_val = ", clock_timestamp()" if with_ack else ""
    sql = f"""
        INSERT INTO public.garuda_voa_checks (
            hash, environment, case_type, nationality, entry_date,
            passport_expiry_date, purpose, travellers, self_pay,
            decision, expiry_date, last_legal_day, expiry_is_estimated,
            published_filing_deadline{ack_col}
        ) VALUES (
            $1, 'TEST', 'issuance', 'USA', $2,
            $3, 'tourism', 1, TRUE,
            'ACCEPT', $4, $5, FALSE,
            $6{ack_val}
        )
    """
    return sql, ()


def _random_hash() -> str:
    return uuid.uuid4().hex[:16]


def _garuda_check_params(hash_: str) -> tuple:
    entry = date(2026, 8, 1)
    passport_expiry = date(2027, 8, 1)
    expiry = date(2026, 8, 31)
    last_legal_day = date(2026, 8, 31)
    filing_deadline = date(2026, 8, 24)
    return (hash_, entry, passport_expiry, expiry, last_legal_day, filing_deadline)


async def test_insert_fails_without_any_active_policy(garuda_281_sandbox: _Sandbox) -> None:
    """retention-fail-closed.feature Scenario Outline, policy_state=absent."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        sql, _ = _garuda_check_insert_sql()
        with pytest.raises(asyncpg.RaiseError, match="no active Zero-approved retention policy"):
            await connection.execute(sql, *_garuda_check_params(_random_hash()))
    finally:
        await connection.close()


async def test_insert_fails_when_policy_effective_period_excludes_created_at(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature Scenario Outline, policy_state=expired-or-inactive."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(
            connection,
            policy_version="expired-v1",
            lower_bound="clock_timestamp() - INTERVAL '10 days'",
            upper_bound="clock_timestamp() - INTERVAL '5 days'",
        )
        sql, _ = _garuda_check_insert_sql()
        with pytest.raises(asyncpg.RaiseError, match="no active Zero-approved retention policy"):
            await connection.execute(sql, *_garuda_check_params(_random_hash()))
    finally:
        await connection.close()


async def test_two_overlapping_garuda_check_policies_are_structurally_impossible(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature Scenario Outline, policy_state=ambiguous-multiple-active.

    The EXCLUDE constraint widened in 281 (environment, policy_scope,
    effective_period) is what makes "ambiguous" unreachable in a correctly
    running database -- the TOO_MANY_ROWS branch in
    bind_garuda_voa_check_retention_policy is defense-in-depth, not the
    primary enforcement. This proves the primary enforcement.
    """

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(connection, policy_version="overlap-v1")
        with pytest.raises(asyncpg.ExclusionViolationError):
            await _insert_garuda_check_policy(connection, policy_version="overlap-v2")
    finally:
        await connection.close()


async def test_insert_fails_without_retention_notice_acknowledgement(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature 'Missing explicit acknowledgement prevents persistence'."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(connection, policy_version="ack-v1")
        sql, _ = _garuda_check_insert_sql(with_ack=False)
        with pytest.raises(
            asyncpg.RaiseError, match="explicit retention notice acknowledgement"
        ):
            await connection.execute(sql, *_garuda_check_params(_random_hash()))
    finally:
        await connection.close()


async def test_insert_succeeds_and_database_derives_retention_deadline(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature 'The database derives retention from the one active policy'."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(
            connection, policy_version="derive-v1", retention_interval="INTERVAL '90 days'"
        )
        hash_ = _random_hash()
        sql, _ = _garuda_check_insert_sql()
        await connection.execute(sql, *_garuda_check_params(hash_))

        row = await connection.fetchrow(
            "SELECT retention_policy_id, retention_until, created_at "
            "FROM public.garuda_voa_checks WHERE hash = $1",
            hash_,
        )
        policy_id = await connection.fetchval(
            "SELECT id FROM public.visa_decision_retention_policies WHERE policy_version = $1",
            "derive-v1",
        )
        assert row["retention_policy_id"] == policy_id
        assert row["retention_until"] > row["created_at"]
        assert abs(
            (row["retention_until"] - row["created_at"]) - timedelta(days=90)
        ) < timedelta(seconds=5)
    finally:
        await connection.close()


async def test_insert_fails_atomically_when_caller_supplies_mismatched_deadline(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature: caller-supplied deadline/policy mismatch fails atomically."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(connection, policy_version="mismatch-v1")
        hash_ = _random_hash()
        bogus_future = datetime.now(timezone.utc) + timedelta(days=9999)
        sql = """
            INSERT INTO public.garuda_voa_checks (
                hash, environment, case_type, nationality, entry_date,
                passport_expiry_date, purpose, travellers, self_pay,
                decision, expiry_date, last_legal_day, expiry_is_estimated,
                published_filing_deadline, retention_notice_acknowledged_at,
                retention_until
            ) VALUES (
                $1, 'TEST', 'issuance', 'USA', $2,
                $3, 'tourism', 1, TRUE,
                'ACCEPT', $4, $5, FALSE,
                $6, clock_timestamp(), $7
            )
        """
        with pytest.raises(
            asyncpg.RaiseError, match="retention deadline does not match active policy"
        ):
            await connection.execute(sql, *_garuda_check_params(hash_), bogus_future)

        exists = await connection.fetchval(
            "SELECT 1 FROM public.garuda_voa_checks WHERE hash = $1", hash_
        )
        assert exists is None
    finally:
        await connection.close()


async def test_purge_skips_legal_hold_and_leaves_identifier_free_evidence(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature 'Bounded purge skips legal hold and leaves
    identifier-free evidence' + 'When the purge command is retried Then no
    row, evidence count, or purge event is duplicated'."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(
            connection,
            policy_version="purge-v1",
            retention_interval="INTERVAL '1 second'",
            idempotency_retention_interval="INTERVAL '1 second'",
        )
        held_hash = _random_hash()
        unheld_hash = _random_hash()
        sql, _ = _garuda_check_insert_sql()
        await connection.execute(sql, *_garuda_check_params(held_hash))
        await connection.execute(sql, *_garuda_check_params(unheld_hash))

        held = await connection.fetchval(
            "SELECT public.set_garuda_voa_check_legal_hold("
            "$1, TRUE, 'zero-test-op', 'CASE-1', 'PENDING_REVIEW', 'zero-test-approver', "
            "clock_timestamp() + INTERVAL '10 days')",
            held_hash,
        )
        assert held is True

        await asyncio.sleep(1.2)  # let the 1-second retention_interval elapse

        deleted_first = await connection.fetchval(
            "SELECT public.purge_garuda_voa_checks(100, 'zero-test-purge-op')"
        )
        assert deleted_first == 1

        remaining_hashes = {
            row["hash"]
            for row in await connection.fetch("SELECT hash FROM public.garuda_voa_checks")
        }
        assert remaining_hashes == {held_hash}

        hold_events = await connection.fetch(
            "SELECT garuda_hash, event_type FROM public.garuda_voa_check_legal_hold_events"
        )
        assert len(hold_events) == 1
        assert hold_events[0]["garuda_hash"] == held_hash

        batch_rows = await connection.fetch(
            "SELECT affected_count, executor_label FROM public.visa_decision_retention_batches"
        )
        assert len(batch_rows) == 1
        assert batch_rows[0]["affected_count"] == 1
        # Aggregate-only: the batches table carries no hash/decision identifier column.
        batch_columns = {
            row["column_name"]
            for row in await connection.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'visa_decision_retention_batches'"
            )
        }
        assert "hash" not in batch_columns

        deleted_second = await connection.fetchval(
            "SELECT public.purge_garuda_voa_checks(100, 'zero-test-purge-op')"
        )
        assert deleted_second == 0
        batch_count_after_retry = await connection.fetchval(
            "SELECT count(*) FROM public.visa_decision_retention_batches"
        )
        assert batch_count_after_retry == 1
    finally:
        await connection.close()


async def _create_lowpriv_role_for_garuda(connection: asyncpg.Connection, role: str) -> None:
    await connection.execute(f'CREATE ROLE "{role}" NOLOGIN')
    await connection.execute(f'GRANT SELECT, INSERT ON TABLE public.garuda_voa_checks TO "{role}"')
    await connection.execute(
        f'GRANT SELECT ON TABLE public.visa_decision_retention_policies TO "{role}"'
    )


async def test_unauthorized_caller_cannot_execute_purge_or_legal_hold_directly(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature 'Retention authority cannot be bypassed
    through public execution': EXECUTE is revoked from PUBLIC on every
    privileged function this migration introduces."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _create_lowpriv_role_for_garuda(connection, garuda_281_sandbox.lowpriv_role)

        async with connection.transaction():
            await connection.execute(f'SET LOCAL ROLE "{garuda_281_sandbox.lowpriv_role}"')
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(
                    "SELECT public.purge_garuda_voa_checks(10, 'attacker')"
                )
        async with connection.transaction():
            await connection.execute(f'SET LOCAL ROLE "{garuda_281_sandbox.lowpriv_role}"')
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(
                    "SELECT public.set_garuda_voa_check_legal_hold("
                    "'deadbeefdeadbeef', TRUE, 'attacker', 'C', 'R', 'A', "
                    "clock_timestamp() + INTERVAL '1 day')"
                )
    finally:
        await connection.close()


async def test_all_new_functions_are_security_definer(garuda_281_sandbox: _Sandbox) -> None:
    """SECURITY DEFINER applies to the privileged capability functions --
    the two guard/mutation trigger functions deliberately stay SECURITY
    INVOKER (mirroring guard_visa_decisions_retention_mutation in 264):
    their ownership check (`current_user <> table_owner`) is only
    meaningful when `current_user` is the CALLING role, not the function's
    owner, so DEFINER there would silently defeat the very check it runs.
    """

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        rows = await connection.fetch(
            """
            SELECT proname, prosecdef
              FROM pg_proc
             WHERE proname IN (
                 'bind_garuda_voa_check_retention_policy',
                 'purge_garuda_voa_checks',
                 'garuda_voa_check_retention_evidence',
                 'set_garuda_voa_check_legal_hold',
                 'bind_legacy_garuda_voa_checks_retention_policy',
                 'guard_garuda_voa_checks_retention_mutation',
                 'guard_garuda_voa_check_legal_hold_events_mutation'
             )
            """
        )
    finally:
        await connection.close()

    by_name = {row["proname"]: row["prosecdef"] for row in rows}
    assert set(by_name) == {
        "bind_garuda_voa_check_retention_policy",
        "purge_garuda_voa_checks",
        "garuda_voa_check_retention_evidence",
        "set_garuda_voa_check_legal_hold",
        "bind_legacy_garuda_voa_checks_retention_policy",
        "guard_garuda_voa_checks_retention_mutation",
        "guard_garuda_voa_check_legal_hold_events_mutation",
    }
    definer_functions = {
        "bind_garuda_voa_check_retention_policy",
        "purge_garuda_voa_checks",
        "garuda_voa_check_retention_evidence",
        "set_garuda_voa_check_legal_hold",
        "bind_legacy_garuda_voa_checks_retention_policy",
    }
    invoker_functions = {
        "guard_garuda_voa_checks_retention_mutation",
        "guard_garuda_voa_check_legal_hold_events_mutation",
    }
    assert all(by_name[name] for name in definer_functions)
    assert not any(by_name[name] for name in invoker_functions)


async def test_view_count_and_share_count_remain_freely_writable(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """The 261 contract ("edits only to view_count/share_count") must survive
    281's mutation guard unchanged."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(connection, policy_version="counters-v1")
        hash_ = _random_hash()
        sql, _ = _garuda_check_insert_sql()
        await connection.execute(sql, *_garuda_check_params(hash_))

        await connection.execute(
            "UPDATE public.garuda_voa_checks SET view_count = view_count + 1, "
            "share_count = share_count + 1 WHERE hash = $1",
            hash_,
        )
        row = await connection.fetchrow(
            "SELECT view_count, share_count FROM public.garuda_voa_checks WHERE hash = $1",
            hash_,
        )
        assert row["view_count"] == 1
        assert row["share_count"] == 1

        with pytest.raises(asyncpg.RaiseError, match="may only change"):
            await connection.execute(
                "UPDATE public.garuda_voa_checks SET decision = 'DECLINE' WHERE hash = $1",
                hash_,
            )
    finally:
        await connection.close()


async def test_direct_delete_is_rejected_and_only_bounded_purge_may_delete(
    garuda_281_sandbox: _Sandbox,
) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(
            connection, policy_version="delete-guard-v1", retention_interval="INTERVAL '90 days'"
        )
        hash_ = _random_hash()
        sql, _ = _garuda_check_insert_sql()
        await connection.execute(sql, *_garuda_check_params(hash_))

        with pytest.raises(
            asyncpg.RaiseError, match="delete must use the bounded retention purge"
        ):
            await connection.execute(
                "DELETE FROM public.garuda_voa_checks WHERE hash = $1", hash_
            )
    finally:
        await connection.close()


async def test_table_owner_still_cannot_delete_a_non_expired_row(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """Isolates the SECOND guard clause from the ownership clause proven
    above: even a caller who IS the table owner (the shape purge's own
    SECURITY DEFINER runs under) cannot delete a row whose retention has
    not yet elapsed. purge_garuda_voa_checks never reaches this path today
    because its own SELECT already filters to eligible rows only -- this
    proves the guard does not merely rely on that filter being correct.
    """

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        await _insert_garuda_check_policy(
            connection, policy_version="owner-delete-v1", retention_interval="INTERVAL '90 days'"
        )
        hash_ = _random_hash()
        sql, _ = _garuda_check_insert_sql()
        await connection.execute(sql, *_garuda_check_params(hash_))

        table_owner = await connection.fetchval(
            "SELECT pg_get_userbyid(relowner) FROM pg_class "
            "WHERE relname = 'garuda_voa_checks' AND relnamespace = 'public'::regnamespace"
        )

        async with connection.transaction():
            await connection.execute(f'SET LOCAL ROLE "{table_owner}"')
            await connection.execute(
                "SELECT set_config('visa.retention_requested_by', 'zero-test-owner-op', TRUE)"
            )
            with pytest.raises(
                asyncpg.RaiseError, match="delete requires elapsed retention"
            ):
                await connection.execute(
                    "DELETE FROM public.garuda_voa_checks WHERE hash = $1", hash_
                )
    finally:
        await connection.close()


async def test_legacy_rows_are_backfilled_with_environment_but_stay_ungoverned(
    garuda_281_sandbox: _Sandbox,
) -> None:
    """retention-fail-closed.feature 'Legacy GARUDA rows become governed
    rather than exempt': a row written BEFORE migration 281 gets
    environment='PRODUCTION' but no retention_policy_id/retention_until --
    no fabricated coverage."""

    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=280)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        legacy_hash = _random_hash()
        # created_at is set explicitly, far in the past: this row predates
        # migration 281 (no binding trigger exists yet to bind/derive it),
        # and its true age is the point of this scenario -- a legacy row's
        # honest age, once governed, is expected to already be
        # purge-eligible under a 90-day policy.
        await connection.execute(
            """
            INSERT INTO public.garuda_voa_checks (
                hash, created_at, case_type, nationality, entry_date, passport_expiry_date,
                purpose, travellers, self_pay, decision, expiry_date,
                last_legal_day, expiry_is_estimated, published_filing_deadline
            ) VALUES (
                $1, TIMESTAMPTZ '2020-01-01T00:00:00Z', 'issuance', 'USA', $2, $3,
                'tourism', 1, TRUE, 'ACCEPT', $4, $5, FALSE, $6
            )
            """,
            *_garuda_check_params(legacy_hash),
        )
    finally:
        await connection.close()

    # Now land the migration this legacy row predates.
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        forward_sql, _rollback_sql = split_migration_sql(
            _resolve_migration(281).read_text(encoding="utf-8")
        )
        async with connection.transaction():
            await connection.execute(forward_sql)

        row = await connection.fetchrow(
            "SELECT environment, retention_policy_id, retention_until "
            "FROM public.garuda_voa_checks WHERE hash = $1",
            legacy_hash,
        )
        assert row["environment"] == "PRODUCTION"
        assert row["retention_policy_id"] is None
        assert row["retention_until"] is None

        # No PRODUCTION-scoped policy exists yet: the bounded backfill must
        # leave it ungoverned rather than inventing coverage.
        bound = await connection.fetchval(
            "SELECT public.bind_legacy_garuda_voa_checks_retention_policy(100, 'zero-backfill-op')"
        )
        assert bound == 0

        await connection.execute(
            """
            INSERT INTO public.visa_decision_retention_policies (
                environment, policy_scope, policy_version, retention_interval,
                idempotency_retention_interval, legal_hold_review_interval,
                retention_anchor, effective_period, approved_by, approval_reference
            ) VALUES (
                'PRODUCTION', 'GARUDA_CHECK', 'legacy-backfill-v1', INTERVAL '90 days',
                INTERVAL '1 hour', INTERVAL '30 days',
                'CREATED_AT', tstzrange(clock_timestamp() - INTERVAL '10 years', NULL, '[)'),
                'zero-test-approver', 'ZERO-GARUDA-LEGACY-BACKFILL-APPROVAL'
            )
            """
        )

        bound_now = await connection.fetchval(
            "SELECT public.bind_legacy_garuda_voa_checks_retention_policy(100, 'zero-backfill-op')"
        )
        assert bound_now == 1

        row = await connection.fetchrow(
            "SELECT retention_policy_id, retention_until, created_at "
            "FROM public.garuda_voa_checks WHERE hash = $1",
            legacy_hash,
        )
        assert row["retention_policy_id"] is not None
        # The legacy row's real age means its computed deadline is already
        # in the past -- that is the intended, purge-eligible outcome, not
        # an error (unlike a brand-new INSERT, which the trigger forbids
        # from starting pre-expired).
        assert row["retention_until"] < datetime.now(timezone.utc)
    finally:
        await connection.close()
