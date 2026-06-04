"""Contract tests for migration 211 Olympus residual runtime grants."""

from __future__ import annotations

from pathlib import Path

from backend.db.migration_manager import _extract_rollback_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "211_olympus_residual_runtime_grants.sql"
)

READ_TABLES = ("public.query_clusters", "public.x_monitored_tweets")
WRITE_TABLE = "public.persistent_sessions"


def _forward(sql: str) -> str:
    """Return the forward section applied by the migration runner."""
    return sql.split("-- === ROLLBACK ===", maxsplit=1)[0]


def test_migration_211_file_exists() -> None:
    assert MIGRATION_FILE.exists()


def test_migration_211_has_rollback_marker() -> None:
    sql = MIGRATION_FILE.read_text()

    assert "-- === ROLLBACK ===" in sql
    assert _extract_rollback_sql(sql) is not None


def test_migration_211_targets_runtime_role_conditionally() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "runtime_role constant text := 'backend_rag_v2'" in forward
    assert "pg_roles WHERE rolname = runtime_role" in forward
    assert "GRANT USAGE ON SCHEMA public TO backend_rag_v2" in forward


def test_migration_211_targets_live_olympus_residuals() -> None:
    sql = MIGRATION_FILE.read_text()

    for table in READ_TABLES:
        assert table in sql
    assert WRITE_TABLE in sql


def test_migration_211_grants_read_tables_for_sequence_repair() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "read_objects text[] := ARRAY[" in forward
    assert "GRANT SELECT ON TABLE" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'SELECT')" in forward


def test_migration_211_grants_write_table_for_session_cleanup() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "write_objects text[] := ARRAY[" in forward
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'DELETE')" in forward


def test_migration_211_grants_sequence_update_for_repair() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "pg_get_serial_sequence(object_name, 'id')" in forward
    assert "GRANT USAGE, SELECT, UPDATE ON SEQUENCE" in forward
    assert "has_sequence_privilege(runtime_role, sequence_reg, 'UPDATE')" in forward


def test_migration_211_fails_loudly_when_manual_grants_remain() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "manual grant required: GRANT SELECT ON TABLE" in forward
    assert (
        "manual grant required: GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE"
        in forward
    )
    assert "apply manual grant with an owner/admin role" in forward


def test_migration_211_rollback_revokes_same_grants() -> None:
    rollback = _extract_rollback_sql(MIGRATION_FILE.read_text())

    assert rollback is not None
    assert "REVOKE SELECT ON TABLE" in rollback
    assert "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE" in rollback
    assert "REVOKE USAGE, SELECT, UPDATE ON SEQUENCE" in rollback
