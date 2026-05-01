from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pulse_events (
    outbox_id INTEGER PRIMARY KEY,
    cell_id TEXT NOT NULL, cell_kind TEXT NOT NULL,
    pulse_id TEXT NOT NULL, pulse_timestamp INTEGER NOT NULL,
    phase TEXT NOT NULL, classifier_self TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    received_at INTEGER NOT NULL, received_lag_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pulse_events_cell_ts ON pulse_events(cell_id, pulse_timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_pulse_events_classifier ON pulse_events(classifier_self, pulse_timestamp DESC);

CREATE TABLE IF NOT EXISTS pulse_classifications (
    outbox_id INTEGER PRIMARY KEY REFERENCES pulse_events(outbox_id),
    classified_at INTEGER NOT NULL,
    label TEXT NOT NULL, confidence REAL NOT NULL,
    reasoning TEXT, label_diff TEXT,
    model TEXT NOT NULL, model_version TEXT,
    cost_usd REAL NOT NULL, latency_ms INTEGER NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_classifications_label ON pulse_classifications(label, classified_at DESC);
CREATE INDEX IF NOT EXISTS ix_classifications_disagree ON pulse_classifications(label, outbox_id) WHERE label_diff='disagree';

CREATE TABLE IF NOT EXISTS pulse_daily_rollup (
    day TEXT NOT NULL, cell_id TEXT NOT NULL,
    n_pulse INTEGER NOT NULL, n_self_green INTEGER NOT NULL,
    n_self_yellow INTEGER NOT NULL, n_self_red INTEGER NOT NULL,
    n_classified INTEGER NOT NULL, n_anomaly INTEGER NOT NULL,
    n_critical INTEGER NOT NULL, n_disagree INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    PRIMARY KEY (day, cell_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS pulse_classifications_fts USING fts5(
    outbox_id UNINDEXED, label, reasoning,
    content='pulse_classifications', content_rowid='outbox_id'
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL
);
INSERT OR IGNORE INTO schema_version VALUES (1, strftime('%s','now')*1000);
"""


def _to_epoch_ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        assert self._conn is not None
        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def insert_pulse_event(self, payload: dict[str, Any]) -> bool:
        """Idempotent insert. Returns True if inserted, False if outbox_id already present."""
        assert self._conn is not None
        ts_ms = _to_epoch_ms(payload["pulse_timestamp"])
        now = _now_ms()
        cursor = await self._conn.execute(
            "INSERT OR IGNORE INTO pulse_events "
            "(outbox_id, cell_id, cell_kind, pulse_id, pulse_timestamp, phase, "
            " classifier_self, payload_json, received_at, received_lag_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                payload["outbox_id"], payload["cell_id"], payload["cell_kind"],
                payload["pulse_id"], ts_ms, payload["phase"],
                payload["pulse_result"].get("classifier_self", "unknown"),
                json.dumps(payload),
                now, max(0, now - ts_ms),
            ),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def upsert_classification(self, c: dict[str, Any]) -> None:
        """A1 fix: ON CONFLICT DO UPDATE so backfill can re-classify."""
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO pulse_classifications "
            "(outbox_id, classified_at, label, confidence, reasoning, label_diff, "
            " model, model_version, cost_usd, latency_ms, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(outbox_id) DO UPDATE SET "
            "classified_at=excluded.classified_at, label=excluded.label, "
            "confidence=excluded.confidence, reasoning=excluded.reasoning, "
            "label_diff=excluded.label_diff, model=excluded.model, "
            "model_version=excluded.model_version, cost_usd=excluded.cost_usd, "
            "latency_ms=excluded.latency_ms, error=excluded.error",
            (
                c["outbox_id"], _now_ms(), c["label"], c["confidence"],
                c["reasoning"], c["label_diff"], c["model"], c["model_version"],
                c["cost_usd"], c["latency_ms"], c["error"],
            ),
        )
        await self._conn.commit()
