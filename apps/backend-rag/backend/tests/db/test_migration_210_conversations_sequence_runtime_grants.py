"""Contract tests for migration 210 conversations sequence runtime grants."""

from __future__ import annotations

from pathlib import Path

from backend.db.migration_manager import _extract_rollback_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "210_conversations_sequence_runtime_grants.sql"
)

SEQUENCE_NAME = "public.conversations_id_seq"


def _forward(sql: str) -> str:
    """Return the forward section applied by the migration runner."""
    return sql.split("-- === ROLLBACK ===", maxsplit=1)[0]


def test_migration_210_file_exists() -> None:
    assert MIGRATION_FILE.exists()


def test_migration_210_has_rollback_marker() -> None:
    sql = MIGRATION_FILE.read_text()

    assert "-- === ROLLBACK ===" in sql
    assert _extract_rollback_sql(sql) is not None


def test_migration_210_targets_runtime_role_conditionally() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "runtime_role constant text := 'backend_rag_v2'" in forward
    assert "pg_roles WHERE rolname = runtime_role" in forward
    assert "GRANT USAGE ON SCHEMA public TO backend_rag_v2" in forward


def test_migration_210_is_safe_when_sequence_is_missing() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "sequence_reg := to_regclass(sequence_name)" in forward
    assert "IF sequence_reg IS NULL THEN" in forward
    assert "RETURN;" in forward


def test_migration_210_checks_existing_privileges_before_granting() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "has_schema_privilege(runtime_role, 'public', 'USAGE')" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'USAGE')" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'SELECT')" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'UPDATE')" in forward
    assert "WHEN insufficient_privilege THEN" in forward
    assert "manual grant required: GRANT USAGE, SELECT, UPDATE ON SEQUENCE" in forward
    assert "apply manual grant with an owner/admin role" in forward


def test_migration_210_grants_live_error_sequence() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT USAGE, SELECT, UPDATE ON SEQUENCE" in forward
    assert SEQUENCE_NAME in forward


def test_migration_210_rollback_revokes_same_grants() -> None:
    rollback = _extract_rollback_sql(MIGRATION_FILE.read_text())

    assert rollback is not None
    assert "REVOKE USAGE, SELECT, UPDATE ON SEQUENCE" in rollback
    assert SEQUENCE_NAME in rollback
