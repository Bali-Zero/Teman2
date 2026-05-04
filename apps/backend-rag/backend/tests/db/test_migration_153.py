"""Verify migration 153 creates crm_welcome_runs table + trigger — Sprint 3 W2.

Spec: docs/sprint3/crm-cell-design.md § Q2c "New crm_welcome_completed channel"
       and § "crm_welcome_runs table spec"

The migration must:
  1. Create crm_welcome_runs table with the specced columns + UNIQUE constraint.
  2. Create notify_crm_welcome_completed() function emitting only when
     success=true (audit rows persist regardless, but downstream observers
     receive only full-success events).
  3. Persist to events_outbox BEFORE pg_notify (mig 144 outbox pattern).
  4. Inject _outbox_id into the NOTIFY payload (mig 146 contract).
  5. Be idempotent on re-run.
  6. Have a -- === ROLLBACK === section.
  7. Register crm_welcome_completed → crm.welcome_completed in PG_CHANNEL_MAP.

Mirrors test_migration_152.py contract-test pattern.
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "153_crm_welcome_runs.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql, (
        "ROLLBACK marker is required by the migration runner "
        "(see cicatrix: 'Migration Runner Was Executing ROLLBACK Section')"
    )


def test_migration_creates_crm_welcome_runs_table():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE TABLE IF NOT EXISTS crm_welcome_runs" in forward_section


def test_migration_table_has_required_columns():
    """crm_welcome_runs must carry the columns specced in W1.2."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # Core identity
    assert "client_id BIGINT NOT NULL REFERENCES clients(id)" in forward_section
    assert "practice_id BIGINT REFERENCES practices(id)" in forward_section
    # Welcome flow artifacts
    assert "drive_folder_id" in forward_section
    assert "channels_sent TEXT[]" in forward_section
    # Audit
    assert "started_at TIMESTAMPTZ" in forward_section
    assert "completed_at TIMESTAMPTZ" in forward_section
    # Success gate (only-true rows fire the event)
    assert "success BOOLEAN NOT NULL" in forward_section
    # Forward-compat metadata
    assert "metadata JSONB" in forward_section
    # Dedup constraint — one welcome run per (client, practice)
    assert "UNIQUE (client_id, practice_id)" in forward_section


def test_migration_creates_notify_function():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE OR REPLACE FUNCTION notify_crm_welcome_completed()" in forward_section


def test_migration_emits_only_on_success_true():
    """The trigger must NOT broadcast partial-failure rows. Audit-only.

    Post 2026-05-04 multi-LLM W2 review: the success=true guard moved
    from the function body to the trigger WHEN clause to also cover the
    UPSERT retry path (false→true UPDATE transition). The function body
    is now the unconditional emit; correctness depends on the WHEN.
    """
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # The WHEN guard on the trigger declaration enforces success=true
    assert "WHEN (NEW.success = true" in forward_section
    # event_type literal in the function body
    assert "'welcome_completed'" in forward_section


def test_migration_trigger_fires_on_false_to_true_transition():
    """Sprint 3 W2 review B1 fix: the trigger MUST fire on UPDATE
    when OLD.success=false → NEW.success=true (cell adapter UPSERT
    retry path), not just on INSERT.
    """
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "AFTER INSERT OR UPDATE ON crm_welcome_runs" in forward_section
    # The WHEN clause must explicitly include the OLD.success transition
    assert "OLD.success IS DISTINCT FROM NEW.success" in forward_section


def test_migration_trigger_does_not_fire_on_noop_update():
    """Idempotent UPSERT (true→true rewrite with same values) MUST NOT
    re-emit the welcome_completed event. The WHEN clause filters via
    OLD.success IS DISTINCT FROM NEW.success which evaluates false on
    no-op true→true transitions (as well as false→false).
    """
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # Documentation comment block in the trigger declaration calls out
    # the no-op case explicitly so future readers understand the intent.
    assert "true→true (no-op)" in forward_section.lower() or \
           "true→true" in forward_section


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


def test_migration_uses_crm_welcome_completed_channel():
    """Channel name must match PG_CHANNEL_MAP entry in event_bus.py."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'crm_welcome_completed'" in forward_section


def test_migration_injects_outbox_id_into_notify_payload():
    """Mig 146 contract: consumers must receive _outbox_id for idempotent ack."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'_outbox_id'" in forward_section
    assert "outbox_id" in forward_section, (
        "RETURNING id INTO outbox_id required to inject into NOTIFY payload"
    )


def test_migration_attaches_after_insert_or_update_trigger():
    """Trigger must be AFTER INSERT OR UPDATE — fires on the
    false→true success transition (whether new row or retry UPSERT)."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "AFTER INSERT OR UPDATE ON crm_welcome_runs" in forward_section
    assert "FOR EACH ROW" in forward_section
    # WHEN clause is the actual guard
    assert "WHEN (NEW.success = true" in forward_section


def test_migration_is_idempotent():
    """Re-running the migration must not fail on partial state."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE TABLE IF NOT EXISTS crm_welcome_runs" in forward_section
    assert "CREATE OR REPLACE FUNCTION" in forward_section
    assert "DROP TRIGGER IF EXISTS crm_welcome_runs_notify" in forward_section
    assert "CREATE INDEX IF NOT EXISTS ix_crm_welcome_runs_client" in forward_section
    assert "CREATE INDEX IF NOT EXISTS ix_crm_welcome_runs_completed" in forward_section


def test_pg_channel_map_registers_crm_welcome_completed():
    """The Python-side PG_CHANNEL_MAP must include crm_welcome_completed so
    the EventBus listener picks up the new channel and the events_outbox
    replay-on-reconnect hook covers it (mig 146 contract)."""
    event_bus_path = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "events"
        / "event_bus.py"
    )
    src = event_bus_path.read_text()
    assert '"crm_welcome_completed": "crm.welcome_completed"' in src, (
        "PG_CHANNEL_MAP must register crm_welcome_completed → crm.welcome_completed "
        "(see migration 153 header comment)"
    )


def test_rollback_drops_trigger_then_function_then_table():
    """Rollback ordering: trigger → function → indexes → table. DROP FUNCTION
    fails if a trigger still depends on it (without CASCADE), and DROP TABLE
    fails if indexes still reference it (though indexes auto-drop on DROP
    TABLE; we drop them explicitly for clarity)."""
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    drop_trigger_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS crm_welcome_runs_notify"
    )
    drop_function_pos = rollback_section.find(
        "DROP FUNCTION IF EXISTS notify_crm_welcome_completed"
    )
    drop_table_pos = rollback_section.find(
        "DROP TABLE IF EXISTS crm_welcome_runs"
    )
    assert drop_trigger_pos != -1
    assert drop_function_pos != -1
    assert drop_table_pos != -1
    assert drop_trigger_pos < drop_function_pos
    assert drop_function_pos < drop_table_pos
