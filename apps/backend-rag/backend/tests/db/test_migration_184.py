"""Verify migration 184 only reconciles the migration tracking ledger."""

from __future__ import annotations

from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "184_reconcile_182_tracking_divergence.sql"
)


def _sections() -> tuple[str, str]:
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, rollback = sql.split("-- === ROLLBACK ===", maxsplit=1)
    return forward, rollback


def _executable_lines(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def test_migration_file_exists() -> None:
    assert MIGRATION_FILE.exists(), f"Migration file missing: {MIGRATION_FILE}"


def test_forward_backfills_legacy_tracking_from_canonical_row() -> None:
    forward, _rollback = _sections()

    assert "INSERT INTO _schema_versions" in forward
    assert "FROM schema_migrations sm" in forward
    assert "WHERE sm.migration_number = 182" in forward
    assert "WHERE sv.migration_number = 182" in forward
    assert "migration-184-ledger-reconcile" in forward
    assert "ON CONFLICT (migration_name) DO NOTHING" in forward


def test_forward_does_not_touch_application_tables() -> None:
    forward, _rollback = _sections()
    executable = _executable_lines(forward)

    assert "clients" not in executable
    assert "companies" not in executable
    assert "company_documents" not in executable
    assert "DROP " not in executable.upper()
    assert "DELETE " not in executable.upper()


def test_rollback_is_intentionally_noop() -> None:
    _forward, rollback = _sections()

    assert "Intentionally no-op" in rollback
    assert "DELETE " not in rollback.upper()
    assert "DROP " not in rollback.upper()
