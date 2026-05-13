"""Intel Lake producer-side outbox (Wave 1).

Each producer (intel_radar, imigrasi_monitor, ...) writes observations to a
local SQLite outbox in their own transaction. A separate cron worker
(`intel-lake-outbox-drain.py`) reads the outbox and POSTs to the Fly
backend `/api/intel/lake/observations:batch` endpoint.

This decouples producer success from backend availability:
- Producer never fails because backend is down
- Outbox row persists across reboots
- Drain worker retries with exponential backoff

Schema is intentionally tiny — no indexes beyond the obvious because
volume is low (~100-1000 rows/day, drained every 60s).

Design: research/symbiosis/2026-05-12-intel-lake-design.md
Plan:   research/symbiosis/2026-05-12-intel-lake-wave1-plan.md
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

OUTBOX_PATH = Path.home() / ".intel-lake-outbox.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS intel_lake_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producer_name TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    enqueued_at TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON intel_lake_outbox(id) WHERE delivered_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_outbox_stale
    ON intel_lake_outbox(enqueued_at) WHERE delivered_at IS NULL AND attempts >= 10;
"""


def _connect() -> sqlite3.Connection:
    OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(OUTBOX_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.executescript(_SCHEMA)
    return conn


def enqueue(producer_name: str, payload: dict[str, Any]) -> int:
    """Append a payload to the outbox. Returns row id.

    Best-effort: producer SHOULD NOT fail if outbox is unreachable. Caller
    catches exceptions; this function raises on truly broken disk only.
    """
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO intel_lake_outbox (producer_name, payload_json) VALUES (?, ?)",
            (producer_name, json.dumps(payload, default=str)),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def fetch_pending(limit: int = 100) -> list[tuple[int, str, str]]:
    """Returns up to `limit` undelivered rows as (id, producer_name, payload_json).

    Drain worker uses this. Sort by id ASC for fairness.
    """
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT id, producer_name, payload_json
              FROM intel_lake_outbox
             WHERE delivered_at IS NULL AND attempts < 10
             ORDER BY id ASC
             LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def mark_delivered(ids: list[int]) -> None:
    """Mark rows as delivered. Idempotent."""
    if not ids:
        return
    conn = _connect()
    try:
        conn.executemany(
            "UPDATE intel_lake_outbox SET delivered_at = datetime('now') WHERE id = ?",
            [(i,) for i in ids],
        )
        conn.commit()
    finally:
        conn.close()


def mark_failed(id_: int, error_message: str) -> None:
    """Increment attempts + record error. After 10 attempts row is left for manual review."""
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE intel_lake_outbox
               SET attempts = attempts + 1,
                   last_error = ?
             WHERE id = ?
            """,
            (error_message[:500], id_),
        )
        conn.commit()
    finally:
        conn.close()


def stats() -> dict[str, int]:
    """Return outbox counts: pending, delivered, abandoned."""
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT
                SUM(CASE WHEN delivered_at IS NULL AND attempts < 10 THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) AS delivered,
                SUM(CASE WHEN delivered_at IS NULL AND attempts >= 10 THEN 1 ELSE 0 END) AS abandoned
              FROM intel_lake_outbox
            """
        )
        row = cur.fetchone()
        return {
            "pending": row[0] or 0,
            "delivered": row[1] or 0,
            "abandoned": row[2] or 0,
        }
    finally:
        conn.close()
