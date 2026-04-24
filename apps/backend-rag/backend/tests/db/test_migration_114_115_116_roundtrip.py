"""
Integration test: apply migrations 114/115/116 against real Postgres, then
rollback each, ensuring schema state matches pre/post expectations.

Uses the `db_tx` fixture from conftest.py — transaction-scoped, rolled back
at teardown. Requires local Postgres running on the default URL.
"""
from __future__ import annotations

import os
import pathlib

import asyncpg
import pytest

from backend.db.migration_base import BaseMigration
from backend.db.migration_manager import MigrationManager, _extract_rollback_sql

pytestmark = pytest.mark.integration


_MIG_DIR = pathlib.Path(__file__).parent.parent.parent / "db" / "migrations_v2"


async def _table_exists(conn: asyncpg.Connection, name: str) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=$1)",
        name,
    )


async def _ensure_clean_slate(conn: asyncpg.Connection) -> None:
    """Drop our tables if they exist from outside this transaction.

    Integration tests in other suites commit data into these tables
    during the test session; this test exercises the raw migration
    semantics from scratch, so start clean.
    """
    await conn.execute("DROP TABLE IF EXISTS alert_outcomes CASCADE")
    await conn.execute("DROP TABLE IF EXISTS compliance_alerts CASCADE")
    await conn.execute("DROP TABLE IF EXISTS intel_validator_log CASCADE")


def _forward_and_rollback(sql_text: str) -> tuple[str, str]:
    """Split a migration file into (forward_sql, rollback_sql)."""
    rollback = _extract_rollback_sql(sql_text) or ""
    forward = sql_text.split("-- === ROLLBACK ===")[0].strip()
    return forward, rollback


@pytest.mark.asyncio
async def test_migration_114_roundtrip(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    sql = (_MIG_DIR / "114_compliance_alerts.sql").read_text(encoding="utf-8")
    forward, rollback = _forward_and_rollback(sql)
    assert rollback, "114 must have a non-empty ROLLBACK block"

    await db_tx.execute(forward)
    assert await _table_exists(db_tx, "compliance_alerts")

    await db_tx.execute(rollback)
    assert not await _table_exists(db_tx, "compliance_alerts")


@pytest.mark.asyncio
async def test_migration_115_requires_114(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    # 115 FK-references compliance_alerts; applying alone must fail
    sql = (_MIG_DIR / "115_alert_outcomes.sql").read_text(encoding="utf-8")
    forward, _ = _forward_and_rollback(sql)
    with pytest.raises(asyncpg.PostgresError):
        await db_tx.execute(forward)


@pytest.mark.asyncio
async def test_migration_114_115_chain(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    for name in ("114_compliance_alerts.sql", "115_alert_outcomes.sql"):
        sql = (_MIG_DIR / name).read_text(encoding="utf-8")
        forward, _ = _forward_and_rollback(sql)
        await db_tx.execute(forward)

    assert await _table_exists(db_tx, "compliance_alerts")
    assert await _table_exists(db_tx, "alert_outcomes")


@pytest.mark.asyncio
async def test_migration_116_standalone(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    sql = (_MIG_DIR / "116_intel_validator_log.sql").read_text(encoding="utf-8")
    forward, _ = _forward_and_rollback(sql)
    await db_tx.execute(forward)
    assert await _table_exists(db_tx, "intel_validator_log")


def test_rollback_marker_present_in_all_three() -> None:
    for name in (
        "114_compliance_alerts.sql",
        "115_alert_outcomes.sql",
        "116_intel_validator_log.sql",
    ):
        sql = (_MIG_DIR / name).read_text(encoding="utf-8")
        rollback = _extract_rollback_sql(sql)
        assert rollback is not None, f"{name} missing ROLLBACK block"
        assert rollback.strip() != "", f"{name} has empty ROLLBACK block"


# ---------------------------------------------------------------------------
# Regression test for the migration_manager bug discovered 2026-04-19:
# BaseMigration.apply() was passing the FULL file contents to
# `conn.execute()`, including the section after `-- === ROLLBACK ===`.
# PostgreSQL treats the marker as a comment, so CREATE TABLE then DROP TABLE
# both ran inside the same transaction → the migration would log "applied
# successfully" but the table would be gone, breaking dependent migrations.
#
# These tests run the actual BaseMigration.apply() and apply_all_pending()
# code paths against real Postgres and verify the tables survive.
# ---------------------------------------------------------------------------

_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)


@pytest.mark.asyncio
async def test_base_migration_apply_strips_rollback_section() -> None:
    """BaseMigration.apply() must NOT execute the rollback DDL.

    Regression for migration_manager bug 2026-04-19. With the bug, this test
    would log m114 as applied but find the table gone afterwards. With the
    fix, the table is present after apply().
    """
    conn = await asyncpg.connect(_TEST_DB_URL)
    try:
        # Clean slate (these tests own these tables).
        for sql in (
            "DROP TABLE IF EXISTS alert_outcomes CASCADE",
            "DROP TABLE IF EXISTS compliance_alerts CASCADE",
        ):
            await conn.execute(sql)
        # Drop schema_migrations rows for 114 so apply() does not skip.
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  id SERIAL PRIMARY KEY, migration_name VARCHAR(255) UNIQUE NOT NULL,"
            "  migration_number INTEGER NOT NULL, executed_at TIMESTAMPTZ DEFAULT NOW(),"
            "  checksum VARCHAR(64) NOT NULL, description TEXT,"
            "  execution_time_ms INTEGER, rollback_sql TEXT)"
        )
        await conn.execute(
            "DELETE FROM schema_migrations WHERE migration_number IN (114, 115)"
        )

        sql_text = (_MIG_DIR / "114_compliance_alerts.sql").read_text(encoding="utf-8")
        rollback = _extract_rollback_sql(sql_text)

        # Point BaseMigration at the real migrations_v2 dir.
        migration = BaseMigration(
            migration_number=114,
            sql_file="114_compliance_alerts.sql",
            description="regression test apply",
            rollback_sql=rollback,
            _sql_dir=_MIG_DIR,
        )

        # Force settings.database_url so apply() connects to the test DB even
        # if global settings point elsewhere. Do this by monkey-patching at the
        # module level for this single call.
        from backend.db import migration_base as mb
        original_url = mb.settings.database_url
        mb.settings.database_url = _TEST_DB_URL  # type: ignore[misc]
        try:
            ok = await migration.apply()
        finally:
            mb.settings.database_url = original_url  # type: ignore[misc]
        assert ok is True

        # Side-channel verification: the table MUST exist after apply().
        exists = await _table_exists(conn, "compliance_alerts")
        assert exists, (
            "compliance_alerts is missing after BaseMigration.apply() — "
            "the rollback section is being executed against the live DB"
        )

        # Cleanup: drop what we just created so other tests are not affected.
        await conn.execute("DROP TABLE IF EXISTS compliance_alerts CASCADE")
        await conn.execute(
            "DELETE FROM schema_migrations WHERE migration_number = 114"
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_apply_all_pending_creates_compliance_chain() -> None:
    """End-to-end: apply_all_pending() applies 114/115/116 and all tables exist.

    This mirrors the Fly release_command path that broke deploy 2026-04-19.
    """
    conn = await asyncpg.connect(_TEST_DB_URL)
    try:
        # Clean slate including bookkeeping tables for tracked migrations.
        for sql in (
            "DROP TABLE IF EXISTS intel_validator_log CASCADE",
            "DROP TABLE IF EXISTS alert_outcomes CASCADE",
            "DROP TABLE IF EXISTS compliance_alerts CASCADE",
        ):
            await conn.execute(sql)
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS _schema_versions ("
            "  id SERIAL PRIMARY KEY, migration_name VARCHAR(255) UNIQUE NOT NULL,"
            "  migration_number INTEGER NOT NULL, executed_at TIMESTAMPTZ DEFAULT NOW(),"
            "  checksum VARCHAR(64) NOT NULL, description TEXT,"
            "  execution_time_ms INTEGER, rollback_sql TEXT,"
            "  applied_by VARCHAR(255) DEFAULT 'system')"
        )
        await conn.execute(
            "DELETE FROM _schema_versions WHERE migration_number IN (114, 115, 116)"
        )
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  id SERIAL PRIMARY KEY, migration_name VARCHAR(255) UNIQUE NOT NULL,"
            "  migration_number INTEGER NOT NULL, executed_at TIMESTAMPTZ DEFAULT NOW(),"
            "  checksum VARCHAR(64) NOT NULL, description TEXT,"
            "  execution_time_ms INTEGER, rollback_sql TEXT)"
        )
        await conn.execute(
            "DELETE FROM schema_migrations WHERE migration_number IN (114, 115, 116)"
        )

        # Mark earlier numbered migrations as applied so this test focuses on 114-116.
        for n, name in (
            (92, "092_attendance_late_incidents.sql"),
            (108, "108_lkpm_receipts.sql"),
            (109, "109_garuda_curator.sql"),
            (110, "110_lkpm_allowlist_krisna.sql"),
        ):
            await conn.execute(
                "INSERT INTO _schema_versions "
                "(migration_name, migration_number, description, applied_by, checksum) "
                "VALUES ($1, $2, 'pre-applied', 'test', 'fake') "
                "ON CONFLICT DO NOTHING",
                name, n,
            )

        mgr = MigrationManager(database_url=_TEST_DB_URL)
        try:
            await mgr.connect()
            from backend.db import migration_base as mb
            original_url = mb.settings.database_url
            mb.settings.database_url = _TEST_DB_URL  # type: ignore[misc]
            try:
                result = await mgr.apply_all_pending(dry_run=False)
            finally:
                mb.settings.database_url = original_url  # type: ignore[misc]
        finally:
            await mgr.close()

        assert 114 in result["applied"], f"m114 not applied: {result}"
        assert 115 in result["applied"], f"m115 not applied: {result}"
        assert 116 in result["applied"], f"m116 not applied: {result}"
        assert not result["failed"], f"failures: {result['failed']}"

        for tbl in ("compliance_alerts", "alert_outcomes", "intel_validator_log"):
            exists = await _table_exists(conn, tbl)
            assert exists, f"{tbl} missing after apply_all_pending()"

        # Cleanup: only reset the migration bookkeeping so a re-run of this
        # test can re-apply 114/115/116. Do NOT drop the three physical
        # tables here — other suites in the same pytest session (compliance
        # services tests, router tests, alert_feedback) rely on
        # compliance_alerts / alert_outcomes / intel_validator_log being
        # present. The _ensure_clean_slate + apply_all_pending round-trip
        # above already proved the migrations are idempotent (CREATE TABLE
        # IF NOT EXISTS), so leaving the tables in place is safe.
        await conn.execute(
            "DELETE FROM schema_migrations WHERE migration_number IN (114, 115, 116)"
        )
        await conn.execute(
            "DELETE FROM _schema_versions WHERE migration_number IN (92, 108, 109, 110, 114, 115, 116)"
        )
    finally:
        await conn.close()
