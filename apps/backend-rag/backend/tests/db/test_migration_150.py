"""Verify migration 150 creates renewal_alert_outcomes with FK to renewal_alerts.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "150_renewal_alert_outcomes.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql


def test_migration_creates_outcomes_table():
    sql = MIGRATION_FILE.read_text()
    assert "CREATE TABLE IF NOT EXISTS renewal_alert_outcomes" in sql


def test_migration_has_required_columns():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for col in ("alert_id", "outcome", "outcome_at", "observed_by"):
        assert col in forward_section, f"Column {col} missing"


def test_migration_has_outcome_check_constraint():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for outcome_value in (
        "acted_by_team",
        "client_renewed",
        "client_ignored",
        "expired_no_action",
    ):
        assert outcome_value in forward_section, (
            f"Outcome {outcome_value} missing in CHECK"
        )


def test_migration_has_observed_by_check():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'cell'" in forward_section
    assert "'team_member'" in forward_section


def test_migration_has_alert_id_fk():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "REFERENCES renewal_alerts" in forward_section


def test_migration_has_alert_id_index():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert (
        "CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_alert"
        in forward_section
    )


def test_rollback_drops_table():
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP TABLE IF EXISTS renewal_alert_outcomes" in rollback_section
