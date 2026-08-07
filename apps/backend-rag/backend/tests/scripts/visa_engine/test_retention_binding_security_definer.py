"""Integration test for migration 268 -- retention-binding trigger SECURITY
DEFINER.

Reproduces the 2026-08-07 production incident (see
``lesson_least_privilege_repair_breaks_invoker_triggers_that_lock_rows_
2026_08_07.md``) against a real, throwaway Postgres database: a
low-privilege role holding only SELECT on
``visa_decision_retention_policies`` -- the shape ``backend_rag_v2`` has
after the "D1" least-privilege repair -- cannot complete the ``SELECT ...
FOR SHARE`` inside migration 264's BEFORE INSERT trigger
``bind_visa_evaluate_idempotency_retention_policy`` (``FOR SHARE`` requires
the UPDATE privilege, not merely SELECT) until migration 268 makes that
trigger, and its two siblings, ``SECURITY DEFINER``.

Mirrors ``test_write_substrate.py``'s throwaway-database pattern (its own
``CREATE DATABASE``/``DROP DATABASE`` against the ``postgres`` maintenance
DB, migrations applied directly off disk) rather than the shared
``nuzantara_test`` database conftest.py's ``visa_schema`` fixture targets --
this test additionally creates a cluster-wide Postgres ROLE (a privilege
boundary cannot be scoped to one database the way a table can), so
isolation from a concurrent sibling test run matters even more here. The
role name is uuid-suffixed per test invocation, so a cross-run collision is
structurally impossible rather than merely unlikely, and the throwaway
database is always dropped before the role is, so the role never has a
dangling privilege blocking its own ``DROP ROLE``.

Reuses ``fullstack_smoke``'s own ``MIGRATION_NUMBERS``/``_migration_paths``
as the single source of truth for the full forward-migration chain (250
through 268) rather than hand-picking a subset here and silently missing a
dependency.

Run manually (creates+drops its own throwaway database and role via an
admin connection derived from ``TEST_DATABASE_URL``, swapped to the
``postgres`` maintenance database; never touches ``nuzantara_dev``/
``nuzantara_test`` themselves):

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \\
    PYTHONPATH=. pytest \\
      backend/tests/scripts/visa_engine/test_retention_binding_security_definer.py -v
"""

from __future__ import annotations

import os
import secrets
import uuid
from collections.abc import AsyncIterator
from typing import NamedTuple

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.scripts.visa_engine import fullstack_smoke

pytestmark = pytest.mark.asyncio

# Same env-var convention as conftest.py / test_write_substrate.py: read
# TEST_DATABASE_URL (the one env var CI actually exports), swap its database
# name for the "postgres" maintenance database every Postgres install ships.
_ADMIN_URL = (
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://nuzantara@localhost:5432/nuzantara_test",
    ).rsplit("/", 1)[0]
    + "/postgres"
)


def _db_url_for(db_name: str) -> str:
    return _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"


async def _apply_migrations_through(database_dsn: str, *, through: int) -> None:
    """Apply every Visa Engine migration up to and including ``through``, in
    the exact order ``fullstack_smoke.MIGRATION_NUMBERS`` defines -- the
    single source of truth for the full chain, so this never hand-picks a
    subset and silently skips a dependency.
    """

    backend_root = fullstack_smoke._backend_root()
    connection = await asyncpg.connect(database_dsn)
    try:
        for migration_path in fullstack_smoke._migration_paths(backend_root):
            number = int(migration_path.name.split("_", 1)[0])
            if number > through:
                continue
            forward_sql, _rollback_sql = split_migration_sql(
                migration_path.read_text(encoding="utf-8")
            )
            async with connection.transaction():
                await connection.execute(forward_sql)
    finally:
        await connection.close()


async def _insert_test_retention_policy(database_dsn: str) -> None:
    connection = await asyncpg.connect(database_dsn)
    try:
        await connection.execute(fullstack_smoke.POLICY_SQL)
    finally:
        await connection.close()


async def _create_lowpriv_role(database_dsn: str, role: str) -> None:
    """The shape ``backend_rag_v2`` has after the D1 least-privilege repair:
    SELECT-only on the retention-policy table, SELECT+INSERT (never UPDATE)
    on the idempotency table it writes to."""

    connection = await asyncpg.connect(database_dsn)
    try:
        await connection.execute(f'CREATE ROLE "{role}" NOLOGIN')
        await connection.execute(
            f'GRANT SELECT ON TABLE public.visa_decision_retention_policies TO "{role}"'
        )
        await connection.execute(
            f'GRANT SELECT, INSERT ON TABLE public.visa_evaluate_idempotency TO "{role}"'
        )
    finally:
        await connection.close()


def _idempotency_insert() -> tuple[str, bytes, bytes, str]:
    sql = """
        INSERT INTO public.visa_evaluate_idempotency
            (key_sha256, request_hmac, request_hmac_key_id, environment,
             reserved_at, created_at, expires_at)
        VALUES
            ($1, $2, $3, 'TEST',
             statement_timestamp(), statement_timestamp(),
             statement_timestamp() + INTERVAL '1 hour')
    """
    return sql, secrets.token_bytes(32), secrets.token_bytes(32), "test-key-1"


class _Sandbox(NamedTuple):
    database_dsn: str
    lowpriv_role: str


@pytest_asyncio.fixture
async def m268_sandbox() -> AsyncIterator[_Sandbox]:
    """A throwaway database plus a matching, uuid-suffixed low-privilege
    role name. Neither the database nor the role is created empty-handed by
    this fixture beyond the database itself -- each test decides how far to
    apply migrations before creating the role, since the pre-268/post-268
    comparison is the point. Teardown always drops the database FIRST (so
    every ACL entry the role held vanishes with it) and only then the role
    itself, so ``DROP ROLE`` never trips over a dangling privilege.
    """

    db_name = f"nuzantara_test_visa_m268_{uuid.uuid4().hex[:16]}"
    role_name = f"visa268_lowpriv_{uuid.uuid4().hex[:12]}"
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


async def test_pre_268_low_privilege_insert_fails_with_insufficient_privilege(
    m268_sandbox: _Sandbox,
) -> None:
    """Reproduces the 2026-08-07 incident: migrations up to 267 only (264's
    trigger is still SECURITY INVOKER), a role with SELECT-only on the
    policy table cannot complete the trigger's ``FOR SHARE`` row lock."""

    await _apply_migrations_through(m268_sandbox.database_dsn, through=267)
    await _insert_test_retention_policy(m268_sandbox.database_dsn)
    await _create_lowpriv_role(m268_sandbox.database_dsn, m268_sandbox.lowpriv_role)

    sql, key_sha256, request_hmac, key_id = _idempotency_insert()
    connection = await asyncpg.connect(m268_sandbox.database_dsn)
    try:
        async with connection.transaction():
            await connection.execute(f'SET LOCAL ROLE "{m268_sandbox.lowpriv_role}"')
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(sql, key_sha256, request_hmac, key_id)
    finally:
        await connection.close()


async def test_post_268_low_privilege_insert_succeeds(m268_sandbox: _Sandbox) -> None:
    """Migration 268 applied: the SAME low-privilege role, the SAME grants,
    the SAME INSERT -- now succeeds because the trigger runs SECURITY
    DEFINER, resolving the policy lookup with the function owner's
    privileges instead of the caller's."""

    await _apply_migrations_through(m268_sandbox.database_dsn, through=268)
    await _insert_test_retention_policy(m268_sandbox.database_dsn)
    await _create_lowpriv_role(m268_sandbox.database_dsn, m268_sandbox.lowpriv_role)

    sql, key_sha256, request_hmac, key_id = _idempotency_insert()
    connection = await asyncpg.connect(m268_sandbox.database_dsn)
    try:
        async with connection.transaction():
            await connection.execute(f'SET LOCAL ROLE "{m268_sandbox.lowpriv_role}"')
            await connection.execute(sql, key_sha256, request_hmac, key_id)

        row = await connection.fetchrow(
            "SELECT retention_policy_id, expires_at FROM public.visa_evaluate_idempotency "
            "WHERE key_sha256 = $1",
            key_sha256,
        )
    finally:
        await connection.close()

    assert row is not None
    assert row["retention_policy_id"] is not None
    assert row["expires_at"] is not None


async def test_268_marks_all_three_retention_binding_triggers_security_definer(
    m268_sandbox: _Sandbox,
) -> None:
    """Fallback structural proof, independent of the role-boundary
    reproduction above: after 268, every one of the three "twin" trigger
    functions (`lesson ... 2026_08_07.md`'s own phrase) is
    ``prosecdef = true``, not only the one the other two tests exercise
    end-to-end."""

    await _apply_migrations_through(m268_sandbox.database_dsn, through=268)

    connection = await asyncpg.connect(m268_sandbox.database_dsn)
    try:
        rows = await connection.fetch(
            """
            SELECT proname, prosecdef
              FROM pg_proc
             WHERE proname IN (
                 'bind_visa_evaluate_idempotency_retention_policy',
                 'bind_visa_decision_retention_policy',
                 'bind_visa_decision_payload_retention'
             )
            """
        )
    finally:
        await connection.close()

    assert {row["proname"] for row in rows} == {
        "bind_visa_evaluate_idempotency_retention_policy",
        "bind_visa_decision_retention_policy",
        "bind_visa_decision_payload_retention",
    }
    assert all(row["prosecdef"] for row in rows)
