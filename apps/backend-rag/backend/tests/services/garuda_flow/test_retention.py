"""Integration tests for backend.services.garuda_flow.retention.

Reuses the throwaway-database sandbox from
backend/tests/scripts/visa_engine/test_garuda_voa_retention.py (migration
281's own bite-proof suite) rather than re-deriving the migration-chain
bootstrap here -- one sandbox fixture, one source of truth for "how do you
stand up a GARUDA-capable Postgres for a test".
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from backend.services.garuda_flow import retention
from backend.tests.scripts.visa_engine.test_garuda_voa_retention import (
    _apply_migrations_through,
    _garuda_check_insert_sql,
    _garuda_check_params,
    _insert_garuda_check_policy,
    _random_hash,
    garuda_281_sandbox,  # noqa: F401 -- reused as a pytest fixture
)

pytestmark = pytest.mark.asyncio


class _OneConnPool:
    """Minimal asyncpg.Pool-shaped wrapper around a single connection, so
    these tests can reuse the module's real `db_pool.acquire()` call shape
    without standing up an actual connection pool."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    def acquire(self):
        return self

    async def __aenter__(self) -> asyncpg.Connection:
        return self._connection

    async def __aexit__(self, *exc_info: object) -> None:
        return None


async def test_active_policy_available_reflects_the_one_signed_policy(garuda_281_sandbox) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        pool = _OneConnPool(connection)
        now = datetime.now(timezone.utc)

        assert await retention.active_garuda_check_policy_available(
            pool, environment="TEST", created_at=now
        ) is False

        await _insert_garuda_check_policy(connection, policy_version="svc-v1")

        assert await retention.active_garuda_check_policy_available(
            pool, environment="TEST", created_at=now
        ) is True
    finally:
        await connection.close()


async def test_active_policy_available_rejects_naive_datetime(garuda_281_sandbox) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        pool = _OneConnPool(connection)
        with pytest.raises(ValueError, match="timezone-aware"):
            await retention.active_garuda_check_policy_available(
                pool, environment="TEST", created_at=datetime(2026, 1, 1)
            )
    finally:
        await connection.close()


async def test_purge_expired_garuda_checks_rejects_out_of_range_limit(garuda_281_sandbox) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        pool = _OneConnPool(connection)
        with pytest.raises(ValueError, match="limit must be"):
            await retention.purge_expired_garuda_checks(pool, limit=0, requested_by="zero")
        with pytest.raises(ValueError, match="requested_by"):
            await retention.purge_expired_garuda_checks(pool, limit=10, requested_by="")
    finally:
        await connection.close()


async def test_purge_expired_garuda_checks_deletes_via_the_bounded_primitive(
    garuda_281_sandbox,
) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        pool = _OneConnPool(connection)
        await _insert_garuda_check_policy(
            connection,
            policy_version="svc-purge-v1",
            retention_interval="INTERVAL '1 second'",
            idempotency_retention_interval="INTERVAL '1 second'",
        )
        hash_ = _random_hash()
        sql, _ = _garuda_check_insert_sql()
        await connection.execute(sql, *_garuda_check_params(hash_))

        await asyncio.sleep(1.2)

        deleted = await retention.purge_expired_garuda_checks(
            pool, limit=100, requested_by="svc-op"
        )
        assert deleted == 1
    finally:
        await connection.close()


async def test_set_and_release_garuda_check_legal_hold_via_service(garuda_281_sandbox) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        pool = _OneConnPool(connection)
        await _insert_garuda_check_policy(connection, policy_version="svc-hold-v1")
        hash_ = _random_hash()
        sql, _ = _garuda_check_insert_sql()
        await connection.execute(sql, *_garuda_check_params(hash_))

        held = await retention.set_garuda_check_legal_hold(
            pool,
            hash_=hash_,
            legal_hold=True,
            requested_by="svc-op",
            case_reference="CASE-SVC-1",
            reason_code="PENDING_REVIEW",
            approved_by="zero-test-approver",
            review_due_at=datetime.now(timezone.utc) + timedelta(days=5),
        )
        assert held is True

        with pytest.raises(ValueError, match="review_due_at must be absent"):
            await retention.set_garuda_check_legal_hold(
                pool,
                hash_=hash_,
                legal_hold=False,
                requested_by="svc-op",
                case_reference="CASE-SVC-1",
                reason_code="PENDING_REVIEW",
                approved_by="zero-test-approver",
                review_due_at=datetime.now(timezone.utc),
            )

        released = await retention.set_garuda_check_legal_hold(
            pool,
            hash_=hash_,
            legal_hold=False,
            requested_by="svc-op",
            case_reference="CASE-SVC-1",
            reason_code="REVIEW_COMPLETE",
            approved_by="zero-test-approver",
            review_due_at=None,
        )
        assert released is True
    finally:
        await connection.close()


async def test_bind_legacy_garuda_checks_never_invents_coverage(garuda_281_sandbox) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=280)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
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
            *_garuda_check_params(_random_hash()),
        )
    finally:
        await connection.close()

    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        from backend.db.migration_base import split_migration_sql
        from backend.tests.scripts.visa_engine.test_garuda_voa_retention import _resolve_migration

        forward_sql, _rollback_sql = split_migration_sql(
            _resolve_migration(281).read_text(encoding="utf-8")
        )
        async with connection.transaction():
            await connection.execute(forward_sql)

        pool = _OneConnPool(connection)
        # No PRODUCTION-scoped GARUDA_CHECK policy exists yet.
        bound = await retention.bind_legacy_garuda_checks(pool, limit=100, requested_by="svc-op")
        assert bound == 0
    finally:
        await connection.close()


async def test_garuda_check_retention_evidence_is_aggregate_only(garuda_281_sandbox) -> None:
    await _apply_migrations_through(garuda_281_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(garuda_281_sandbox.database_dsn)
    try:
        pool = _OneConnPool(connection)
        evidence = await retention.garuda_check_retention_evidence(pool)
        assert evidence.expired_rows == 0
        assert evidence.expired_held_rows == 0
        assert evidence.max_lag_seconds == 0.0
    finally:
        await connection.close()
