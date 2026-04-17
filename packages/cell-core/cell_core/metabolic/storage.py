"""MetabolicStore — SQLite persistence for metabolic snapshots.

Follows the Genome class pattern exactly: WAL mode, threading.Lock for writes,
per-thread connections via threading.local().

# Organo: cell-core (L0) metabolic module
# Produce: persistent snapshots (queryable SQLite)
# Consuma: MetabolicSnapshot from collector
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from cell_core.metabolic.definitions import (
    METRIC_AUTONOMY_INDEX,
    METRIC_ESCALATION_FREQ,
    METRIC_ONTOLOGY_DENSITY,
    METRIC_TTR,
    MetabolicSnapshot,
    MetricValue,
)

logger = logging.getLogger("cell_core.metabolic.storage")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metabolic_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calculated_at TEXT NOT NULL,
    ttr_value REAL,
    ttr_metadata TEXT,
    do_value REAL,
    do_metadata TEXT,
    ia_value REAL,
    ia_metadata TEXT,
    fe_value REAL,
    fe_metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_metabolic_at ON metabolic_snapshots(calculated_at DESC);
"""


class MetabolicStore:
    """SQLite store for metabolic snapshots. Thread-safe via Lock + WAL.

    Usage:
        store = MetabolicStore(db_path="~/.agent/decisions/organism_metrics.db")
        store.store(snapshot)
        latest = store.latest(n=1)
    """

    def __init__(self, db_path: str = "organism_metrics.db") -> None:
        self._db_path = os.path.expanduser(db_path)
        self._write_lock = threading.Lock()
        self._local = threading.local()

        # Ensure parent directory exists
        parent = Path(self._db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a per-thread connection (reused across calls)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        """Idempotent schema init + v2 migration (collector_host + metric_scope).

        Serializes DDL via threading.Lock + BEGIN IMMEDIATE to avoid race when
        two processes (cron + manual run) open the store concurrently.
        """
        with self._write_lock:
            conn = self._get_conn()
            conn.executescript(_SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            try:
                cols = {row[1] for row in conn.execute("PRAGMA table_info(metabolic_snapshots)")}
                if "collector_host" not in cols:
                    conn.execute("ALTER TABLE metabolic_snapshots ADD COLUMN collector_host TEXT")
                if "metric_scope" not in cols:
                    conn.execute("ALTER TABLE metabolic_snapshots ADD COLUMN metric_scope TEXT")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_metabolic_collector_scope "
                    "ON metabolic_snapshots(collector_host, metric_scope, calculated_at DESC)"
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def store(
        self,
        snapshot: MetabolicSnapshot,
        collector_host: str | None = None,
        metric_scope: str | None = None,
    ) -> int:
        """Persist a snapshot. Returns the row id.

        v2 schema adds collector_host ('pro'|'air') and metric_scope ('global'|'host').
        Kept Optional to preserve backwards-compat with legacy callers and tests;
        production rollup should always pass both.
        """
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """INSERT INTO metabolic_snapshots
                   (calculated_at, ttr_value, ttr_metadata,
                    do_value, do_metadata, ia_value, ia_metadata,
                    fe_value, fe_metadata,
                    collector_host, metric_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.calculated_at,
                    snapshot.ttr.value,
                    json.dumps(snapshot.ttr.metadata),
                    snapshot.ontology_density.value,
                    json.dumps(snapshot.ontology_density.metadata),
                    snapshot.autonomy_index.value,
                    json.dumps(snapshot.autonomy_index.metadata),
                    snapshot.escalation_freq.value,
                    json.dumps(snapshot.escalation_freq.metadata),
                    collector_host,
                    metric_scope,
                ),
            )
            conn.commit()
            rowid = cursor.lastrowid
            logger.info(
                f"[metabolic] stored snapshot at {snapshot.calculated_at} "
                f"(id={rowid}, collector={collector_host}, scope={metric_scope})"
            )
            return rowid

    def latest(self, n: int = 1) -> list[MetabolicSnapshot]:
        """Retrieve the N most recent snapshots, newest first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM metabolic_snapshots ORDER BY calculated_at DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def range(self, since: str, until: str) -> list[MetabolicSnapshot]:
        """Retrieve snapshots in a date range (inclusive), oldest first."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM metabolic_snapshots
               WHERE calculated_at >= ? AND calculated_at <= ?
               ORDER BY calculated_at ASC""",
            (since, until),
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def metric_series(self, metric_type: str, n: int = 30) -> list[tuple[str, float | None]]:
        """Return (calculated_at, value) pairs for a single metric, newest first."""
        col_map = {
            METRIC_TTR: "ttr_value",
            METRIC_ONTOLOGY_DENSITY: "do_value",
            METRIC_AUTONOMY_INDEX: "ia_value",
            METRIC_ESCALATION_FREQ: "fe_value",
        }
        col = col_map.get(metric_type)
        if not col:
            return []
        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT calculated_at, {col} FROM metabolic_snapshots ORDER BY calculated_at DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [(r["calculated_at"], r[col]) for r in rows]

    def stats(self) -> dict:
        """Summary statistics for monitoring."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM metabolic_snapshots").fetchone()[0]
        first = conn.execute(
            "SELECT calculated_at FROM metabolic_snapshots ORDER BY calculated_at ASC LIMIT 1"
        ).fetchone()
        last = conn.execute(
            "SELECT calculated_at FROM metabolic_snapshots ORDER BY calculated_at DESC LIMIT 1"
        ).fetchone()

        db_size = 0
        try:
            db_size = os.path.getsize(self._db_path)
        except OSError:
            pass

        return {
            "total_snapshots": total,
            "first_snapshot": first["calculated_at"] if first else None,
            "last_snapshot": last["calculated_at"] if last else None,
            "db_file_size": db_size,
        }

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> MetabolicSnapshot:
        """Convert a DB row to a MetabolicSnapshot."""
        now_str = row["calculated_at"]
        return MetabolicSnapshot(
            ttr=MetricValue(
                metric_type=METRIC_TTR,
                value=row["ttr_value"],
                calculated_at=now_str,
                metadata=json.loads(row["ttr_metadata"]) if row["ttr_metadata"] else {},
            ),
            ontology_density=MetricValue(
                metric_type=METRIC_ONTOLOGY_DENSITY,
                value=row["do_value"],
                calculated_at=now_str,
                metadata=json.loads(row["do_metadata"]) if row["do_metadata"] else {},
            ),
            autonomy_index=MetricValue(
                metric_type=METRIC_AUTONOMY_INDEX,
                value=row["ia_value"],
                calculated_at=now_str,
                metadata=json.loads(row["ia_metadata"]) if row["ia_metadata"] else {},
            ),
            escalation_freq=MetricValue(
                metric_type=METRIC_ESCALATION_FREQ,
                value=row["fe_value"],
                calculated_at=now_str,
                metadata=json.loads(row["fe_metadata"]) if row["fe_metadata"] else {},
            ),
            calculated_at=now_str,
        )
