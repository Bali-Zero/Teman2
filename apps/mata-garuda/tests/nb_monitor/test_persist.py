"""Tests for nb_monitor.persist."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.persist import (
    MetricRow,
    AlertRecord,
    connect,
    ensure_schema,
    insert_metric_row,
    insert_alert_record,
    fetch_latest_per_uuid,
    fetch_alert_last_sent,
)


def _open(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    ensure_schema(conn)
    return conn


def test_ensure_schema_creates_tables(tmp_path):
    conn = _open(tmp_path / "m.db")
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [r[0] for r in cursor.fetchall()]
    assert "schema_version" in tables
    assert "nb_metrics" in tables
    assert "alerts_sent" in tables
    conn.close()


def test_ensure_schema_records_version(tmp_path):
    conn = _open(tmp_path / "m.db")
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 1
    conn.close()


def test_ensure_schema_is_idempotent(tmp_path):
    db = tmp_path / "m.db"
    conn1 = _open(db)
    conn1.close()
    conn2 = _open(db)
    rows = conn2.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert rows == 1
    conn2.close()


def test_wal_mode_enabled(tmp_path):
    conn = _open(tmp_path / "m.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    conn.close()


def test_foreign_keys_enabled(tmp_path):
    conn = _open(tmp_path / "m.db")
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    conn.close()


def test_insert_metric_row_round_trip(tmp_path):
    conn = _open(tmp_path / "m.db")
    row = MetricRow(
        uuid="u1",
        ts_capture=1700000000,
        tier="ALIVE",
        read_freq_7d=42,
        read_freq_30d=200,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=10,
        push_success_rate=0.99,
        instrumentation_status="ok",
    )
    insert_metric_row(conn, row)
    fetched = conn.execute(
        "SELECT uuid, tier, read_freq_7d, push_success_rate, instrumentation_status "
        "FROM nb_metrics WHERE uuid=?",
        ("u1",),
    ).fetchone()
    assert fetched == ("u1", "ALIVE", 42, 0.99, "ok")
    conn.close()


def test_insert_metric_row_handles_nulls(tmp_path):
    conn = _open(tmp_path / "m.db")
    row = MetricRow(
        uuid="u2",
        ts_capture=1700000001,
        tier="IDLE",
        read_freq_7d=None,
        read_freq_30d=None,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=None,
        push_success_rate=None,
        instrumentation_status="parse_failure",
    )
    insert_metric_row(conn, row)
    fetched = conn.execute(
        "SELECT read_freq_7d, push_success_rate FROM nb_metrics WHERE uuid=?",
        ("u2",),
    ).fetchone()
    assert fetched == (None, None)
    conn.close()


def test_fetch_latest_per_uuid_returns_most_recent(tmp_path):
    conn = _open(tmp_path / "m.db")
    for ts in [1700000000, 1700000100, 1700000050]:
        insert_metric_row(
            conn,
            MetricRow(
                uuid="u1",
                ts_capture=ts,
                tier="ALIVE",
                read_freq_7d=ts % 100,
                read_freq_30d=None,
                skill_derivation_count=None,
                downstream_cite_rate=None,
                source_freshness_age_days=None,
                push_success_rate=None,
                instrumentation_status="ok",
            ),
        )
    latest = fetch_latest_per_uuid(conn, "u1")
    assert latest is not None
    assert latest.ts_capture == 1700000100
    assert latest.read_freq_7d == 0
    conn.close()


def test_fetch_latest_per_uuid_returns_none_when_missing(tmp_path):
    conn = _open(tmp_path / "m.db")
    assert fetch_latest_per_uuid(conn, "missing") is None
    conn.close()


def test_insert_and_fetch_alert(tmp_path):
    conn = _open(tmp_path / "m.db")
    insert_alert_record(
        conn,
        AlertRecord(
            uuid="u1",
            condition="top5_drop_50pct",
            sent_at=1700000000,
            payload='{"prev":100,"now":40}',
        ),
    )
    last = fetch_alert_last_sent(conn, "u1", "top5_drop_50pct")
    assert last == 1700000000
    conn.close()


def test_fetch_alert_last_sent_returns_none_for_unknown(tmp_path):
    conn = _open(tmp_path / "m.db")
    assert fetch_alert_last_sent(conn, "u1", "top5_drop_50pct") is None
    conn.close()


def test_metric_row_primary_key_uuid_ts(tmp_path):
    """Inserting same (uuid, ts_capture) twice should raise IntegrityError."""
    conn = _open(tmp_path / "m.db")
    row = MetricRow(
        uuid="u1",
        ts_capture=1700000000,
        tier="ALIVE",
        read_freq_7d=1,
        read_freq_30d=None,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=None,
        push_success_rate=None,
        instrumentation_status="ok",
    )
    insert_metric_row(conn, row)
    with pytest.raises(sqlite3.IntegrityError):
        insert_metric_row(conn, row)
    conn.close()
