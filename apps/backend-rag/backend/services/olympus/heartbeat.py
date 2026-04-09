"""Olympus DB Guardian — Heartbeat Rhythm.

Collects database metrics, evaluates alert conditions, and persists snapshots.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import asyncpg

from backend.services.olympus.models import HeartbeatSnapshot

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.heartbeat")

# Type alias for alert callbacks
AlertCallback = Callable[[str], Awaitable[None]]


class Heartbeat:
    """Collect DB metrics, evaluate alerts, and persist heartbeat snapshots."""

    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self._pool = db_pool
        self._rules = rules
        self._alert_callbacks: list[AlertCallback] = []

    def on_alert(self, callback: AlertCallback) -> None:
        """Register a callback to be invoked on each alert."""
        self._alert_callbacks.append(callback)

    async def alert(self, message: str) -> None:
        """Invoke all registered alert callbacks with *message*."""
        logger.warning("ALERT: %s", message)
        for cb in self._alert_callbacks:
            await cb(message)

    # ------------------------------------------------------------------
    # Metrics collection
    # ------------------------------------------------------------------

    async def collect_metrics(self) -> HeartbeatSnapshot:
        """Query Postgres for connection, bloat, query, and lock metrics."""
        pool_size: int = self._pool.get_size()
        pool_idle: int = self._pool.get_idle_size()

        async with self._pool.acquire() as conn:
            active_connections = await self._count_active_connections(conn)
            max_connections = await self._get_max_connections(conn)
            db_size_bytes = await self._get_db_size(conn)
            bloat_top3 = await self._get_bloat_top3(conn)

            long_query_threshold: int = self._rules.get_threshold(
                "long_query_seconds", default=30,
            )
            long_queries = await self._count_long_queries(conn, long_query_threshold)
            lock_waits = await self._count_lock_waits(conn)

        snapshot = HeartbeatSnapshot(
            pool_size=pool_size,
            pool_idle=pool_idle,
            active_connections=active_connections,
            max_connections=max_connections,
            db_size_bytes=db_size_bytes,
            bloat_top3=bloat_top3,
            long_queries=long_queries,
            lock_waits=lock_waits,
        )
        logger.info(
            "Heartbeat collected: pool=%d/%d active=%d/%d bloat=%d long=%d locks=%d",
            pool_size - pool_idle,
            pool_size,
            active_connections,
            max_connections,
            len(bloat_top3),
            long_queries,
            lock_waits,
        )
        return snapshot

    # ------------------------------------------------------------------
    # Alert evaluation
    # ------------------------------------------------------------------

    async def check_alerts(self, snapshot: HeartbeatSnapshot) -> list[str]:
        """Evaluate thresholds and fire alerts. Returns list of messages sent."""
        messages: list[str] = []

        pool_alert_pct: float = self._rules.get_threshold(
            "pool_alert_pct", default=80,
        )
        if snapshot.pool_utilization > pool_alert_pct / 100:
            msg = (
                f"Pool utilization {snapshot.pool_utilization:.0%} "
                f"exceeds threshold {pool_alert_pct:.0f}%"
            )
            await self.alert(msg)
            messages.append(msg)

        connection_alert_pct: float = self._rules.get_threshold(
            "connection_alert_pct", default=80,
        )
        if snapshot.max_connections > 0:
            conn_ratio = snapshot.active_connections / snapshot.max_connections
            if conn_ratio > connection_alert_pct / 100:
                msg = (
                    f"Connection ratio {conn_ratio:.0%} "
                    f"exceeds threshold {connection_alert_pct:.0f}%"
                )
                await self.alert(msg)
                messages.append(msg)

        if snapshot.long_queries > 0:
            msg = f"{snapshot.long_queries} long-running queries detected"
            await self.alert(msg)
            messages.append(msg)

        snapshot.alerts_sent = len(messages)
        return messages

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def persist(self, snapshot: HeartbeatSnapshot) -> None:
        """INSERT the snapshot into olympus_heartbeats."""
        query = """
            INSERT INTO olympus_heartbeats (
                pool_size, pool_idle, active_connections, max_connections,
                db_size_bytes, bloat_top3, long_queries, lock_waits,
                alerts_sent, recorded_at, pool_utilization
            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                snapshot.pool_size,
                snapshot.pool_idle,
                snapshot.active_connections,
                snapshot.max_connections,
                snapshot.db_size_bytes,
                snapshot.bloat_top3,
                snapshot.long_queries,
                snapshot.lock_waits,
                snapshot.alerts_sent,
                snapshot.recorded_at,
                snapshot.pool_utilization,
            )
        logger.info("Heartbeat persisted at %s", snapshot.recorded_at.isoformat())

    # ------------------------------------------------------------------
    # Private helpers — individual SQL queries
    # ------------------------------------------------------------------

    @staticmethod
    async def _count_active_connections(conn: asyncpg.Connection) -> int:
        """Count non-idle connections from pg_stat_activity."""
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_stat_activity WHERE state != 'idle'",
        )
        return int(row["cnt"]) if row else 0

    @staticmethod
    async def _get_max_connections(conn: asyncpg.Connection) -> int:
        """Read server max_connections from SHOW."""
        row = await conn.fetchrow("SHOW max_connections")
        return int(row["max_connections"]) if row else 100

    @staticmethod
    async def _get_db_size(conn: asyncpg.Connection) -> int:
        """Return current database size in bytes."""
        row = await conn.fetchrow(
            "SELECT pg_database_size(current_database()) AS size",
        )
        return int(row["size"]) if row else 0

    @staticmethod
    async def _get_bloat_top3(conn: asyncpg.Connection) -> list[dict[str, Any]]:
        """Top 3 tables by dead tuples (only those with > 1000 dead rows)."""
        rows = await conn.fetch(
            """
            SELECT relname, n_dead_tup, n_live_tup
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000
            ORDER BY n_dead_tup DESC
            LIMIT 3
            """,
        )
        return [
            {
                "table": r["relname"],
                "dead_tuples": r["n_dead_tup"],
                "live_tuples": r["n_live_tup"],
            }
            for r in rows
        ]

    @staticmethod
    async def _count_long_queries(
        conn: asyncpg.Connection,
        threshold_seconds: int,
    ) -> int:
        """Count queries running longer than *threshold_seconds*."""
        row = await conn.fetchrow(
            """
            SELECT count(*) AS cnt
            FROM pg_stat_activity
            WHERE state = 'active'
              AND query_start < now() - make_interval(secs => $1)
            """,
            threshold_seconds,
        )
        return int(row["cnt"]) if row else 0

    @staticmethod
    async def _count_lock_waits(conn: asyncpg.Connection) -> int:
        """Count blocked locks from pg_locks."""
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_locks WHERE NOT granted",
        )
        return int(row["cnt"]) if row else 0
