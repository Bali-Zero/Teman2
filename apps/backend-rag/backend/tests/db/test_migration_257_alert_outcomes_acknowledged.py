"""Contract checks for migration 257's compliance outcome alignment."""

from pathlib import Path

_MIGRATION = (
    Path(__file__).parents[2]
    / "db"
    / "migrations_v2"
    / "257_alert_outcomes_acknowledged.sql"
)


def test_migration_257_aligns_outcome_and_status_contracts() -> None:
    sql = _MIGRATION.read_text(encoding="utf-8")
    forward, rollback = sql.split("-- === ROLLBACK ===", maxsplit=1)

    assert "ck_alert_outcomes_outcome" in forward
    assert "'acknowledged'" in forward
    assert "NOT VALID" in forward
    assert "VALIDATE CONSTRAINT ck_alert_outcomes_outcome" in forward

    assert "WHERE outcome = 'acknowledged'" in rollback
    assert "SET outcome = 'dismissed'" in rollback
    assert "'acknowledged'" not in rollback.split("CHECK", maxsplit=1)[1]
