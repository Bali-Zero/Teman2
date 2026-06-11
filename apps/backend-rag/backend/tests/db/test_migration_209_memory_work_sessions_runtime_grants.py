"""Contract tests for migration 209 memory/work-session runtime grants."""

from __future__ import annotations

from pathlib import Path

from backend.db.migration_manager import _extract_rollback_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "209_memory_work_sessions_runtime_grants.sql"
)

WRITE_OBJECTS = (
    "public.memory_facts",
    "public.team_work_sessions",
)


def _forward(sql: str) -> str:
    """Return the forward section applied by the migration runner."""
    return sql.split("-- === ROLLBACK ===", maxsplit=1)[0]


def test_migration_209_file_exists() -> None:
    assert MIGRATION_FILE.exists()


def test_migration_209_has_rollback_marker() -> None:
    sql = MIGRATION_FILE.read_text()

    assert "-- === ROLLBACK ===" in sql
    assert _extract_rollback_sql(sql) is not None


def test_migration_209_targets_runtime_role_conditionally() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "runtime_role constant text := 'backend_rag_v2'" in forward
    assert "pg_roles WHERE rolname = runtime_role" in forward
    assert "GRANT USAGE ON SCHEMA public TO backend_rag_v2" in forward


def test_migration_209_is_safe_when_objects_are_missing() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "to_regclass(object_name)" in forward
    assert "IF object_reg IS NULL THEN" in forward
    assert "CONTINUE;" in forward


def test_migration_209_checks_existing_privileges_before_granting() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "has_schema_privilege(runtime_role, 'public', 'USAGE')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'SELECT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'INSERT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'UPDATE')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'DELETE')" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'USAGE')" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'SELECT')" in forward
    assert "WHEN insufficient_privilege THEN" in forward
    assert "manual grant required: GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE" in forward
    assert "manual grant required: GRANT USAGE, SELECT ON SEQUENCE" in forward
    assert "apply manual grant with an owner/admin role" in forward


def test_migration_209_grants_live_error_objects() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE" in forward
    assert "GRANT USAGE, SELECT ON SEQUENCE" in forward
    for object_name in WRITE_OBJECTS:
        assert object_name in forward


def test_migration_209_rollback_revokes_same_grants() -> None:
    rollback = _extract_rollback_sql(MIGRATION_FILE.read_text())

    assert rollback is not None
    assert "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE" in rollback
    assert "REVOKE USAGE, SELECT ON SEQUENCE" in rollback
    for object_name in WRITE_OBJECTS:
        assert object_name in rollback
