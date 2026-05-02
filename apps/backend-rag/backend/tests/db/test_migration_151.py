"""Verify migration 151 creates observed_shell_events table — Sprint 0 Track C2.

Spec: docs/cell-core/observed-shell-tier.md
Reference: brainstorm 2026-05-02 round 2 § "observed-shell tier"

Round-2 cross-LLM review (4-LLM, PR #426) requested this contract test
to mirror the 150_renewal_alert_outcomes pattern. Verifies forward DDL
+ ROLLBACK marker + Squawk-ignore directives present.
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "151_observed_shell_events.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql, (
        "ROLLBACK marker is required by the migration runner "
        "(see cicatrix: 'Migration Runner Was Executing ROLLBACK Section')"
    )


def test_migration_creates_observed_shell_events_table():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE TABLE IF NOT EXISTS observed_shell_events" in forward_section


def test_migration_has_required_columns():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for col in ("automation_name", "status", "payload", "trace_id", "created_at"):
        assert col in forward_section, f"Column {col} missing"


def test_migration_has_status_check_constraint():
    """Status must be constrained to ok|error|warning|skipped."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for status_value in ("ok", "error", "warning", "skipped"):
        assert f"'{status_value}'" in forward_section, (
            f"Status value '{status_value}' missing from CHECK constraint"
        )


def test_migration_has_partial_indexes():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "ix_observed_shell_events_name_ts" in forward_section
    assert "ix_observed_shell_events_status_ts" in forward_section
    # Partial index: WHERE status != 'ok'
    assert "WHERE status != 'ok'" in forward_section


def test_migration_has_squawk_ignore_directives():
    """Round-2 review: legitimate suppressions on a brand-new empty table
    where Squawk's concurrent-index warning cannot apply."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "squawk-ignore" in forward_section
    assert "require-concurrent-index-creation" in forward_section


def test_rollback_drops_table():
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP TABLE IF EXISTS observed_shell_events" in rollback_section


def test_rollback_drops_indexes_first():
    """Rollback must drop indexes BEFORE the table (although DROP TABLE
    cascades, dropping explicitly is safer for partial-rollback recovery)."""
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    drop_idx_pos = rollback_section.find("DROP INDEX IF EXISTS ix_observed_shell_events_status_ts")
    drop_table_pos = rollback_section.find("DROP TABLE IF EXISTS observed_shell_events")
    assert drop_idx_pos != -1
    assert drop_table_pos != -1
    assert drop_idx_pos < drop_table_pos
