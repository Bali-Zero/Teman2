"""SQLite persistence layer for nb_monitor.

Schema versioning: v1 = initial. PRAGMA journal_mode=WAL for safe
concurrent reads while a daily writer is appending.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MetricRow:
    uuid: str
    ts_capture: int
    tier: str
    read_freq_7d: int | None
    read_freq_30d: int | None
    skill_derivation_count: int | None
    downstream_cite_rate: float | None
    source_freshness_age_days: int | None
    push_success_rate: float | None
    instrumentation_status: str


@dataclass(frozen=True)
class AlertRecord:
    uuid: str
    condition: str
    sent_at: int
    payload: str | None = None


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with WAL + FK pragmas applied."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and record schema version. Idempotent."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nb_metrics (
            uuid                       TEXT NOT NULL,
            ts_capture                 INTEGER NOT NULL,
            tier                       TEXT NOT NULL,
            read_freq_7d               INTEGER,
            read_freq_30d              INTEGER,
            skill_derivation_count     INTEGER,
            downstream_cite_rate       REAL,
            source_freshness_age_days  INTEGER,
            push_success_rate          REAL,
            instrumentation_status     TEXT,
            PRIMARY KEY (uuid, ts_capture)
        );
        CREATE INDEX IF NOT EXISTS idx_uuid_ts ON nb_metrics(uuid, ts_capture DESC);
        CREATE INDEX IF NOT EXISTS idx_ts_capture ON nb_metrics(ts_capture DESC);

        CREATE TABLE IF NOT EXISTS alerts_sent (
            uuid       TEXT NOT NULL,
            condition  TEXT NOT NULL,
            sent_at    INTEGER NOT NULL,
            payload    TEXT,
            PRIMARY KEY (uuid, condition, sent_at)
        );
        CREATE INDEX IF NOT EXISTS idx_alert_lookup
          ON alerts_sent(uuid, condition, sent_at DESC);
        """
    )
    existing = conn.execute(
        "SELECT version FROM schema_version WHERE version=?",
        (CURRENT_SCHEMA_VERSION,),
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (CURRENT_SCHEMA_VERSION, int(time.time())),
        )
    conn.commit()


def insert_metric_row(conn: sqlite3.Connection, row: MetricRow) -> None:
    conn.execute(
        """
        INSERT INTO nb_metrics (
            uuid, ts_capture, tier, read_freq_7d, read_freq_30d,
            skill_derivation_count, downstream_cite_rate,
            source_freshness_age_days, push_success_rate, instrumentation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.uuid,
            row.ts_capture,
            row.tier,
            row.read_freq_7d,
            row.read_freq_30d,
            row.skill_derivation_count,
            row.downstream_cite_rate,
            row.source_freshness_age_days,
            row.push_success_rate,
            row.instrumentation_status,
        ),
    )
    conn.commit()


def insert_alert_record(conn: sqlite3.Connection, record: AlertRecord) -> None:
    conn.execute(
        """
        INSERT INTO alerts_sent (uuid, condition, sent_at, payload)
        VALUES (?, ?, ?, ?)
        """,
        (record.uuid, record.condition, record.sent_at, record.payload),
    )
    conn.commit()


def fetch_latest_per_uuid(conn: sqlite3.Connection, uuid: str) -> MetricRow | None:
    cursor = conn.execute(
        """
        SELECT uuid, ts_capture, tier, read_freq_7d, read_freq_30d,
               skill_derivation_count, downstream_cite_rate,
               source_freshness_age_days, push_success_rate, instrumentation_status
          FROM nb_metrics
         WHERE uuid=?
         ORDER BY ts_capture DESC
         LIMIT 1
        """,
        (uuid,),
    )
    r = cursor.fetchone()
    if r is None:
        return None
    return MetricRow(*r)


def fetch_alert_last_sent(
    conn: sqlite3.Connection, uuid: str, condition: str
) -> int | None:
    r = conn.execute(
        "SELECT MAX(sent_at) FROM alerts_sent WHERE uuid=? AND condition=?",
        (uuid, condition),
    ).fetchone()
    return r[0] if r and r[0] is not None else None
