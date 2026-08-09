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
_ROUNDTRIP_MIGRATION_NUMBERS = {114, 115, 116}


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


def _migration_number(path: pathlib.Path) -> int:
    return int(path.name.split("_", 1)[0])


def _non_roundtrip_migration_files() -> list[pathlib.Path]:
    return [
        path
        for path in _MIG_DIR.glob("*.sql")
        if _migration_number(path) not in _ROUNDTRIP_MIGRATION_NUMBERS
    ]


def _forward_and_rollback(sql_text: str) -> tuple[str, str]:
    """Split a migration file into (forward_sql, rollback_sql)."""
    rollback = _extract_rollback_sql(sql_text) or ""
    forward = sql_text.split("-- === ROLLBACK ===")[0].strip()
    return forward, rollback


# The three tables 114/115/116 own. The two autocommit tests at the bottom of
# this file DROP them on a shared database and rebuild them from 114/115/116
# alone — which is exactly the m115-era shape, not today's.
_ROUNDTRIP_TABLES = ("compliance_alerts", "alert_outcomes", "intel_validator_log")


def _later_migrations_touching_roundtrip_tables() -> list[pathlib.Path]:
    """Post-116 migrations whose FORWARD half alters the tables we rebuild.

    Derived from the files, never a hardcoded {258}: a future migration that
    widens one of these tables must be restored too, and nobody will remember
    to add its number here.
    """
    later: list[pathlib.Path] = []
    for path in _MIG_DIR.glob("*.sql"):
        if _migration_number(path) <= 116:
            continue
        forward, _ = _forward_and_rollback(path.read_text(encoding="utf-8"))
        if any(table in forward for table in _ROUNDTRIP_TABLES):
            later.append(path)
    return sorted(later, key=_migration_number)


async def _restore_roundtrip_tables(conn: asyncpg.Connection) -> None:
    """Put the shared DB back at HEAD schema, not at the m115-era one.

    Why this exists (2026-08-08): the two tests below commit their DDL — they
    do NOT use the transactional `db_tx` fixture — and they deliberately leave
    the physical tables in place because later suites need them. But rebuilding
    from 114/115/116 alone recreates `alert_outcomes` with m115's
    `ck_alert_outcomes_outcome CHECK (outcome IN ('dismissed','acted','expired'))`,
    and m258 (which adds 'acknowledged') is marked pre-applied so it never
    re-runs. Everything downstream that writes 'acknowledged' — the compliance
    outcome router, `test_intake_gate` — then dies on a CheckViolationError,
    and only when pytest-randomly happens to order it after this file. That
    intermittency is what made the local pre-push gate spuriously red and
    stranded pushes on machines with a provisioned test DB.
    """
    for name in ("114_compliance_alerts.sql", "115_alert_outcomes.sql", "116_intel_validator_log.sql"):
        forward, _ = _forward_and_rollback((_MIG_DIR / name).read_text(encoding="utf-8"))
        await conn.execute(forward)
    for path in _later_migrations_touching_roundtrip_tables():
        forward, _ = _forward_and_rollback(path.read_text(encoding="utf-8"))
        await conn.execute(forward)


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
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
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
        await conn.execute("DELETE FROM schema_migrations WHERE migration_number IN (114, 115)")

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

        # Cleanup: reset only the bookkeeping so a re-run can re-apply 114.
        await conn.execute("DELETE FROM schema_migrations WHERE migration_number = 114")
    finally:
        # This test DROPped alert_outcomes + compliance_alerts on a SHARED
        # database and rebuilt m114 only, so it would hand the next suite a
        # missing alert_outcomes. Restore runs in `finally` on purpose: a
        # failed assertion above must not leave the database maimed either.
        await _restore_roundtrip_tables(conn)
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
        await conn.execute("DELETE FROM _schema_versions WHERE migration_number IN (114, 115, 116)")
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

        # Mark every migration outside 114/115/116 as applied so this test
        # keeps its intended scope even as newer migration files are added.
        preapplied_names: list[str] = []
        for path in _non_roundtrip_migration_files():
            preapplied_names.append(path.name)
            await conn.execute(
                "INSERT INTO _schema_versions "
                "(migration_name, migration_number, description, applied_by, checksum) "
                "VALUES ($1, $2, 'pre-applied', 'test', 'fake') "
                "ON CONFLICT DO NOTHING",
                path.name,
                _migration_number(path),
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
        # present.
        #
        # Leaving them PRESENT was never the whole job, though: this test runs
        # apply_all_pending() with every other migration marked pre-applied,
        # so the rebuild stops at 116 and the tables come back in their
        # m115-era shape. `_restore_roundtrip_tables` in the `finally` below
        # is what makes "leaving the tables in place" actually safe.
        await conn.execute(
            "DELETE FROM schema_migrations WHERE migration_number IN (114, 115, 116)"
        )
        await conn.execute(
            "DELETE FROM _schema_versions "
            "WHERE migration_number IN (114, 115, 116) "
            "OR (applied_by = 'test' AND migration_name = ANY($1::text[]))",
            preapplied_names,
        )
    finally:
        await _restore_roundtrip_tables(conn)
        await conn.close()


_CONSTRAINT_DEF_SQL = (
    "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
    "JOIN pg_class t ON t.oid = c.conrelid "
    "WHERE c.conname = 'ck_alert_outcomes_outcome' AND t.relname = 'alert_outcomes'"
)


@pytest.mark.asyncio
async def test_restore_puts_alert_outcomes_back_at_head_not_m115() -> None:
    """Pin for the 2026-08-08 cross-test pollution.

    Guilt and innocence in one body, because the interesting claim is the
    DIFFERENCE: rebuilding from m115 alone must produce the narrow constraint
    (asserted, not assumed — a vacuous premise would make the green below
    meaningless), and `_restore_roundtrip_tables` must widen it again.
    """
    conn = await asyncpg.connect(_TEST_DB_URL)
    try:
        await conn.execute("DROP TABLE IF EXISTS alert_outcomes CASCADE")
        await conn.execute("DROP TABLE IF EXISTS compliance_alerts CASCADE")
        for name in ("114_compliance_alerts.sql", "115_alert_outcomes.sql"):
            forward, _ = _forward_and_rollback((_MIG_DIR / name).read_text(encoding="utf-8"))
            await conn.execute(forward)

        narrow = await conn.fetchval(_CONSTRAINT_DEF_SQL)
        assert narrow is not None, "m115 must create ck_alert_outcomes_outcome"
        assert "acknowledged" not in narrow, (
            "PREMISE FAILED: m115 alone is supposed to leave the NARROW constraint. "
            f"Got {narrow!r} — this test can no longer prove anything about the restore."
        )

        await _restore_roundtrip_tables(conn)

        widened = await conn.fetchval(_CONSTRAINT_DEF_SQL)
        assert widened is not None and "acknowledged" in widened, (
            "restore left alert_outcomes at its m115 shape; every later test that "
            f"writes 'acknowledged' will die on CheckViolationError. Got {widened!r}"
        )
    finally:
        await _restore_roundtrip_tables(conn)
        await conn.close()
