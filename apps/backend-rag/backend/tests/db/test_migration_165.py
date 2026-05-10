"""Verify migration 165 keeps the migration ledger reconciliation safe."""

from __future__ import annotations

from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "165_reconcile_schema_migrations_duplicates.sql"
)


def _sections() -> tuple[str, str]:
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, rollback = sql.split("-- === ROLLBACK ===", maxsplit=1)
    return forward, rollback


def test_migration_file_exists() -> None:
    assert MIGRATION_FILE.exists(), f"Migration file missing: {MIGRATION_FILE}"


def test_migration_has_rollback_marker() -> None:
    assert "-- === ROLLBACK ===" in MIGRATION_FILE.read_text(encoding="utf-8")


def test_forward_archives_duplicate_tracking_rows_before_delete() -> None:
    forward, _rollback = _sections()

    assert "schema_migrations_reconciliation_archive" in forward
    assert "165_schema_migrations_duplicate_number_reconcile" in forward
    assert "rows_to_archive" in forward
    assert "DELETE FROM schema_migrations" in forward
    assert "ON CONFLICT (archive_reason, migration_name) DO NOTHING" in forward


def test_forward_adds_unique_migration_number_index_and_tracking_row() -> None:
    forward, _rollback = _sections()

    assert "uq_schema_migrations_migration_number" in forward
    assert "CREATE UNIQUE INDEX IF NOT EXISTS" in forward
    assert "ON schema_migrations (migration_number)" in forward
    assert "INSERT INTO _schema_versions" in forward
    assert "165_reconcile_schema_migrations_duplicates" in forward


def test_rollback_restores_archive_and_removes_tracking_row() -> None:
    _forward, rollback = _sections()

    assert "DROP INDEX IF EXISTS uq_schema_migrations_migration_number" in rollback
    assert "INSERT INTO schema_migrations" in rollback
    assert "FROM schema_migrations_reconciliation_archive" in rollback
    assert "ON CONFLICT (migration_name) DO NOTHING" in rollback
    assert "DELETE FROM _schema_versions" in rollback
