"""Verify migration 152 creates measurer_event triggers — Sprint 2.

Spec: docs/audits/sprint0/wr2-ipc-mechanism.md § "Violation 1 — measurer
       writes to DB but no trigger fires"
Plan: docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md
       § Sprint 2 — WR2 mapping + event contracts

The migration must:
  1. Create notify_measurer_event() function dispatching by TG_TABLE_NAME.
  2. Attach AFTER INSERT triggers on post_metrics_history (mig 128) and
     m13_retrain_log (mig 128).
  3. Persist to events_outbox BEFORE pg_notify (mig 144 outbox pattern).
  4. Inject _outbox_id into the NOTIFY payload (mig 146 contract).
  5. Be idempotent on re-run (CREATE OR REPLACE + DROP TRIGGER IF EXISTS).
  6. Have a -- === ROLLBACK === section.

Mirrors test_migration_151.py contract-test pattern.
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "152_measurer_event_trigger.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql, (
        "ROLLBACK marker is required by the migration runner "
        "(see cicatrix: 'Migration Runner Was Executing ROLLBACK Section')"
    )


def test_migration_creates_notify_function():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE OR REPLACE FUNCTION notify_measurer_event()" in forward_section


def test_migration_dispatches_on_table_name():
    """Function must dispatch to per-table event_type via TG_TABLE_NAME."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "TG_TABLE_NAME = 'post_metrics_history'" in forward_section
    assert "TG_TABLE_NAME = 'm13_retrain_log'" in forward_section
    # Both event_type values must appear
    assert "'metric_recorded'" in forward_section
    assert "'retrain_executed'" in forward_section


def test_migration_writes_to_outbox_before_notify():
    """Mig 146 contract: INSERT INTO events_outbox before pg_notify, both
    inside the user transaction. Order matters — outbox FIRST (durability)."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    insert_pos = forward_section.find("INSERT INTO events_outbox")
    notify_pos = forward_section.find("pg_notify(")
    assert insert_pos != -1, "Must INSERT INTO events_outbox"
    assert notify_pos != -1, "Must call pg_notify"
    assert insert_pos < notify_pos, (
        "events_outbox INSERT must precede pg_notify per migration 146 "
        "outbox pattern (durability before volatile NOTIFY)"
    )


def test_migration_uses_measurer_event_channel():
    """Channel name must match PG_CHANNEL_MAP entry in event_bus.py."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'measurer_event'" in forward_section


def test_migration_injects_outbox_id_into_notify_payload():
    """Mig 146 contract: consumers must receive _outbox_id for idempotent ack."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'_outbox_id'" in forward_section
    assert "outbox_id" in forward_section, (
        "RETURNING id INTO outbox_id required to inject into NOTIFY payload"
    )


def test_migration_attaches_after_insert_triggers():
    """Triggers must be AFTER INSERT only — m13 tables are append-only."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "AFTER INSERT ON post_metrics_history" in forward_section
    assert "AFTER INSERT ON m13_retrain_log" in forward_section
    # FOR EACH ROW required (per-row payload construction)
    assert "FOR EACH ROW" in forward_section


def test_migration_is_idempotent():
    """Re-running the migration must not fail on partial state."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE OR REPLACE FUNCTION" in forward_section
    assert "DROP TRIGGER IF EXISTS post_metrics_history_notify_measurer" in forward_section
    assert "DROP TRIGGER IF EXISTS m13_retrain_log_notify_measurer" in forward_section


def test_pg_channel_map_registers_measurer_event():
    """The Python-side PG_CHANNEL_MAP must include measurer_event so the
    EventBus listener picks up the new channel and the events_outbox
    replay-on-reconnect hook covers it (mig 146 contract)."""
    event_bus_path = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "events"
        / "event_bus.py"
    )
    src = event_bus_path.read_text()
    assert '"measurer_event": "measurer.event"' in src, (
        "PG_CHANNEL_MAP must register measurer_event → measurer.event "
        "(see migration 152 header comment)"
    )


def test_rollback_drops_triggers_then_function():
    """Rollback must drop triggers BEFORE the function (DROP FUNCTION fails
    if triggers still depend on it without CASCADE)."""
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    drop_trigger_post_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS post_metrics_history_notify_measurer"
    )
    drop_trigger_m13_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS m13_retrain_log_notify_measurer"
    )
    drop_function_pos = rollback_section.find(
        "DROP FUNCTION IF EXISTS notify_measurer_event"
    )
    assert drop_trigger_post_pos != -1
    assert drop_trigger_m13_pos != -1
    assert drop_function_pos != -1
    assert drop_trigger_post_pos < drop_function_pos
    assert drop_trigger_m13_pos < drop_function_pos
