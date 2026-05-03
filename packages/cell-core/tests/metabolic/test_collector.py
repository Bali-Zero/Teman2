"""Tests for MetabolicCollector — reads data sources, computes metrics."""
import json
import os
import sqlite3
import time

import pytest

from cell_core.metabolic.collector import MetabolicCollector, _extract_episodes, _parse_timestamp
from cell_core.metabolic.definitions import (
    METRIC_AUTONOMY_INDEX,
    METRIC_ESCALATION_FREQ,
    METRIC_ONTOLOGY_DENSITY,
    METRIC_TTR,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_cron_jsonl(path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _write_escalation_jsonl(path: str, entries: list[dict]) -> None:
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _create_mos_db(path: str, session_count: int) -> None:
    """Create a minimal MOS sessions table with N sessions in the last hour."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            machine TEXT,
            project TEXT,
            branch TEXT
        )
    """)
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    for i in range(session_count):
        ts = (now - timedelta(minutes=i * 5)).isoformat()
        conn.execute("INSERT INTO sessions (started_at, machine, project, branch) VALUES (?, ?, ?, ?)",
                     (ts, "test", "test_project", "main"))
    conn.commit()
    conn.close()


# ── TTR episode extraction (pure function) ──────────────────────────────────

def test_extract_episodes_simple():
    statuses = ["green", "yellow", "red", "green", "red", "green"]
    assert _extract_episodes(statuses) == [2, 1]


def test_extract_episodes_no_degraded():
    statuses = ["green", "green", "green"]
    assert _extract_episodes(statuses) == []


def test_extract_episodes_all_degraded():
    statuses = ["yellow", "red", "yellow", "red"]
    assert _extract_episodes(statuses) == [4]


def test_extract_episodes_ends_non_green():
    statuses = ["green", "yellow", "red"]
    assert _extract_episodes(statuses) == [2]


def test_extract_episodes_multiple():
    statuses = ["green", "yellow", "green", "red", "red", "green", "yellow", "green"]
    assert _extract_episodes(statuses) == [1, 2, 1]


# ── Timestamp parsing ───────────────────────────────────────────────────────

def test_parse_timestamp_iso():
    ts = _parse_timestamp("2026-04-16T12:00:00+00:00")
    assert ts is not None
    assert ts > 0


def test_parse_timestamp_unix_float():
    assert _parse_timestamp(1713261600.0) == 1713261600.0


def test_parse_timestamp_unix_string():
    assert _parse_timestamp("1713261600") == 1713261600.0


def test_parse_timestamp_empty():
    assert _parse_timestamp("") is None
    assert _parse_timestamp(None) is None


# ── M3: Autonomy Index (file-based, no PG) ─────────────────────────────────

def test_collect_ia_from_files(tmp_path):
    """IA computed from cron JSONL + MOS sessions."""
    cron_dir = str(tmp_path / "cron")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    _write_cron_jsonl(
        os.path.join(cron_dir, "test.jsonl"),
        [
            {"job": "sentinel", "status": "ok", "ts": now_iso},
            {"job": "backup", "status": "ok", "ts": now_iso},
            {"job": "failed_job", "status": "failed", "ts": now_iso},  # not counted
        ],
    )

    mos_path = str(tmp_path / "memory.db")
    _create_mos_db(mos_path, session_count=5)

    collector = MetabolicCollector(
        cron_log_dir=cron_dir,
        escalation_path=str(tmp_path / "empty.jsonl"),
        mos_db_path=mos_path,
        pg_dsn=None,
    )
    snap = collector.collect()
    ia = snap.autonomy_index
    assert ia.value is not None
    # 2 cron ok / (2 cron + 5 sessions) = 2/7 ≈ 0.2857
    assert abs(ia.value - 2.0 / 7.0) < 0.01
    assert ia.metadata["endogenous"]["cron"] == 2
    assert ia.metadata["exogenous"]["sessions"] == 5


def test_collect_ia_zero_exogenous(tmp_path):
    """All endogenous = IA 1.0."""
    cron_dir = str(tmp_path / "cron")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    _write_cron_jsonl(
        os.path.join(cron_dir, "test.jsonl"),
        [{"job": "j1", "status": "ok", "ts": now_iso}] * 10,
    )
    # No MOS DB = 0 sessions
    collector = MetabolicCollector(
        cron_log_dir=cron_dir,
        escalation_path=str(tmp_path / "empty.jsonl"),
        mos_db_path=str(tmp_path / "nonexistent.db"),
        pg_dsn=None,
    )
    snap = collector.collect()
    assert snap.autonomy_index.value == 1.0


def test_collect_ia_zero_endogenous(tmp_path):
    """All exogenous = IA 0.0."""
    mos_path = str(tmp_path / "memory.db")
    _create_mos_db(mos_path, session_count=5)
    collector = MetabolicCollector(
        cron_log_dir=str(tmp_path / "empty_cron"),
        escalation_path=str(tmp_path / "empty.jsonl"),
        mos_db_path=mos_path,
        pg_dsn=None,
    )
    snap = collector.collect()
    assert snap.autonomy_index.value == 0.0


# ── M4: Escalation Frequency ───────────────────────────────────────────────

def test_collect_fe_from_file(tmp_path):
    """FE computed from escalation JSONL."""
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    esc_path = str(tmp_path / "escalations.jsonl")
    _write_escalation_jsonl(esc_path, [
        {"job": "j1", "ts": now_iso, "status": "pending"},
        {"job": "j2", "ts": now_iso, "status": "pending"},
        {"job": "j3", "ts": now_iso, "status": "pending"},
    ])

    cron_dir = str(tmp_path / "cron")
    _write_cron_jsonl(
        os.path.join(cron_dir, "test.jsonl"),
        [{"job": "ok_job", "status": "ok", "ts": now_iso}] * 7,
    )
    mos_path = str(tmp_path / "memory.db")
    _create_mos_db(mos_path, session_count=3)

    collector = MetabolicCollector(
        cron_log_dir=cron_dir,
        escalation_path=esc_path,
        mos_db_path=mos_path,
        pg_dsn=None,
    )
    snap = collector.collect()
    fe = snap.escalation_freq
    assert fe.value is not None
    # 3 escalations / 10 total actions = 0.3
    assert abs(fe.value - 0.3) < 0.01
    assert fe.metadata["raw_count"] == 3


def test_collect_fe_empty_file(tmp_path):
    """No escalations = FE 0.0."""
    collector = MetabolicCollector(
        cron_log_dir=str(tmp_path / "empty_cron"),
        escalation_path=str(tmp_path / "nonexistent.jsonl"),
        mos_db_path=str(tmp_path / "nonexistent.db"),
        pg_dsn=None,
    )
    snap = collector.collect()
    assert snap.escalation_freq.value == 0.0


# ── M1/M2: PG-dependent (graceful degradation) ────────────────────────────

def test_collect_ttr_pg_unavailable(tmp_path):
    """TTR returns None when pg_dsn is None."""
    collector = MetabolicCollector(
        cron_log_dir=str(tmp_path),
        escalation_path=str(tmp_path / "e.jsonl"),
        mos_db_path=str(tmp_path / "m.db"),
        pg_dsn=None,
    )
    snap = collector.collect()
    assert snap.ttr.value is None
    assert "pg_dsn_not_configured" in str(snap.ttr.metadata)


def test_collect_do_pg_unavailable(tmp_path):
    """DO returns None when pg_dsn is None."""
    collector = MetabolicCollector(
        cron_log_dir=str(tmp_path),
        escalation_path=str(tmp_path / "e.jsonl"),
        mos_db_path=str(tmp_path / "m.db"),
        pg_dsn=None,
    )
    snap = collector.collect()
    assert snap.ontology_density.value is None
    assert "pg_dsn_not_configured" in str(snap.ontology_density.metadata)


# ── Full snapshot ──────────────────────────────────────────────────────────

def test_collect_full_snapshot(tmp_path):
    """Full snapshot with all local sources, PG skipped."""
    cron_dir = str(tmp_path / "cron")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    _write_cron_jsonl(
        os.path.join(cron_dir, "test.jsonl"),
        [{"job": f"j{i}", "status": "ok", "ts": now_iso} for i in range(5)],
    )
    esc_path = str(tmp_path / "esc.jsonl")
    _write_escalation_jsonl(esc_path, [
        {"job": "e1", "ts": now_iso, "status": "pending"},
    ])
    mos_path = str(tmp_path / "memory.db")
    _create_mos_db(mos_path, session_count=3)

    collector = MetabolicCollector(
        cron_log_dir=cron_dir,
        escalation_path=esc_path,
        mos_db_path=mos_path,
        pg_dsn=None,
    )
    snap = collector.collect()

    # TTR and DO are None (no PG)
    assert snap.ttr.value is None
    assert snap.ontology_density.value is None

    # IA and FE computed from local files
    assert snap.autonomy_index.value is not None
    assert snap.escalation_freq.value is not None
    assert snap.calculated_at
