"""`rollback_migration` had no test, and the gap hid a self-concealing defect.

Applying a migration writes TWO ledgers (`BaseMigration._log_migration` inserts
into both `schema_migrations` and `_schema_versions`). Until 2026-09-01 rolling
one back deleted from `_schema_versions` only. The consequence is worse than an
untidy row, and it is why this file exists:

  1. `MigrationManager.get_applied_migrations` reads `_schema_versions`, so the
     migration is correctly re-queued as pending.
  2. `BaseMigration._is_applied` reads `schema_migrations` — still populated —
     so `apply()` takes the "already applied" early-return and the forward SQL
     NEVER re-runs. Whatever the rollback tore down stays torn down.
  3. That same branch calls `_log_migration`, which re-INSERTs the missing
     `_schema_versions` row. The two ledgers re-converge, `schema_audit`'s
     `tracking_divergence_canonical_only` finding goes green, and the only
     signal that could have reported the problem is erased by the very run that
     was supposed to repair it.

Measured before writing this: `rollback_migration` has exactly ONE call site
(`BaseMigration.rollback`, itself with zero callers), no CLI subcommand, and no
workflow invocation — so the defect has almost certainly never fired in
production. That is luck, not safety: migrations 277 and 278 each carry a
hand-written `DELETE FROM schema_migrations` in their own rollback SQL, added
2026-08-21 by someone who found this by reading `_is_applied`. Two migrations
remembering is not a fix; the next one will not.

ISOLATION. These tests cannot use the `db_tx` fixture: the manager acquires its
own connection from its own pool, so its writes land outside any transaction a
fixture holds. They use a uniquely-named synthetic migration and delete it in a
finally, so a failure cannot leave a phantom row in a shared database.
"""

from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from backend.db.migration_manager import MigrationManager

pytestmark = pytest.mark.integration

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

#: Far above any real migration, so a collision with the tree is impossible.
_SYNTHETIC_NUMBER = 999_001


def _synthetic_name() -> str:
    return f"zz_rollback_ledger_probe_{uuid.uuid4().hex[:12]}"


async def _seed_both_ledgers(conn: asyncpg.Connection, name: str, table: str) -> None:
    """Record the synthetic migration exactly as a real apply would.

    Both INSERTs mirror `_log_migration`: writing only one would make the test
    prove something the runner never produces.
    """
    await conn.execute(f"CREATE TABLE {table} (id int)")
    rollback_sql = f"DROP TABLE IF EXISTS {table};"
    for ledger in ("schema_migrations", "_schema_versions"):
        await conn.execute(
            f"INSERT INTO {ledger} "
            "(migration_name, migration_number, checksum, description, rollback_sql) "
            "VALUES ($1, $2, $3, $4, $5)",
            name,
            _SYNTHETIC_NUMBER,
            "0" * 64,
            "synthetic probe for the rollback ledger test",
            rollback_sql,
        )


async def _in_ledger(conn: asyncpg.Connection, ledger: str, name: str) -> bool:
    return bool(
        await conn.fetchval(
            f"SELECT EXISTS(SELECT 1 FROM {ledger} WHERE migration_name = $1)",
            name,
        )
    )


async def _cleanup(conn: asyncpg.Connection, name: str, table: str) -> None:
    for ledger in ("schema_migrations", "_schema_versions"):
        await conn.execute(
            f"DELETE FROM {ledger} WHERE migration_name = $1", name
        )
    await conn.execute(f"DROP TABLE IF EXISTS {table}")


@pytest.mark.asyncio
async def test_rollback_clears_both_ledgers_not_just_the_legacy_one() -> None:
    """The fix, stated as the property it restores.

    A rolled-back migration must be invisible to BOTH readers: to
    `get_applied_migrations` (which reads `_schema_versions` to compute pending
    work) and to `_is_applied` (which reads `schema_migrations` to decide
    whether to skip). Leaving either one behind means the rollback did not
    happen as far as that reader is concerned.
    """
    name = _synthetic_name()
    table = f"t_{name}"
    manager = MigrationManager(database_url=_DB_URL)
    conn = await asyncpg.connect(_DB_URL)
    try:
        await _seed_both_ledgers(conn, name, table)
        assert await _in_ledger(conn, "schema_migrations", name)
        assert await _in_ledger(conn, "_schema_versions", name)

        assert await manager.rollback_migration(name) is True

        assert not await _in_ledger(conn, "_schema_versions", name), (
            "the legacy ledger still records the migration"
        )
        assert not await _in_ledger(conn, "schema_migrations", name), (
            "the CANONICAL ledger still records the migration — this is the "
            "defect: _is_applied reads this table, so the next apply-all would "
            "skip the forward SQL and re-heal the other ledger, erasing the "
            "evidence that anything was wrong"
        )
    finally:
        await _cleanup(conn, name, table)
        if manager.pool:
            await manager.pool.close()
        await conn.close()


@pytest.mark.asyncio
async def test_the_rollback_sql_actually_ran() -> None:
    """Guard against a rollback that tidies the ledgers and nothing else.

    Without this, deleting BOTH rows and never executing the rollback body
    would satisfy the test above perfectly — the ledgers would be clean and the
    schema untouched, which is the worst of both outcomes.
    """
    name = _synthetic_name()
    table = f"t_{name}"
    manager = MigrationManager(database_url=_DB_URL)
    conn = await asyncpg.connect(_DB_URL)
    try:
        await _seed_both_ledgers(conn, name, table)
        assert await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table)

        await manager.rollback_migration(name)

        assert not await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table), (
            "the rollback SQL did not run — the ledgers were cleared over a "
            "schema that still carries the migration's changes"
        )
    finally:
        await _cleanup(conn, name, table)
        if manager.pool:
            await manager.pool.close()
        await conn.close()


@pytest.mark.asyncio
async def test_a_migration_with_no_rollback_sql_leaves_both_ledgers_intact() -> None:
    """Innocence, not only guilt: the early `return False` must not delete.

    `rollback_migration` bails out before its transaction when the stored
    rollback SQL is missing. A fix that moved the new DELETE outside that guard
    would silently de-register migrations it never reversed — strictly worse
    than the bug it replaced.
    """
    name = _synthetic_name()
    table = f"t_{name}"
    manager = MigrationManager(database_url=_DB_URL)
    conn = await asyncpg.connect(_DB_URL)
    try:
        await _seed_both_ledgers(conn, name, table)
        await conn.execute(
            "UPDATE _schema_versions SET rollback_sql = NULL WHERE migration_name = $1",
            name,
        )

        assert await manager.rollback_migration(name) is False

        assert await _in_ledger(conn, "schema_migrations", name)
        assert await _in_ledger(conn, "_schema_versions", name)
        assert await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table)
    finally:
        await _cleanup(conn, name, table)
        if manager.pool:
            await manager.pool.close()
        await conn.close()
