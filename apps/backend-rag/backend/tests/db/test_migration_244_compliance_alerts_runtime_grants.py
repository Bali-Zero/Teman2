"""Contract tests for migration 244 compliance_alerts runtime grants."""

from __future__ import annotations

from pathlib import Path

from backend.db.migration_manager import _extract_rollback_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "244_compliance_alerts_runtime_grants.sql"
)

WRITE_OBJECTS = ("public.compliance_alerts",)


def _forward(sql: str) -> str:
    """Return the forward section applied by the migration runner."""
    return sql.split("-- === ROLLBACK ===", maxsplit=1)[0]


def test_migration_244_file_exists() -> None:
    assert MIGRATION_FILE.exists()


def test_migration_244_has_rollback_marker() -> None:
    sql = MIGRATION_FILE.read_text()

    assert "-- === ROLLBACK ===" in sql
    assert _extract_rollback_sql(sql) is not None


def test_migration_244_targets_runtime_role_conditionally() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "runtime_role constant text := 'backend_rag_v2'" in forward
    assert "pg_roles WHERE rolname = runtime_role" in forward
    assert "GRANT USAGE ON SCHEMA public TO backend_rag_v2" in forward


def test_migration_244_is_safe_when_object_is_missing() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "to_regclass(object_name)" in forward
    assert "IF object_reg IS NULL THEN" in forward
    assert "CONTINUE;" in forward


def test_migration_244_checks_existing_privileges_before_granting() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "has_schema_privilege(runtime_role, 'public', 'USAGE')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'SELECT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'INSERT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'UPDATE')" in forward
    assert "WHEN insufficient_privilege THEN" in forward
    assert "manual grant required: GRANT SELECT, INSERT, UPDATE ON TABLE" in forward
    assert "apply manual grant with an owner/admin role" in forward


def test_migration_244_grants_live_error_object() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT SELECT, INSERT, UPDATE ON TABLE" in forward
    for object_name in WRITE_OBJECTS:
        assert object_name in forward


def test_migration_244_does_not_over_grant_delete() -> None:
    """Least-privilege guard: no runtime code path DELETEs compliance_alerts
    rows (backend/services/compliance/alert_repository.py is INSERT/SELECT/
    UPDATE only) — only test-fixture teardown does, under the local `test`
    role. This migration must never grant DELETE to backend_rag_v2; a future
    edit that copy-pastes the 207/209/211 four-privilege bundle onto this
    table would silently regress that guarantee.

    Checks the actual SQL verbs/privilege-check calls, not a bare substring
    scan of the whole file — the header comment legitimately discusses
    DELETE in prose (why it's excluded), and a blind "DELETE not in forward"
    assertion would false-positive on that prose (guard over-match, cicatrix
    family #3) instead of checking the grant itself.
    """
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT SELECT, INSERT, UPDATE, DELETE" not in forward
    assert "has_table_privilege(runtime_role, object_reg, 'DELETE')" not in forward
    assert "REVOKE SELECT, INSERT, UPDATE, DELETE" not in forward


def test_migration_244_rollback_revokes_same_grants() -> None:
    rollback = _extract_rollback_sql(MIGRATION_FILE.read_text())

    assert rollback is not None
    assert "REVOKE SELECT, INSERT, UPDATE ON TABLE" in rollback
    assert "DELETE" not in rollback
    for object_name in WRITE_OBJECTS:
        assert object_name in rollback
