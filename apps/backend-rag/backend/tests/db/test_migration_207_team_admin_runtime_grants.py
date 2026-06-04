"""Contract tests for migration 207 team/admin runtime grants.

The migration fixes live permission denials on team/admin endpoints without
assuming every historical table or view exists in local/CI databases.
"""

from __future__ import annotations

from pathlib import Path

from backend.db.migration_manager import _extract_rollback_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "207_team_admin_runtime_grants.sql"
)

LIVE_ERROR_OBJECTS = (
    "public.conversations",
    "public.team_online_status",
)

TEAM_STATUS_OBJECTS = (
    "public.daily_work_hours",
    "public.weekly_work_summary",
    "public.monthly_work_summary",
)

ADMIN_TEAM_ACTIVITY_OBJECTS = (
    "public.v_messages",
    "public.team_timesheet",
    "public.team_members",
    "public.activity_log",
    "public.email_activity_log",
    "public.knowledge_activity_log",
    "public.kg_nodes",
    "public.kg_edges",
)


def _forward(sql: str) -> str:
    """Return the forward section applied by the migration runner."""
    return sql.split("-- === ROLLBACK ===", maxsplit=1)[0]


def test_migration_207_file_exists() -> None:
    assert MIGRATION_FILE.exists()


def test_migration_207_has_rollback_marker() -> None:
    sql = MIGRATION_FILE.read_text()

    assert "-- === ROLLBACK ===" in sql
    assert _extract_rollback_sql(sql) is not None


def test_migration_207_targets_runtime_role_conditionally() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "runtime_role constant text := 'backend_rag_v2'" in forward
    assert "pg_roles WHERE rolname = runtime_role" in forward
    assert "GRANT USAGE ON SCHEMA public TO backend_rag_v2" in forward


def test_migration_207_is_safe_when_historical_objects_are_missing() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "to_regclass(object_name)" in forward
    assert "IF object_reg IS NULL THEN" in forward
    assert "CONTINUE;" in forward


def test_migration_207_checks_existing_privileges_before_granting() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "has_schema_privilege(runtime_role, 'public', 'USAGE')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'SELECT')" in forward
    assert "WHEN insufficient_privilege THEN" in forward
    assert "manual grant required: GRANT USAGE ON SCHEMA public" in forward
    assert "manual grant required: GRANT SELECT ON TABLE" in forward
    assert "apply manual grant with an owner/admin role" in forward


def test_migration_207_grants_live_error_objects() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    for object_name in LIVE_ERROR_OBJECTS:
        assert object_name in forward


def test_migration_207_grants_team_status_dependencies() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    for object_name in TEAM_STATUS_OBJECTS:
        assert object_name in forward


def test_migration_207_grants_admin_team_activity_dependencies() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    for object_name in ADMIN_TEAM_ACTIVITY_OBJECTS:
        assert object_name in forward


def test_migration_207_rollback_revokes_same_select_grants() -> None:
    rollback = _extract_rollback_sql(MIGRATION_FILE.read_text())

    assert rollback is not None
    assert "REVOKE SELECT ON TABLE" in rollback
    for object_name in LIVE_ERROR_OBJECTS + TEAM_STATUS_OBJECTS + ADMIN_TEAM_ACTIVITY_OBJECTS:
        assert object_name in rollback
