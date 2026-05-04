"""Verify migration 155 creates asset_provenance trigger — Sprint 3 W2.

Spec: docs/sprint3/mata-garuda-cell-design.md § "Trigger emission"
Depends: migration 154 (asset_provenance table)

The migration must:
  1. Create notify_asset_provenance() function dispatching by TG_OP.
  2. Attach AFTER INSERT OR UPDATE trigger on asset_provenance.
  3. Persist to events_outbox BEFORE pg_notify (mig 146 outbox pattern).
  4. Inject _outbox_id into the NOTIFY payload.
  5. Build payload including admiralty 2-axis (reliability/credibility),
     TLP, and the 3-column invalidation policy.
  6. Be idempotent on re-run.
  7. Have a -- === ROLLBACK === section.

Mirrors test_migration_152.py contract-test pattern.
"""
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "155_asset_provenance_trigger.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql


def test_migration_creates_notify_function():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE OR REPLACE FUNCTION notify_asset_provenance()" in forward_section


def test_migration_dispatches_on_tg_op():
    """event_type must derive from TG_OP, not be hardcoded."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "TG_OP = 'INSERT'" in forward_section
    assert "TG_OP = 'UPDATE'" in forward_section
    assert "'provenance_recorded'" in forward_section
    assert "'provenance_updated'" in forward_section


def test_migration_payload_includes_admiralty_axes():
    """M2 fields (reliability + credibility) MUST be in the NOTIFY payload —
    consumers (oracle citation guard, KG demotion) filter on these axes."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'reliability'" in forward_section
    assert "'credibility'" in forward_section
    assert "NEW.reliability" in forward_section
    assert "NEW.credibility" in forward_section


def test_migration_payload_includes_invalidation_columns():
    """X5: 3-column invalidation policy must be in the NOTIFY payload."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'valid_until'" in forward_section
    assert "'invalidation_event_topic'" in forward_section
    assert "'invalidation_mode'" in forward_section


def test_migration_payload_includes_tlp():
    """TLP propagated downstream — consumers can filter on distribution policy."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'tlp'" in forward_section
    assert "NEW.tlp" in forward_section


def test_migration_writes_to_outbox_before_notify():
    """Mig 146 contract: events_outbox INSERT before pg_notify, same tx."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    insert_pos = forward_section.find("INSERT INTO events_outbox")
    notify_pos = forward_section.find("pg_notify(")
    assert insert_pos != -1
    assert notify_pos != -1
    assert insert_pos < notify_pos


def test_migration_uses_asset_provenance_channel():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'asset_provenance'" in forward_section


def test_migration_injects_outbox_id_into_notify_payload():
    """Mig 146 contract: consumers must receive _outbox_id for idempotent ack."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'_outbox_id'" in forward_section
    assert "outbox_id" in forward_section


def test_migration_attaches_separate_insert_and_update_triggers():
    """v2.6: two separate triggers (INSERT + UPDATE), not one combined
    AFTER INSERT OR UPDATE — Postgres does not support TG_OP in
    CREATE TRIGGER WHEN clauses."""
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    # Two distinct trigger names
    assert "asset_provenance_notify_insert" in forward_section
    assert "asset_provenance_notify_update" in forward_section
    # Each on its own event
    assert "AFTER INSERT ON asset_provenance" in forward_section
    assert "AFTER UPDATE ON asset_provenance" in forward_section
    assert "FOR EACH ROW" in forward_section
    # Must NOT use TG_OP in WHEN (Postgres rejects)
    assert "WHEN (TG_OP" not in forward_section


def test_migration_update_trigger_filters_noop_updates():
    """Sprint 3 W2 review I1 fix: the UPDATE trigger MUST NOT fire on
    no-op UPDATEs (UPSERT with identical values). The WHEN clause
    uses OLD.* IS DISTINCT FROM NEW.* (Postgres NULL-safe row
    comparison) so idempotent re-tagging by the cell adapter doesn't
    generate spurious 'provenance_updated' events.

    v2.6: enforced on the UPDATE trigger only (INSERT trigger always
    fires; INSERT with no-op concept doesn't apply).
    """
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "WHEN (OLD.* IS DISTINCT FROM NEW.*)" in forward_section


def test_migration_is_idempotent():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE OR REPLACE FUNCTION" in forward_section
    # Drop both new split triggers AND legacy unified one
    assert "DROP TRIGGER IF EXISTS asset_provenance_notify_insert" in forward_section
    assert "DROP TRIGGER IF EXISTS asset_provenance_notify_update" in forward_section


def test_rollback_drops_triggers_then_function():
    """DROP FUNCTION fails if a trigger still depends on it (without CASCADE).

    v2.6: must drop both split triggers (insert + update) AND the
    legacy unified trigger before dropping the function.
    """
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    drop_insert_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS asset_provenance_notify_insert"
    )
    drop_update_pos = rollback_section.find(
        "DROP TRIGGER IF EXISTS asset_provenance_notify_update"
    )
    drop_function_pos = rollback_section.find(
        "DROP FUNCTION IF EXISTS notify_asset_provenance"
    )
    assert drop_insert_pos != -1
    assert drop_update_pos != -1
    assert drop_function_pos != -1
    assert max(drop_insert_pos, drop_update_pos) < drop_function_pos
