"""Verify migration 317 declares a 30-day default for visa_oracle_sessions.expires_at
and its rollback restores 90 days — parses the .sql file, no database needed.

No shipped test previously covered this: `test_retention_policy_scope_family_tripwire.py`
governs a different scope-predicate family, and no test named visa_oracle_sessions'
expires_at default anywhere in backend/tests/. This file exists to catch a regression
where the default silently stays at 90 days (the value PROD carries today).
"""

from __future__ import annotations

from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "317_visa_oracle_sessions_retention_30d.sql"
)


def _sections() -> tuple[str, str]:
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, rollback = sql.split("-- === ROLLBACK ===", maxsplit=1)
    return forward, rollback


def _executable_lines(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def test_migration_file_exists() -> None:
    assert MIGRATION_FILE.exists(), f"Migration file missing: {MIGRATION_FILE}"


def test_forward_sets_the_default_to_30_days() -> None:
    """The load-bearing declaration: NEW rows must default to 30 days, not 90."""
    forward, _rollback = _sections()
    executable = _executable_lines(forward)

    assert "ALTER TABLE public.visa_oracle_sessions" in executable
    assert "ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '30 days')" in executable
    # The 90-day value may appear in the CREATE TABLE IF NOT EXISTS fallback
    # (provenance guard for a fresh database) but the final ALTER must win.
    alter_idx = executable.rindex("ALTER COLUMN expires_at SET DEFAULT")
    assert "30 days" in executable[alter_idx : alter_idx + 80]


def test_forward_does_not_rewrite_existing_rows() -> None:
    """Conservative choice: existing rows keep their already-declared 90-day
    expires_at. No UPDATE statement may touch the table."""
    forward, _rollback = _sections()
    executable = _executable_lines(forward).upper()

    assert "UPDATE " not in executable
    assert "DELETE " not in executable


def test_forward_ddl_is_idempotent() -> None:
    """CREATE TABLE / CREATE INDEX must be guarded so a re-run against a
    database that already has the table is a no-op, not an error."""
    forward, _rollback = _sections()

    assert "CREATE TABLE IF NOT EXISTS public.visa_oracle_sessions" in forward
    assert "CREATE INDEX IF NOT EXISTS idx_vo_sessions_session_id" in forward
    assert "CREATE INDEX IF NOT EXISTS idx_vo_sessions_created_at" in forward


def test_rollback_restores_90_days() -> None:
    _forward, rollback = _sections()
    executable = _executable_lines(rollback)

    assert "ALTER TABLE public.visa_oracle_sessions" in executable
    assert "ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '90 days')" in executable


def test_rollback_does_not_rewrite_existing_rows() -> None:
    _forward, rollback = _sections()
    executable = _executable_lines(rollback).upper()

    assert "UPDATE " not in executable
    assert "DELETE " not in executable
    assert "DROP TABLE" not in executable
