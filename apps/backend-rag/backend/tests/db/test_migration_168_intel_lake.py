"""Tests for migration 168_intel_lake_schema.sql.

Contract:
  1. CREATE TABLE intel_items + intel_observations + intel_lake_audit_log
  2. routing_status CHECK constraint with 7 enum values
  3. trigger trg_notify_intel_lake_event AFTER INSERT only
  4. function notify_intel_lake_event INSERTs into events_outbox BEFORE pg_notify
  5. ROLLBACK marker present + drops in FK-correct order
  6. PG_CHANNEL_MAP must register intel_lake_event
"""

import re
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "db" / "migrations_v2" / "168_intel_lake_schema.sql"
)


@pytest.fixture(scope="module")
def migration_text() -> str:
    assert MIGRATION_PATH.exists(), f"missing: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text()


@pytest.fixture(scope="module")
def forward_section(migration_text: str) -> str:
    parts = migration_text.split("-- === ROLLBACK ===")
    return parts[0]


@pytest.fixture(scope="module")
def rollback_section(migration_text: str) -> str:
    parts = migration_text.split("-- === ROLLBACK ===")
    assert len(parts) == 2, "missing -- === ROLLBACK === marker"
    return parts[1]


def test_creates_three_tables(forward_section: str) -> None:
    for table in ("intel_items", "intel_observations", "intel_lake_audit_log"):
        assert re.search(
            rf"CREATE TABLE IF NOT EXISTS {table}\b", forward_section, re.IGNORECASE
        ), f"missing CREATE TABLE {table}"


def test_routing_status_check_constraint(forward_section: str) -> None:
    """routing_status must accept exactly 7 enum values."""
    enum_values = {"unrouted", "blog", "wr2", "nb-intel", "archive", "skip", "needs_review"}
    for val in enum_values:
        assert f"'{val}'" in forward_section, f"missing routing_status value: {val}"


def test_canonical_url_unique(forward_section: str) -> None:
    assert re.search(r"canonical_url\s+TEXT\s+UNIQUE", forward_section, re.IGNORECASE)


def test_observations_fk_cascade(forward_section: str) -> None:
    assert re.search(
        r"item_id\s+UUID\s+NOT NULL\s+REFERENCES\s+intel_items\(id\)\s+ON DELETE CASCADE",
        forward_section,
        re.IGNORECASE,
    )


def test_trigger_only_on_insert(forward_section: str) -> None:
    """Critical: trigger must NOT fire on UPDATE (last_seen_at refresh)."""
    trigger_match = re.search(
        r"CREATE TRIGGER trg_notify_intel_lake_event\s+AFTER\s+(\w+)\s+ON\s+intel_items",
        forward_section,
        re.IGNORECASE,
    )
    assert trigger_match, "missing trigger trg_notify_intel_lake_event"
    assert trigger_match.group(1).upper() == "INSERT", (
        "trigger MUST be AFTER INSERT only — UPDATEs of last_seen_at should not fire"
    )


def test_outbox_pattern_insert_before_notify(forward_section: str) -> None:
    """Mig 146 contract: INSERT events_outbox before pg_notify, both in same tx."""
    func_start = forward_section.find("CREATE OR REPLACE FUNCTION notify_intel_lake_event")
    assert func_start != -1, "missing notify_intel_lake_event function"
    func_body = forward_section[func_start : func_start + 2000]

    insert_pos = func_body.find("INSERT INTO events_outbox")
    notify_pos = func_body.find("pg_notify(")
    assert insert_pos != -1, "function must INSERT INTO events_outbox"
    assert notify_pos != -1, "function must call pg_notify"
    assert insert_pos < notify_pos, (
        "events_outbox INSERT must precede pg_notify per migration 146 outbox contract"
    )


def test_outbox_id_injected_into_payload(forward_section: str) -> None:
    """_outbox_id must be injected into pg_notify payload for consumer ack."""
    assert "_outbox_id" in forward_section, (
        "pg_notify payload must include _outbox_id for outbox replay ack"
    )


def test_rollback_marker_present(migration_text: str) -> None:
    assert "-- === ROLLBACK ===" in migration_text


def test_rollback_drops_in_fk_correct_order(rollback_section: str) -> None:
    """intel_observations FKs intel_items, so it must drop first."""
    obs_pos = rollback_section.find("DROP TABLE IF EXISTS intel_observations")
    items_pos = rollback_section.find("DROP TABLE IF EXISTS intel_items")
    assert obs_pos != -1 and items_pos != -1
    assert obs_pos < items_pos, (
        "rollback must drop intel_observations (FK side) before intel_items (PK side)"
    )


def test_rollback_drops_trigger_and_function(rollback_section: str) -> None:
    assert re.search(
        r"DROP TRIGGER IF EXISTS trg_notify_intel_lake_event", rollback_section, re.IGNORECASE
    )
    assert re.search(
        r"DROP FUNCTION IF EXISTS notify_intel_lake_event", rollback_section, re.IGNORECASE
    )


def test_pg_channel_map_registers_intel_lake_event() -> None:
    """The Python-side PG_CHANNEL_MAP must include intel_lake_event so the
    EventBus listener picks up the new channel and the events_outbox replay
    can dispatch to in-process handlers."""
    from backend.services.events.event_bus import PG_CHANNEL_MAP

    assert "intel_lake_event" in PG_CHANNEL_MAP, (
        "PG_CHANNEL_MAP must register intel_lake_event → intel_lake.event "
        "per migration 168 contract"
    )
