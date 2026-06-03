"""Contract tests for migration 208 analytics runtime grants."""

from __future__ import annotations

from pathlib import Path

from backend.db.migration_manager import _extract_rollback_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "208_analytics_runtime_grants.sql"
)

WRITE_OBJECTS = (
    "public.attendance_late_incidents",
    "public.team_timesheet",
)

EXECUTE_FUNCTIONS = ("public.auto_logout_expired_sessions()",)


def _forward(sql: str) -> str:
    """Return the forward section applied by the migration runner."""
    return sql.split("-- === ROLLBACK ===", maxsplit=1)[0]


def test_migration_208_file_exists() -> None:
    assert MIGRATION_FILE.exists()


def test_migration_208_has_rollback_marker() -> None:
    sql = MIGRATION_FILE.read_text()

    assert "-- === ROLLBACK ===" in sql
    assert _extract_rollback_sql(sql) is not None


def test_migration_208_targets_runtime_role_conditionally() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "runtime_role constant text := 'backend_rag_v2'" in forward
    assert "pg_roles WHERE rolname = runtime_role" in forward
    assert "GRANT USAGE ON SCHEMA public TO backend_rag_v2" in forward


def test_migration_208_is_safe_when_objects_are_missing() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "to_regclass(object_name)" in forward
    assert "to_regprocedure(function_name)" in forward
    assert "IF object_reg IS NULL THEN" in forward
    assert "IF function_reg IS NULL THEN" in forward
    assert "CONTINUE;" in forward


def test_migration_208_checks_existing_privileges_before_granting() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "has_schema_privilege(runtime_role, 'public', 'USAGE')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'SELECT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'INSERT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'UPDATE')" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'USAGE')" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'SELECT')" in forward
    assert "has_function_privilege(runtime_role, function_reg, 'EXECUTE')" in forward
    assert "WHEN insufficient_privilege THEN" in forward
    assert "manual grant required: GRANT SELECT, INSERT, UPDATE ON TABLE" in forward
    assert "manual grant required: GRANT USAGE, SELECT ON SEQUENCE" in forward
    assert "manual grant required: GRANT EXECUTE ON FUNCTION" in forward
    assert "apply manual grant with an owner/admin role" in forward


def test_migration_208_grants_live_error_objects() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT SELECT, INSERT, UPDATE ON TABLE" in forward
    assert "GRANT USAGE, SELECT ON SEQUENCE" in forward
    for object_name in WRITE_OBJECTS:
        assert object_name in forward


def test_migration_208_grants_live_error_functions() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT EXECUTE ON FUNCTION" in forward
    for function_name in EXECUTE_FUNCTIONS:
        assert function_name in forward


def test_migration_208_rollback_revokes_same_grants() -> None:
    rollback = _extract_rollback_sql(MIGRATION_FILE.read_text())

    assert rollback is not None
    assert "REVOKE SELECT, INSERT, UPDATE ON TABLE" in rollback
    assert "REVOKE USAGE, SELECT ON SEQUENCE" in rollback
    assert "REVOKE EXECUTE ON FUNCTION" in rollback
    for object_name in WRITE_OBJECTS:
        assert object_name in rollback
    for function_name in EXECUTE_FUNCTIONS:
        assert function_name in rollback
