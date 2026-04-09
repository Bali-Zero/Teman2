"""Olympus v2 — Heartbeat Rhythm.

Collects database metrics, evaluates alert conditions, persists snapshots.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import asyncpg

from backend.services.olympus.models import HeartbeatSnapshot

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.heartbeat")

AlertCallback = Callable[[str], Awaitable[None]]


class Heartbeat:
    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self._pool = db_pool
        self._rules = rules
        self._alert_callbacks: list[AlertCallback] = []

    def on_alert(self, callback: AlertCallback) -> None:
        self._alert_callbacks.append(callback)

    async def alert(self, message: str) -> None:
        logger.warning("ALERT: %s", message)
        for cb in self._alert_callbacks:
            await cb(message)

    async def collect_metrics(self) -> HeartbeatSnapshot:
        pool_size: int = self._pool.get_size()
        pool_idle: int = self._pool.get_idle_size()

        async with self._pool.acquire() as conn:
            active_connections = await self._count_active_connections(conn)
            max_connections = await self._get_max_connections(conn)
            db_size_bytes = await self._get_db_size(conn)
            bloat_top3 = await self._get_bloat_top3(conn)

            # FIX BUG-3: rule key must be "long_query_threshold_seconds"
            long_query_threshold: int = self._rules.get_threshold(
                "long_query_threshold_seconds", default=30,
            )
            long_queries = await self._count_long_queries(conn, long_query_threshold)
            lock_waits = await self._count_lock_waits(conn)

            # v3 extended metrics
            cache_hit_ratio = await self._get_cache_hit_ratio(conn)
            top_tables = await self._get_top_tables_by_size(conn)
            idx_scan_ratio = await self._get_idx_scan_ratio(conn)
            dead_tuple_ratio = await self._get_dead_tuple_ratio(conn)

        snapshot = HeartbeatSnapshot(
            pool_size=pool_size,
            pool_idle=pool_idle,
            active_connections=active_connections,
            max_connections=max_connections,
            db_size_bytes=db_size_bytes,
            bloat_top3=bloat_top3,
            long_queries=long_queries,
            lock_waits=lock_waits,
            cache_hit_ratio=cache_hit_ratio,
            top_tables_by_size=top_tables,
            idx_scan_ratio=idx_scan_ratio,
        )
        snapshot.health_score = snapshot.compute_health_score(dead_tuple_ratio)
        logger.info(
            "Heartbeat: pool=%d/%d active=%d/%d long=%d locks=%d",
            pool_size - pool_idle, pool_size,
            active_connections, max_connections,
            long_queries, lock_waits,
        )
        return snapshot

    async def check_alerts(self, snapshot: HeartbeatSnapshot) -> list[str]:
        messages: list[str] = []

        pool_alert_pct: float = self._rules.get_threshold("pool_alert_pct", default=80)
        if snapshot.pool_utilization > pool_alert_pct / 100:
            msg = f"Pool utilization {snapshot.pool_utilization:.0%} exceeds {pool_alert_pct:.0f}%"
            await self.alert(msg)
            messages.append(msg)

        connection_alert_pct: float = self._rules.get_threshold("connection_alert_pct", default=80)
        if snapshot.max_connections > 0:
            conn_ratio = snapshot.active_connections / snapshot.max_connections
            if conn_ratio > connection_alert_pct / 100:
                msg = f"Connection ratio {conn_ratio:.0%} exceeds {connection_alert_pct:.0f}%"
                await self.alert(msg)
                messages.append(msg)

        if snapshot.long_queries > 0:
            msg = f"{snapshot.long_queries} long-running queries detected"
            await self.alert(msg)
            messages.append(msg)

        health_threshold: int = self._rules.get_threshold("health_score_alert_threshold", default=60)
        if snapshot.health_score is not None and snapshot.health_score < health_threshold:
            msg = f"Health score {snapshot.health_score} below threshold {health_threshold}"
            await self.alert(msg)
            messages.append(msg)

        snapshot.alerts_sent = len(messages)
        return messages

    async def persist(self, snapshot: HeartbeatSnapshot) -> None:
        import json
        query = """
            INSERT INTO olympus_heartbeats (
                pool_size, pool_idle, active_connections, max_connections,
                db_size_bytes, bloat_top3, long_queries, lock_waits,
                alerts_sent, recorded_at, pool_utilization,
                cache_hit_ratio, top_tables_by_size, idx_scan_ratio, health_score
            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13::jsonb, $14, $15)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                snapshot.pool_size, snapshot.pool_idle,
                snapshot.active_connections, snapshot.max_connections,
                snapshot.db_size_bytes, json.dumps(snapshot.bloat_top3),
                snapshot.long_queries, snapshot.lock_waits,
                snapshot.alerts_sent, snapshot.recorded_at,
                snapshot.pool_utilization,
                snapshot.cache_hit_ratio,
                json.dumps(snapshot.top_tables_by_size),
                snapshot.idx_scan_ratio,
                snapshot.health_score,
            )

    @staticmethod
    async def _get_cache_hit_ratio(conn: asyncpg.Connection) -> float | None:
        row = await conn.fetchrow(
            "SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit + blks_read), 0), 2) AS ratio "
            "FROM pg_stat_database WHERE datname = current_database()",
        )
        return float(row["ratio"]) if row and row["ratio"] is not None else None

    @staticmethod
    async def _get_top_tables_by_size(conn: asyncpg.Connection) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            "SELECT relname, pg_total_relation_size(relid) AS total_bytes "
            "FROM pg_stat_user_tables "
            "ORDER BY pg_total_relation_size(relid) DESC LIMIT 5",
        )
        return [{"table": r["relname"], "bytes": r["total_bytes"]} for r in rows]

    @staticmethod
    async def _get_idx_scan_ratio(conn: asyncpg.Connection) -> float | None:
        val = await conn.fetchval(
            "SELECT round(100.0 * sum(idx_scan) / nullif(sum(seq_scan + idx_scan), 0), 2) "
            "FROM pg_stat_user_tables WHERE seq_scan + idx_scan > 0",
        )
        return float(val) if val is not None else None

    @staticmethod
    async def _get_dead_tuple_ratio(conn: asyncpg.Connection) -> float:
        val = await conn.fetchval(
            "SELECT COALESCE(round(100.0 * sum(n_dead_tup) / "
            "nullif(sum(n_live_tup + n_dead_tup), 0), 2), 0) "
            "FROM pg_stat_user_tables",
        )
        return float(val) if val is not None else 0.0

    @staticmethod
    async def _count_active_connections(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_stat_activity WHERE state != 'idle'",
        )
        return int(row["cnt"]) if row else 0

    @staticmethod
    async def _get_max_connections(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow("SHOW max_connections")
        return int(row["max_connections"]) if row else 100

    @staticmethod
    async def _get_db_size(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow(
            "SELECT pg_database_size(current_database()) AS size",
        )
        return int(row["size"]) if row else 0

    @staticmethod
    async def _get_bloat_top3(conn: asyncpg.Connection) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            "SELECT relname, n_dead_tup, n_live_tup "
            "FROM pg_stat_user_tables WHERE n_dead_tup > 1000 "
            "ORDER BY n_dead_tup DESC LIMIT 3",
        )
        return [
            {"table": r["relname"], "dead_tuples": r["n_dead_tup"], "live_tuples": r["n_live_tup"]}
            for r in rows
        ]

    @staticmethod
    async def _count_long_queries(conn: asyncpg.Connection, threshold_seconds: int) -> int:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_stat_activity "
            "WHERE state = 'active' AND query_start < now() - make_interval(secs => $1)",
            threshold_seconds,
        )
        return int(row["cnt"]) if row else 0

    @staticmethod
    async def _count_lock_waits(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_locks WHERE NOT granted",
        )
        return int(row["cnt"]) if row else 0
