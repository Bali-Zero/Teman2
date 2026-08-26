"""Integration tests for migration 282 -- the policy-driven retention layer
for ``visa_oracle_consultant_requests`` (migration 281).

Mirrors ``test_retention_binding_security_definer.py``'s throwaway-database
pattern (its own ``CREATE DATABASE``/``DROP DATABASE`` against the
``postgres`` maintenance DB, migrations applied directly off disk via
``split_migration_sql``) rather than the shared ``nuzantara_test`` database
conftest.py fixtures target. Unlike that file this migration only needs its
OWN two migrations applied -- 281 (the table) and 282 (the retention
policy/purge/evidence layer) -- because ``visa_oracle_consultant_requests``
has no dependency on the visa_decisions/visa_evaluate_idempotency chain
(migrations 250-268): it is a standalone append-only table, so replaying the
whole visa-engine migration history here would be needless weight.

Run manually (creates+drops its own throwaway database via an admin
connection derived from ``TEST_DATABASE_URL``, swapped to the ``postgres``
maintenance database; never touches ``nuzantara_dev``/``nuzantara_test``
themselves):

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \
    PYTHONPATH=. pytest \
      backend/tests/scripts/visa_engine/test_consultant_request_retention.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.services.visa_engine import retention

pytestmark = pytest.mark.asyncio

_ADMIN_URL = (
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://nuzantara@localhost:5432/nuzantara_test",
    ).rsplit("/", 1)[0]
    + "/postgres"
)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS_DIR = _BACKEND_ROOT / "db" / "migrations_v2"
_MIGRATION_281_PATH = _MIGRATIONS_DIR / "293_visa_oracle_consultant_requests.sql"
_MIGRATION_282_PATH = (
    _MIGRATIONS_DIR / "294_visa_oracle_consultant_requests_retention_policy.sql"
)


def _db_url_for(db_name: str) -> str:
    return _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"


async def _apply_migration(connection: asyncpg.Connection, path: Path) -> None:
    forward_sql, rollback_sql = split_migration_sql(path.read_text(encoding="utf-8"))
    assert rollback_sql, f"{path.name} must carry a '-- === ROLLBACK ===' section"
    async with connection.transaction():
        await connection.execute(forward_sql)


class _Sandbox(NamedTuple):
    database_dsn: str


@pytest_asyncio.fixture
async def m282_sandbox() -> AsyncIterator[_Sandbox]:
    """A throwaway database with migrations 281 and 282 applied, nothing
    else. Every ``visa_write_substrate`` shared trigger function
    (``reject_visa_write_substrate_mutation``, migration 252) that 282's
    triggers reference is created inline below -- reproducing exactly the
    one function 282 depends on from an earlier migration, rather than
    replaying the whole 250-280 chain for one helper function.
    """

    db_name = f"nuzantara_test_visa_m282_{uuid.uuid4().hex[:16]}"
    admin_conn = await asyncpg.connect(_ADMIN_URL)
    try:
        await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin_conn.close()

    database_dsn = _db_url_for(db_name)
    connection = await asyncpg.connect(database_dsn)
    try:
        # The one piece of shared infrastructure 282 leans on from migration
        # 252 (never redefined by 282 itself, matching 264's own convention
        # of reusing it rather than inventing a per-table variant). Body
        # copied verbatim from migration 252
        # (`RAISE EXCEPTION '% is append-only', TG_TABLE_NAME`) so a test
        # asserting on the real error text does not need a fixture-only
        # special case.
        await connection.execute(
            """
            CREATE FUNCTION public.reject_visa_write_substrate_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog, pg_temp
            AS $$
            BEGIN
                RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
            END;
            $$;
            """
        )
        await _apply_migration(connection, _MIGRATION_281_PATH)
        await _apply_migration(connection, _MIGRATION_282_PATH)
    finally:
        await connection.close()

    try:
        yield _Sandbox(database_dsn=database_dsn)
    finally:
        admin_conn = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin_conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                db_name,
            )
            await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        finally:
            await admin_conn.close()


@pytest_asyncio.fixture
async def db_pool(m282_sandbox: _Sandbox) -> AsyncIterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(m282_sandbox.database_dsn, min_size=1, max_size=5)
    yield pool
    await pool.close()


async def _insert_request(
    conn: asyncpg.Connection,
    *,
    requested_at: datetime,
    origin_screen: str = "wizard",
    tier: str = "T1",
    locale: str = "en",
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO public.visa_oracle_consultant_requests
            (evaluation_id, requested_at, origin_screen, tier, locale)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        uuid.uuid4(),
        requested_at,
        origin_screen,
        tier,
        locale,
    )
    return row["id"]


async def _insert_policy(
    conn: asyncpg.Connection,
    *,
    policy_version: str,
    retention_interval: timedelta,
    effective_from: datetime,
    retention_anchor: str = "REQUESTED_AT",
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO public.visa_oracle_consultant_request_retention_policies (
            policy_version, retention_interval, retention_anchor,
            effective_period, approved_by, approval_reference
        ) VALUES (
            $1, $2, $3, tstzrange($4, NULL, '[)'), 'zero-test-approver',
            'ZERO-RETENTION-TEST-APPROVAL'
        )
        RETURNING id
        """,
        policy_version,
        retention_interval,
        retention_anchor,
        effective_from,
    )
    return row["id"]


async def test_purge_rejects_out_of_range_limit_at_the_sql_layer(
    db_pool: asyncpg.Pool,
) -> None:
    """The SQL function's own defensive posture, independent of the Python
    wrapper's validation -- proves PostgreSQL rejects an out-of-range limit
    even if a caller bypassed retention.py entirely."""

    async with db_pool.acquire() as conn:
        with pytest.raises(
            asyncpg.RaiseError, match="purge limit must be between 1 and 1000"
        ):
            await conn.fetchval(
                "SELECT public.purge_visa_oracle_consultant_requests($1, $2)",
                1_001,
                "retention-test",
            )
        with pytest.raises(
            asyncpg.RaiseError, match="purge limit must be between 1 and 1000"
        ):
            await conn.fetchval(
                "SELECT public.purge_visa_oracle_consultant_requests($1, $2)",
                0,
                "retention-test",
            )


async def test_purge_rejects_out_of_range_limit_at_the_python_layer() -> None:
    """``retention.py``'s own validation raises before ever touching the
    pool -- proven by passing ``None`` as db_pool and confirming the
    ValueError still fires (a real db_pool would never be reached)."""

    with pytest.raises(ValueError, match="limit must be an integer between 1 and 1000"):
        await retention.purge_expired_consultant_requests(
            None,  # type: ignore[arg-type]
            limit=0,
            requested_by="retention-test",
        )
    with pytest.raises(ValueError, match="limit must be an integer between 1 and 1000"):
        await retention.purge_expired_consultant_requests(
            None,  # type: ignore[arg-type]
            limit=1_001,
            requested_by="retention-test",
        )
    with pytest.raises(ValueError, match="requested_by has an invalid format"):
        await retention.purge_expired_consultant_requests(
            None,  # type: ignore[arg-type]
            limit=10,
            requested_by="",
        )


async def test_purge_is_a_documented_no_op_with_no_active_policy(
    db_pool: asyncpg.Pool,
) -> None:
    """No policy row exists at all: an old row (any age) is never a purge
    candidate, mirroring active_policy_available()'s abstain semantics for
    the decisions/idempotency pair -- 0 deleted, 0 evidence rows, the row
    still present."""

    old_at = datetime.now(timezone.utc) - timedelta(days=3650)
    async with db_pool.acquire() as conn:
        request_id = await _insert_request(conn, requested_at=old_at)

    deleted = await retention.purge_expired_consultant_requests(
        db_pool, limit=100, requested_by="retention-test"
    )
    assert deleted == 0

    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_oracle_consultant_requests WHERE id = $1",
                request_id,
            )
            == 1
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_oracle_consultant_request_retention_batches"
            )
            == 0
        )

    evidence = await retention.consultant_request_retention_evidence(db_pool)
    assert evidence.expired_rows == 0
    assert evidence.max_lag_seconds == 0
    assert evidence.observed_at.tzinfo is not None


async def test_non_expired_row_is_refused_by_purge(db_pool: asyncpg.Pool) -> None:
    """Established FIRST that this reproduces for the right reason: a fresh
    row governed by a 30-day policy is NOT a candidate. Verified to fail
    for the right reason by first asserting the row is genuinely governed
    (an evidence backlog of 0, not 1) -- if the join/anchor logic were
    broken such that the policy never matched the row at all, this same
    assertion sequence would also read "0 deleted, row present", which is
    indistinguishable from "refused because not yet expired" unless the
    evidence count backs it. The companion expired-row test below proves
    the same policy DOES delete once elapsed, which is what rules out
    "never matched" as the explanation for this test's green.
    """

    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        policy_id = await _insert_policy(
            conn,
            policy_version="zero-test-v1",
            retention_interval=timedelta(days=30),
            effective_from=now - timedelta(days=1),
        )
        fresh_id = await _insert_request(conn, requested_at=now)

    # The row IS governed by the active policy (proves the join matched),
    # but its lag is negative (not yet due) -- evidence must read 0 expired.
    evidence = await retention.consultant_request_retention_evidence(db_pool)
    assert evidence.expired_rows == 0

    deleted = await retention.purge_expired_consultant_requests(
        db_pool, limit=100, requested_by="retention-test"
    )
    assert deleted == 0

    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_oracle_consultant_requests WHERE id = $1",
                fresh_id,
            )
            == 1
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_oracle_consultant_request_retention_batches "
                "WHERE retention_policy_id = $1",
                policy_id,
            )
            == 0
        )


async def test_expired_row_is_actually_deleted_and_recorded_as_evidence(
    db_pool: asyncpg.Pool,
) -> None:
    """The same policy shape as the refused-row test above, but the row's
    anchor timestamp is already past retention_interval -- proving the
    purge function's guilt path, not only its innocence path."""

    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        policy_id = await _insert_policy(
            conn,
            policy_version="zero-test-v1",
            retention_interval=timedelta(seconds=1),
            effective_from=now - timedelta(days=30),
        )
        expired_id = await _insert_request(conn, requested_at=now - timedelta(days=1))
        fresh_id = await _insert_request(conn, requested_at=now)

    evidence_before = await retention.consultant_request_retention_evidence(db_pool)
    assert evidence_before.expired_rows == 1
    assert evidence_before.max_lag_seconds > 0

    deleted = await retention.purge_expired_consultant_requests(
        db_pool, limit=100, requested_by="retention-worker-test"
    )
    assert deleted == 1

    async with db_pool.acquire() as conn:
        remaining = {
            row["id"]
            for row in await conn.fetch("SELECT id FROM public.visa_oracle_consultant_requests")
        }
        assert remaining == {fresh_id}
        session_user = await conn.fetchval("SELECT session_user")
        batch = await conn.fetchrow(
            """
            SELECT retention_policy_id, affected_count, executor_label
              FROM public.visa_oracle_consultant_request_retention_batches
            """
        )
        assert batch["retention_policy_id"] == policy_id
        assert batch["affected_count"] == 1
        assert batch["executor_label"] == f"{session_user}:retention-worker-test"
        with pytest.raises(asyncpg.RaiseError, match="is append-only"):
            await conn.execute(
                "UPDATE public.visa_oracle_consultant_request_retention_batches "
                "SET executor_label = 'tampered'"
            )

    evidence_after = await retention.consultant_request_retention_evidence(db_pool)
    assert evidence_after.expired_rows == 0
    assert expired_id != fresh_id


async def test_purge_batches_bounded_by_limit(db_pool: asyncpg.Pool) -> None:
    """Two expired rows, limit=1: one purge call deletes exactly one, a
    second call deletes the other -- proves ``limit`` bounds the batch
    rather than being advisory."""

    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        await _insert_policy(
            conn,
            policy_version="zero-test-v1",
            retention_interval=timedelta(seconds=1),
            effective_from=now - timedelta(days=30),
        )
        await _insert_request(conn, requested_at=now - timedelta(days=2))
        await _insert_request(conn, requested_at=now - timedelta(days=1))

    assert (
        await retention.purge_expired_consultant_requests(
            db_pool, limit=1, requested_by="retention-worker-test"
        )
        == 1
    )
    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM public.visa_oracle_consultant_requests")
            == 1
        )
    assert (
        await retention.purge_expired_consultant_requests(
            db_pool, limit=1, requested_by="retention-worker-test"
        )
        == 1
    )
    assert (
        await retention.purge_expired_consultant_requests(
            db_pool, limit=1, requested_by="retention-worker-test"
        )
        == 0
    )
