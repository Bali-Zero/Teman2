"""The SECURITY DEFINER ownership floor, proven against a REAL Postgres.

`test_operational_preflight.py` drives `collect_preflight_checks` through a
hand-written fake. That fake decides what the catalog says, so no assertion
made against it can settle whether `SECURITY_DEFINER_CENSUS_SQL` asks Postgres
the right question -- the test and the code would share the same imagination
(scar #9 / W114). The fake tests own the VERDICT logic; this file owns the SQL
and the migration.

Two things are proven here, both against a throwaway database and
uuid-suffixed cluster roles (a privilege boundary is cluster-wide, so a test
may not create a role literally named `visa_ledger_owner`):

  1. The shipped census reads `prosecdef` and ownership out of a real
     `pg_proc`. GUILT -- a SECURITY DEFINER function owned by the application
     role is reported. INNOCENCE -- an ordinary (invoker) function owned by the
     same role is NOT, so the check cannot go red on every function in the
     schema, and a correctly-owned definer function is not reported either.

  2. Migration 300 refuses to be recorded applied while the ownership is still
     wrong. This is the defect migrations 281 and 286 have: their
     `insufficient_privilege` handler emits a NOTICE and defers, so both were
     written into `_schema_versions` on 2026-08-26 while five functions stayed
     owned by `backend_rag_v2` -- measured still wrong on 2026-08-30, four days
     later, with nothing red anywhere.

Mirrors `test_retention_binding_security_definer.py`'s throwaway-database
pattern: its own CREATE DATABASE / DROP DATABASE against the `postgres`
maintenance database, never touching `nuzantara_dev` / `nuzantara_test`.

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \\
    PYTHONPATH=. pytest \\
      backend/tests/scripts/visa_engine/test_security_definer_owner_invariant.py
"""

from __future__ import annotations

import os
import pathlib
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.scripts.visa_engine import operational_preflight

pytestmark = pytest.mark.asyncio

_ADMIN_URL = (
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://nuzantara@localhost:5432/nuzantara_test",
    ).rsplit("/", 1)[0]
    + "/postgres"
)

_MIGRATION_300 = (
    pathlib.Path(__file__).resolve().parents[3]
    / "db"
    / "migrations_v2"
    / "300_garuda_voa_retention_owner_transfer.sql"
)

# Two of the five signatures migration 300 transfers. Two rather than five so
# the test also proves the block does not stop at the first name it fixes, and
# rather than all five so the fixture stays readable; the `not present --
# nothing to transfer` path for the other three is exercised by the same run.
_TRANSFERRED = (
    "public.purge_garuda_voa_checks(integer, text)",
    "public.garuda_voa_check_retention_evidence()",
)


def _db_url_for(db_name: str) -> str:
    return _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"


@pytest_asyncio.fixture
async def definer_sandbox() -> AsyncIterator[dict[str, str]]:
    suffix = uuid.uuid4().hex[:12]
    db_name = f"nuzantara_test_definer_{suffix}"
    ledger = f"vo_ledger_{suffix}"
    app = f"vo_app_{suffix}"

    admin = await asyncpg.connect(_ADMIN_URL)
    try:
        # Asserted, never assumed: the whole fixture needs CREATE ROLE and the
        # ability to SET ROLE into both roles. If the connecting role could not
        # do that, the guilt half would fail for an environment reason and the
        # innocence half would pass vacuously.
        is_superuser = await admin.fetchval(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        )
        assert is_superuser is True, (
            "this test creates cluster roles and switches between them; the "
            "connecting role is not a superuser"
        )
        await admin.execute(f'CREATE DATABASE "{db_name}"')
        await admin.execute(f'CREATE ROLE "{ledger}" NOLOGIN')
        await admin.execute(f'CREATE ROLE "{app}" NOLOGIN')
    finally:
        await admin.close()

    try:
        yield {"dsn": _db_url_for(db_name), "ledger": ledger, "app": app}
    finally:
        admin = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                db_name,
            )
            # The database goes first: while it exists its objects still hold
            # privileges that would block DROP ROLE.
            await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            for role in (app, ledger):
                await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        finally:
            await admin.close()


async def _seed_functions(connection: asyncpg.Connection, sandbox: dict[str, str]) -> None:
    """Three functions covering the census's whole decision surface."""

    await connection.execute(
        f'GRANT CREATE, USAGE ON SCHEMA public TO "{sandbox["app"]}", "{sandbox["ledger"]}"'
    )
    await connection.execute(f'SET ROLE "{sandbox["app"]}"')
    # GUILT: SECURITY DEFINER, owned by the application role.
    await connection.execute(
        "CREATE FUNCTION public.purge_garuda_voa_checks("
        "p_limit integer, p_requested_by text) RETURNS integer "
        "LANGUAGE sql SECURITY DEFINER AS $fn$ SELECT 0 $fn$"
    )
    # INNOCENCE: an ordinary invoker function owned by the SAME role. A census
    # that lost its `prosecdef` predicate would flag this one too, and the
    # check would be permanently red on any real schema.
    await connection.execute(
        "CREATE FUNCTION public.an_ordinary_invoker_function() RETURNS integer "
        "LANGUAGE sql AS $fn$ SELECT 0 $fn$"
    )
    await connection.execute(f'SET ROLE "{sandbox["ledger"]}"')
    # INNOCENCE: SECURITY DEFINER, correctly owned.
    await connection.execute(
        "CREATE FUNCTION public.garuda_voa_check_retention_evidence() "
        "RETURNS integer LANGUAGE sql SECURITY DEFINER AS $fn$ SELECT 0 $fn$"
    )
    await connection.execute("RESET ROLE")


async def test_shipped_census_reads_prosecdef_and_ownership_from_a_real_catalog(
    definer_sandbox: dict[str, str],
) -> None:
    connection = await asyncpg.connect(definer_sandbox["dsn"])
    try:
        await _seed_functions(connection, definer_sandbox)
        rows = await connection.fetch(
            operational_preflight.SECURITY_DEFINER_CENSUS_SQL
        )
    finally:
        await connection.close()

    censused = {row["signature"]: row["owner"] for row in rows}

    # GUILT: the definer function owned by the application role is seen.
    assert (
        censused.get("purge_garuda_voa_checks(p_limit integer, p_requested_by text)")
        == definer_sandbox["app"]
    ), censused
    # INNOCENCE: the invoker function owned by the same role is not.
    assert not any(
        signature.startswith("an_ordinary_invoker_function")
        for signature in censused
    ), (
        "an ordinary invoker function was censused -- the query has lost its "
        f"prosecdef predicate and would be red on every real schema: {censused}"
    )
    # INNOCENCE: the correctly-owned definer function is censused but clean.
    assert (
        censused.get("garuda_voa_check_retention_evidence()")
        == definer_sandbox["ledger"]
    ), censused

    # And the shipped verdict, fed rows from the real catalog rather than a fake.
    violations = operational_preflight._security_definer_violations(
        rows, expected_owner=definer_sandbox["ledger"]
    )
    assert violations == [
        f"purge_garuda_voa_checks(p_limit integer, p_requested_by text) "
        f"owned by {definer_sandbox['app']}"
    ], violations


def _migration_300_forward(ledger_role: str) -> str:
    forward_sql, _rollback_sql = split_migration_sql(
        _MIGRATION_300.read_text(encoding="utf-8")
    )
    # The migration names `visa_ledger_owner` literally, as it must in
    # production. A cluster role cannot be scoped to one database, so the test
    # substitutes a uuid-suffixed name rather than creating that role for real.
    return forward_sql.replace("visa_ledger_owner", ledger_role)


async def test_migration_300_raises_rather_than_deferring_like_281_and_286(
    definer_sandbox: dict[str, str],
) -> None:
    """The defect this whole lane exists to close.

    Run with a session that is neither superuser nor a member of the ledger
    role -- the migration runner's exact shape on production -- the ALTER is
    denied. 281 and 286 swallow that into a NOTICE and let the runner record
    them applied. 300 must raise, so `_schema_versions` cannot claim a cure
    that did not happen.
    """

    forward_sql = _migration_300_forward(definer_sandbox["ledger"])
    connection = await asyncpg.connect(definer_sandbox["dsn"])
    try:
        await _seed_functions(connection, definer_sandbox)
        await connection.execute(f'SET ROLE "{definer_sandbox["app"]}"')
        with pytest.raises(asyncpg.exceptions.RaiseError) as raised:
            await connection.execute(forward_sql)
        await connection.execute("RESET ROLE")

        message = str(raised.value)
        assert "public.purge_garuda_voa_checks(integer, text)" in message, message
        assert definer_sandbox["app"] in message, message
        assert "281" in message and "286" in message, message

        # The ownership really is untouched -- the raise is not the migration
        # failing AFTER a partial transfer.
        owner = await connection.fetchval(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc "
            "WHERE oid = to_regprocedure('public.purge_garuda_voa_checks(integer, text)')"
        )
        assert owner == definer_sandbox["app"]
    finally:
        await connection.close()


async def test_migration_300_transfers_then_is_a_silent_no_op(
    definer_sandbox: dict[str, str],
) -> None:
    """On a superuser connection -- CI, a fresh clone -- the ALTER lands and the
    assertion is silent; a second run changes nothing and still does not raise.
    """

    forward_sql = _migration_300_forward(definer_sandbox["ledger"])
    connection = await asyncpg.connect(definer_sandbox["dsn"])
    try:
        await _seed_functions(connection, definer_sandbox)
        await connection.execute(forward_sql)

        for signature in _TRANSFERRED:
            owner = await connection.fetchval(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc "
                "WHERE oid = to_regprocedure($1)",
                signature,
            )
            assert owner == definer_sandbox["ledger"], signature

        # Idempotent: re-applying an already-satisfied migration is a no-op.
        await connection.execute(forward_sql)

        # And the invoker function is untouched -- the migration transfers what
        # it names, not everything the application role happens to own.
        invoker_owner = await connection.fetchval(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc "
            "WHERE oid = to_regprocedure('public.an_ordinary_invoker_function()')"
        )
        assert invoker_owner == definer_sandbox["app"]

        # Nothing violates the floor any more, read through the shipped pair.
        rows = await connection.fetch(
            operational_preflight.SECURITY_DEFINER_CENSUS_SQL
        )
        assert (
            operational_preflight._security_definer_violations(
                rows, expected_owner=definer_sandbox["ledger"]
            )
            == []
        )
    finally:
        await connection.close()


async def test_migration_300_rollback_is_a_no_op_that_does_not_re_break_anything(
    definer_sandbox: dict[str, str],
) -> None:
    """The ROLLBACK section must parse, run, and change no ownership.

    Its mechanical inverse -- handing the five functions back to the runtime
    role -- re-arms the trap migration 285 fell into, so the section is
    deliberately inert. A rollback that is inert BY ACCIDENT (a syntax error
    nobody ever executes) would look identical from the file, which is why it
    is executed here.
    """

    file_sql = _MIGRATION_300.read_text(encoding="utf-8")
    forward_sql, rollback_sql = split_migration_sql(file_sql)
    assert rollback_sql.strip(), "migration 300 has no ROLLBACK section"

    connection = await asyncpg.connect(definer_sandbox["dsn"])
    try:
        await _seed_functions(connection, definer_sandbox)
        await connection.execute(
            forward_sql.replace("visa_ledger_owner", definer_sandbox["ledger"])
        )
        await connection.execute(
            rollback_sql.replace("visa_ledger_owner", definer_sandbox["ledger"])
        )

        for signature in _TRANSFERRED:
            owner = await connection.fetchval(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc "
                "WHERE oid = to_regprocedure($1)",
                signature,
            )
            assert owner == definer_sandbox["ledger"], (
                f"the rollback moved {signature} back to {owner} -- it is a "
                "symmetric undo, which re-creates the defect"
            )
    finally:
        await connection.close()
