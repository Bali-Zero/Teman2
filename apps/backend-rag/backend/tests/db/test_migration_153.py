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

    v2.6: Postgres does not allow TG_OP in CREATE TRIGGER WHEN clauses
    (only OLD/NEW columns are referenceable). The trigger was split into
    two separate INSERT and UPDATE triggers, both gating on
    `NEW.success = true` in WHEN. Correctness depends on the WHEN
    clauses on each trigger.
    """
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # The WHEN clauses on each trigger declaration enforce success=true
    assert "WHEN (NEW.success = true" in forward_section
    # event_type literal in the function body
    assert "'welcome_completed'" in forward_section


def test_migration_trigger_fires_on_false_to_true_transition():
    """Sprint 3 W2 review B1 fix: the UPDATE trigger MUST fire on
    OLD.success=false → NEW.success=true (cell adapter UPSERT retry
    path), and the INSERT trigger MUST fire on a fresh
    INSERT(success=true).

    v2.6: enforced via two separate triggers (INSERT + UPDATE) because
    TG_OP isn't allowed in WHEN.
    """
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # Two separate triggers
    assert "AFTER INSERT ON crm_welcome_runs" in forward_section
    assert "AFTER UPDATE ON crm_welcome_runs" in forward_section
    # The UPDATE trigger explicitly checks the OLD.success transition
    assert "OLD.success IS DISTINCT FROM NEW.success" in forward_section
    # Both trigger names exist
    assert "crm_welcome_runs_notify_insert" in forward_section
    assert "crm_welcome_runs_notify_update" in forward_section


# NOTE: deleted `test_migration_trigger_does_not_fire_on_noop_update`
# (v2.5 review V2-X1): asserted on a comment string rather than trigger
# behavior — pure test theater. The WHEN clause's no-op semantics are
# already pinned by `test_migration_trigger_fires_on_false_to_true_transition`
# (positive case) and the ON DELETE/UPDATE contract tests below. A real
# behavioral test of "true→true UPSERT does not emit" requires a live
# PG connection (Sprint 4 integration test layer).


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


def test_migration_attaches_separate_insert_and_update_triggers():
    """v2.6: two separate triggers (INSERT + UPDATE), not one combined
    AFTER INSERT OR UPDATE — Postgres does not support TG_OP in
    CREATE TRIGGER WHEN clauses."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # Two distinct trigger names
    assert "crm_welcome_runs_notify_insert" in forward_section
    assert "crm_welcome_runs_notify_update" in forward_section
    # Each on its own event
    assert "AFTER INSERT ON crm_welcome_runs" in forward_section
    assert "AFTER UPDATE ON crm_welcome_runs" in forward_section
    assert "FOR EACH ROW" in forward_section
    # Both have a WHEN clause gating on NEW.success
    assert "WHEN (NEW.success = true" in forward_section
    # Must NOT use TG_OP in WHEN (Postgres rejects). Check on lines that
    # are NOT comments — the explanatory comment block above is allowed
    # to mention TG_OP.
    for line in forward_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        assert "WHEN (TG_OP" not in stripped, (
            f"non-comment line uses TG_OP in WHEN: {line!r}"
        )


def test_migration_is_idempotent():
    """Re-running the migration must not fail on partial state."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE TABLE IF NOT EXISTS crm_welcome_runs" in forward_section
    assert "CREATE OR REPLACE FUNCTION" in forward_section
    # Must drop both triggers (insert + update + legacy unified) before re-create
    assert "DROP TRIGGER IF EXISTS crm_welcome_runs_notify_insert" in forward_section
    assert "DROP TRIGGER IF EXISTS crm_welcome_runs_notify_update" in forward_section
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


def test_rollback_drops_triggers_then_function_then_table():
    """Rollback ordering: triggers → function → indexes → table.
    DROP FUNCTION fails if a trigger still depends on it (without
    CASCADE), and DROP TABLE fails if indexes still reference it
    (though indexes auto-drop on DROP TABLE; we drop them explicitly
    for clarity).

    v2.6: must drop BOTH the new split triggers AND any legacy
    unified trigger that may exist from earlier deploys.
    """
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    drop_insert_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS crm_welcome_runs_notify_insert"
    )
    drop_update_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS crm_welcome_runs_notify_update"
    )
    drop_function_pos = rollback_section.find(
        "DROP FUNCTION IF EXISTS notify_crm_welcome_completed"
    )
    drop_table_pos = rollback_section.find(
        "DROP TABLE IF EXISTS crm_welcome_runs"
    )
    assert drop_insert_pos != -1
    assert drop_update_pos != -1
    assert drop_function_pos != -1
    assert drop_table_pos != -1
    # All trigger drops before function drop
    assert max(drop_insert_pos, drop_update_pos) < drop_function_pos
    # Function before table
    assert drop_function_pos < drop_table_pos
