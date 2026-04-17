"""
TDD tests for rollback enforcement in migration_base.

Tests:
1. MigrationIrreversibleError exists and is raiseable with a message.
2. A migration that properly implements rollback_sql is accepted.
3. A new migration (not in legacy whitelist) that omits rollback_sql
   raises ValueError at construction time.
4. A legacy migration (in LEGACY_NO_ROLLBACK_WHITELIST) is accepted
   without rollback_sql.
5. verify_apply and verify_rollback return bool by default.
"""

import pytest

from backend.db.migration_base import (
    BaseMigration,
    LEGACY_NO_ROLLBACK_WHITELIST,
    MigrationError,
    MigrationIrreversibleError,
)


# ---------------------------------------------------------------------------
# 1. MigrationIrreversibleError
# ---------------------------------------------------------------------------

def test_migration_irreversible_error_is_exception() -> None:
    err = MigrationIrreversibleError("DROP TABLE users — cannot be reversed")
    assert isinstance(err, Exception)
    assert "cannot be reversed" in str(err)


def test_migration_irreversible_error_inherits_migration_error() -> None:
    err = MigrationIrreversibleError("test")
    assert isinstance(err, MigrationError)


# ---------------------------------------------------------------------------
# 2. Legacy whitelist exists and is a frozenset
# ---------------------------------------------------------------------------

def test_legacy_whitelist_is_frozenset() -> None:
    assert isinstance(LEGACY_NO_ROLLBACK_WHITELIST, frozenset)


def test_legacy_whitelist_contains_known_pre_2026_migrations() -> None:
    # Migrations 001–111 should all be in whitelist (pre-2026-04-18 legacy)
    assert "migration_001" in LEGACY_NO_ROLLBACK_WHITELIST
    assert "migration_080a_visa_oracle_sessions" in LEGACY_NO_ROLLBACK_WHITELIST
    assert "migration_111_notification_log" in LEGACY_NO_ROLLBACK_WHITELIST


# ---------------------------------------------------------------------------
# 3. BaseMigration construction: new migration WITHOUT rollback_sql raises
# ---------------------------------------------------------------------------

def test_new_migration_without_rollback_sql_raises(tmp_path) -> None:
    """A migration number > 111 (post-cutoff) must supply rollback_sql."""
    sql_file = tmp_path / "200_test.sql"
    sql_file.write_text("CREATE TABLE test_table (id SERIAL PRIMARY KEY);")

    with pytest.raises(ValueError, match="rollback_sql"):
        BaseMigration(
            migration_number=200,
            sql_file="200_test.sql",
            description="Test migration requiring rollback",
            # rollback_sql intentionally omitted
            _sql_dir=tmp_path,
        )


def test_new_migration_with_rollback_sql_accepted(tmp_path) -> None:
    """A post-cutoff migration that supplies rollback_sql is constructed fine."""
    sql_file = tmp_path / "201_test.sql"
    sql_file.write_text("CREATE TABLE test_table2 (id SERIAL PRIMARY KEY);")

    migration = BaseMigration(
        migration_number=201,
        sql_file="201_test.sql",
        description="Test migration with rollback",
        rollback_sql="DROP TABLE IF EXISTS test_table2;",
        _sql_dir=tmp_path,
    )
    assert migration.rollback_sql == "DROP TABLE IF EXISTS test_table2;"


# ---------------------------------------------------------------------------
# 4. Legacy migration WITHOUT rollback_sql is accepted (whitelist bypass)
# ---------------------------------------------------------------------------

def test_legacy_migration_without_rollback_accepted(tmp_path) -> None:
    """Migrations in LEGACY_NO_ROLLBACK_WHITELIST bypass the rollback requirement."""
    sql_file = tmp_path / "001_fix_missing_tables.sql"
    sql_file.write_text("CREATE TABLE IF NOT EXISTS cultural_knowledge (id SERIAL);")

    # migration_name will be "001_fix_missing_tables" — must be in whitelist
    migration = BaseMigration(
        migration_number=1,
        sql_file="001_fix_missing_tables.sql",
        description="Legacy baseline",
        # rollback_sql intentionally absent
        _sql_dir=tmp_path,
    )
    assert migration.rollback_sql is None


# ---------------------------------------------------------------------------
# 5. verify_apply and verify_rollback return True by default (sync stubs)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_apply_returns_true_by_default(tmp_path) -> None:
    sql_file = tmp_path / "001_fix_missing_tables.sql"
    sql_file.write_text("SELECT 1;")

    migration = BaseMigration(
        migration_number=1,
        sql_file="001_fix_missing_tables.sql",
        description="Legacy",
        _sql_dir=tmp_path,
    )
    result = await migration.verify_apply(None)  # conn=None for unit test
    assert result is True


@pytest.mark.asyncio
async def test_verify_rollback_returns_true_by_default(tmp_path) -> None:
    sql_file = tmp_path / "001_fix_missing_tables.sql"
    sql_file.write_text("SELECT 1;")

    migration = BaseMigration(
        migration_number=1,
        sql_file="001_fix_missing_tables.sql",
        description="Legacy",
        _sql_dir=tmp_path,
    )
    result = await migration.verify_rollback(None)
    assert result is True
