"""Verify migration 166 reconciles client email duplicates safely."""

from __future__ import annotations

from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "166_reconcile_client_email_duplicates.sql"
)


def _forward_sql() -> str:
    return MIGRATION_FILE.read_text(encoding="utf-8").split("-- === ROLLBACK ===")[0]


def test_migration_file_exists() -> None:
    assert MIGRATION_FILE.exists(), f"Migration file missing: {MIGRATION_FILE}"


def test_migration_has_rollback_marker() -> None:
    assert "-- === ROLLBACK ===" in MIGRATION_FILE.read_text(encoding="utf-8")


def test_migration_archives_changed_client_emails() -> None:
    sql = _forward_sql()
    assert "client_email_reconciliation_archive" in sql
    assert "client_snapshot" in sql
    assert "duplicate_case_insensitive_email_to_null" in sql


def test_migration_normalizes_email_and_adds_case_insensitive_unique_index() -> None:
    sql = _forward_sql()
    assert "LOWER(BTRIM(email))" in sql
    assert "uq_clients_email_lower_not_blank" in sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS" in sql
