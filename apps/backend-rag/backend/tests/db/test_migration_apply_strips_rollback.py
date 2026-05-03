"""
Regression test for the migration runner bug discovered 2026-04-19.

Bug: BaseMigration.apply() passed the FULL .sql file content to
`conn.execute()`, including the section after `-- === ROLLBACK ===`.
PostgreSQL treats the marker as a comment, so CREATE TABLE then DROP TABLE
both ran inside the same transaction — the migration would log "applied
successfully" but the table would be gone, breaking every dependent
migration.

This test drives the actual `BaseMigration.apply()` path against real
Postgres using a synthetic migration file (no dependency on any in-tree
SQL file). It belongs on `main` so the runner stays protected even when
no migration in the tree currently exercises the marker convention.

Skipped when no test Postgres URL is reachable.
"""
from __future__ import annotations

import os
from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import BaseMigration

_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)


async def _table_exists(conn: asyncpg.Connection, name: str) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=$1)",
        name,
    )


@pytest.mark.asyncio
async def test_apply_does_not_execute_rollback_section(tmp_path: Path) -> None:
    """A migration file with `-- === ROLLBACK ===` followed by DROP must
    leave the created table intact after `BaseMigration.apply()`.
    """
    # Skip cleanly if the test DB is unreachable in this environment.
    # Connect outside the try/finally so `probe` is unambiguously bound
    # before the cleanup block runs (CodeQL: py/uninitialized-local-variable).
    try:
        probe = await asyncpg.connect(_TEST_DB_URL, timeout=2)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"test DB unreachable: {exc}")
        return  # pytest.skip raises, but help static analyzers see it

    table = "mig_strip_rollback_probe"
    sql_file = tmp_path / "200_strip_rollback_probe.sql"
    sql_file.write_text(
        f"CREATE TABLE {table} (id INT);\n"
        "-- === ROLLBACK ===\n"
        f"DROP TABLE {table};\n",
        encoding="utf-8",
    )

    try:
        # Pre-clean any leftover state from a previous run (other test, crash).
        await probe.execute(f"DROP TABLE IF EXISTS {table}")
        # Ensure schema_migrations exists so apply() can record itself,
        # then clear any prior row for migration 200.
        await probe.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  id SERIAL PRIMARY KEY, migration_name VARCHAR(255) UNIQUE NOT NULL,"
            "  migration_number INTEGER NOT NULL, executed_at TIMESTAMPTZ DEFAULT NOW(),"
            "  checksum VARCHAR(64) NOT NULL, description TEXT,"
            "  execution_time_ms INTEGER, rollback_sql TEXT)"
        )
        await probe.execute(
            "DELETE FROM schema_migrations WHERE migration_name = "
            "'200_strip_rollback_probe'"
        )

        migration = BaseMigration(
            migration_number=200,
            sql_file=sql_file.name,
            description="regression test: rollback section must not run on apply",
            rollback_sql=f"DROP TABLE {table};",
            _sql_dir=tmp_path,
        )

        # Force settings.database_url at module level for this single call so
        # the apply() opens a connection to the test DB even if global config
        # is pointing at something else.
        from backend.db import migration_base as mb
        original_url = mb.settings.database_url
        mb.settings.database_url = _TEST_DB_URL  # type: ignore[misc]
        try:
            ok = await migration.apply()
        finally:
            mb.settings.database_url = original_url  # type: ignore[misc]
        assert ok is True

        # The table MUST exist. With the bug, the rollback DROP would have
        # run inside the same transaction as the CREATE → table missing.
        assert await _table_exists(probe, table), (
            f"{table} is missing after BaseMigration.apply() — the rollback "
            "section is being executed against the live database"
        )
    finally:
        await probe.execute(f"DROP TABLE IF EXISTS {table}")
        await probe.execute(
            "DELETE FROM schema_migrations WHERE migration_name = "
            "'200_strip_rollback_probe'"
        )
        await probe.close()
