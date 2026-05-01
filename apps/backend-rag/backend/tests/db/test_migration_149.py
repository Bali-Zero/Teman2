"""Verify migration 149 creates client_segments with expected schema.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4
Cicatrix: 2026-04-19-migration-runner — ROLLBACK marker mandatory.
Cicatrix: 2026-04-26-atlas-paywalled — Squawk lint applies at PR time.
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "149_client_segments.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists(), f"Migration file missing: {MIGRATION_FILE}"


def test_migration_has_rollback_marker():
    """Cicatrix 2026-04-19 enforces -- === ROLLBACK === marker."""
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql, (
        "Migration must include -- === ROLLBACK === marker (cicatrix 2026-04-19)"
    )


def test_migration_creates_client_segments_table():
    sql = MIGRATION_FILE.read_text()
    assert "CREATE TABLE IF NOT EXISTS client_segments" in sql


def test_migration_has_required_columns():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for col in ("client_id", "tier", "lifetime_value_usd", "computed_at"):
        assert col in forward_section, f"Column {col} missing in forward section"


def test_migration_has_tier_check_constraint():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert (
        "CHECK (tier IN (1, 2, 3))" in forward_section
        or "tier BETWEEN 1 AND 3" in forward_section
    )


def test_migration_has_client_id_fk():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "REFERENCES clients(id)" in forward_section


def test_migration_has_indexes():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE INDEX IF NOT EXISTS idx_client_segments_tier" in forward_section
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_client_segments_client" in forward_section
    )


def test_rollback_drops_table():
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP TABLE IF EXISTS client_segments" in rollback_section
