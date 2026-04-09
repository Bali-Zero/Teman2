"""Olympus DB Guardian — Pulse Rhythm.

Periodic maintenance actions: vacuum, audit cleanup, sequence repair,
index rebuild, materialized-view refresh, session cleanup, partitioning.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import asyncpg

from backend.services.olympus.models import PulseAction

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.pulse")

# ---------------------------------------------------------------------------
# Safe-list for VACUUM — only these tables may be vacuumed automatically.
# ---------------------------------------------------------------------------

_SAFE_VACUUM_TABLES: set[str] = {
    "api_audit_trail",
    "auth_audit_log",
    "kg_edges",
    "kg_nodes",
    "company_documents",
    "memory_facts",
    "team_timesheet",
    "whatsapp_message_context",
    "cell_pulse_log",
    "user_stats",
    "clients",
    "ab_test_metrics",
    "whatsapp_contacts",
    "documents",
    "query_analytics",
    "activity_log",
    "workflow_analytics",
    "cell_episodes",
    "conversations",
    "episodic_memories",
    "olympus_heartbeats",
    "olympus_actions",
}


class Pulse:
    """Execute maintenance actions against the database."""

    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self._pool = db_pool
        self._rules = rules

    # ------------------------------------------------------------------
    # 1. Vacuum bloated tables
    # ------------------------------------------------------------------

    async def vacuum_bloated_tables(self) -> list[PulseAction]:
        """VACUUM ANALYZE tables whose dead-tuple percentage exceeds threshold."""
        threshold: int = self._rules.get_threshold(
            "vacuum_dead_pct_threshold", default=5,
        )

        query = """
            SELECT relname,
                   n_live_tup,
                   n_dead_tup,
                   CASE WHEN n_live_tup + n_dead_tup = 0 THEN 0
                        ELSE (n_dead_tup * 100.0
                              / (n_live_tup + n_dead_tup))
                   END AS dead_pct
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 0
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            table = row["relname"]
            dead_pct = float(row["dead_pct"])

            if dead_pct <= threshold:
                continue

            if table not in _SAFE_VACUUM_TABLES:
                actions.append(PulseAction(
                    action_type="vacuum",
                    target=table,
                    detail={"dead_pct": dead_pct},
                    outcome="skipped",
                    rule_applied="vacuum_dead_pct_threshold",
                    reflection=f"Table {table} not in safe-list",
                ))
                logger.info(
                    "Skipped VACUUM on %s (dead_pct=%.1f%%, not in safe-list)",
                    table, dead_pct,
                )
                continue

            t0 = time.monotonic()
            try:
                # VACUUM cannot run inside a transaction block, so use
                # a raw connection with autocommit.
                async with self._pool.acquire() as conn:
                    await conn.execute(f"VACUUM ANALYZE {table}")  # noqa: S608
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="vacuum",
                    target=table,
                    detail={"dead_pct": dead_pct},
                    outcome="ok",
                    duration_ms=duration_ms,
                    rule_applied="vacuum_dead_pct_threshold",
                ))
                logger.info(
                    "VACUUM ANALYZE %s completed in %dms (dead_pct=%.1f%%)",
                    table, duration_ms, dead_pct,
                )
            except Exception:
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="vacuum",
                    target=table,
                    detail={"dead_pct": dead_pct},
                    outcome="error",
                    duration_ms=duration_ms,
                    rule_applied="vacuum_dead_pct_threshold",
                    reflection="VACUUM failed",
                ))
                logger.exception("VACUUM ANALYZE %s failed", table)

        return actions

    # ------------------------------------------------------------------
    # 2. Cleanup audit trail
    # ------------------------------------------------------------------

    async def cleanup_audit_trail(self) -> PulseAction:
        """Delete old rows from api_audit_trail based on retention rule."""
        retention: int = self._rules.get_threshold(
            "audit_retention_days", default=90,
        )

        sql = (
            "DELETE FROM api_audit_trail "
            f"WHERE created_at < NOW() - INTERVAL '{retention} days'"
        )

        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(sql)
            duration_ms = int((time.monotonic() - t0) * 1000)
            deleted = int(result.split()[-1]) if result else 0
            return PulseAction(
                action_type="cleanup_audit_trail",
                target="api_audit_trail",
                detail={"retention_days": retention, "rows_deleted": deleted},
                outcome="ok",
                duration_ms=duration_ms,
                rule_applied="audit_retention_days",
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("cleanup_audit_trail failed")
            return PulseAction(
                action_type="cleanup_audit_trail",
                target="api_audit_trail",
                detail={"retention_days": retention},
                outcome="error",
                duration_ms=duration_ms,
                rule_applied="audit_retention_days",
                reflection="DELETE failed",
            )

    # ------------------------------------------------------------------
    # 3. Repair broken sequences
    # ------------------------------------------------------------------

    async def repair_sequences(self) -> list[PulseAction]:
        """Find and fix sequences where max(pk) > last_value."""
        query = """
            SELECT t.relname AS table_name,
                   a.attname  AS column_name,
                   pg_get_serial_sequence(t.relname::text, a.attname::text) AS seq
            FROM pg_class t
            JOIN pg_attribute a ON a.attrelid = t.oid
            WHERE t.relkind = 'r'
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND pg_get_serial_sequence(t.relname::text, a.attname::text) IS NOT NULL
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            table = row["table_name"]
            column = row["column_name"]
            seq = row["seq"]

            async with self._pool.acquire() as conn:
                max_val = await conn.fetchval(
                    f"SELECT COALESCE(MAX({column}), 0) FROM {table}"  # noqa: S608
                )
                last_val = await conn.fetchval(
                    f"SELECT last_value FROM {seq}"  # noqa: S608
                )

            if max_val is not None and last_val is not None and max_val > last_val:
                t0 = time.monotonic()
                try:
                    async with self._pool.acquire() as conn:
                        await conn.execute(
                            f"SELECT setval('{seq}', {max_val})"  # noqa: S608
                        )
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="repair_sequence",
                        target=seq,
                        detail={
                            "table": table,
                            "column": column,
                            "old_last_value": last_val,
                            "new_last_value": max_val,
                        },
                        outcome="ok",
                        duration_ms=duration_ms,
                    ))
                    logger.info(
                        "Repaired sequence %s: %d -> %d", seq, last_val, max_val,
                    )
                except Exception:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="repair_sequence",
                        target=seq,
                        detail={"table": table, "column": column},
                        outcome="error",
                        duration_ms=duration_ms,
                        reflection="setval failed",
                    ))
                    logger.exception("Failed to repair sequence %s", seq)

        return actions

    # ------------------------------------------------------------------
    # 4. Rebuild invalid indexes
    # ------------------------------------------------------------------

    async def rebuild_invalid_indexes(self) -> list[PulseAction]:
        """REINDEX CONCURRENTLY any invalid indexes."""
        query = """
            SELECT c.relname AS index_name,
                   t.relname AS table_name
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_class t ON t.oid = i.indrelid
            WHERE NOT i.indisvalid
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            idx = row["index_name"]
            table = row["table_name"]
            t0 = time.monotonic()
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        f"REINDEX INDEX CONCURRENTLY {idx}"  # noqa: S608
                    )
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="reindex",
                    target=idx,
                    detail={"table": table},
                    outcome="ok",
                    duration_ms=duration_ms,
                ))
                logger.info("REINDEX CONCURRENTLY %s completed in %dms", idx, duration_ms)
            except Exception:
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="reindex",
                    target=idx,
                    detail={"table": table},
                    outcome="error",
                    duration_ms=duration_ms,
                    reflection="REINDEX CONCURRENTLY failed",
                ))
                logger.exception("REINDEX CONCURRENTLY %s failed", idx)

        return actions

    # ------------------------------------------------------------------
    # 5. Refresh materialized views
    # ------------------------------------------------------------------

    async def refresh_materialized_views(self) -> list[PulseAction]:
        """Refresh all materialized views, preferring CONCURRENTLY."""
        query = "SELECT matviewname FROM pg_matviews"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            view = row["matviewname"]
            t0 = time.monotonic()
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"  # noqa: S608
                    )
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="refresh_matview",
                    target=view,
                    detail={"concurrent": True},
                    outcome="ok",
                    duration_ms=duration_ms,
                ))
                logger.info(
                    "Refreshed matview %s CONCURRENTLY in %dms", view, duration_ms,
                )
            except Exception:
                logger.warning(
                    "CONCURRENT refresh failed for %s, falling back to non-concurrent",
                    view,
                )
                t0 = time.monotonic()
                try:
                    async with self._pool.acquire() as conn:
                        await conn.execute(
                            f"REFRESH MATERIALIZED VIEW {view}"  # noqa: S608
                        )
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="refresh_matview",
                        target=view,
                        detail={"concurrent": False},
                        outcome="ok",
                        duration_ms=duration_ms,
                        reflection="Fell back to non-concurrent refresh",
                    ))
                    logger.info(
                        "Refreshed matview %s (non-concurrent) in %dms",
                        view, duration_ms,
                    )
                except Exception:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="refresh_matview",
                        target=view,
                        detail={"concurrent": False},
                        outcome="error",
                        duration_ms=duration_ms,
                        reflection="Both concurrent and non-concurrent refresh failed",
                    ))
                    logger.exception("Refresh matview %s failed entirely", view)

        return actions

    # ------------------------------------------------------------------
    # 6. Cleanup expired sessions
    # ------------------------------------------------------------------

    async def cleanup_expired_sessions(self) -> PulseAction:
        """Delete sessions older than 30 days from persistent_sessions."""
        sql = (
            "DELETE FROM persistent_sessions "
            "WHERE updated_at < NOW() - INTERVAL '30 days'"
        )

        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(sql)
            duration_ms = int((time.monotonic() - t0) * 1000)
            deleted = int(result.split()[-1]) if result else 0
            return PulseAction(
                action_type="cleanup_expired_sessions",
                target="persistent_sessions",
                detail={"rows_deleted": deleted},
                outcome="ok",
                duration_ms=duration_ms,
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("cleanup_expired_sessions failed")
            return PulseAction(
                action_type="cleanup_expired_sessions",
                target="persistent_sessions",
                detail={},
                outcome="error",
                duration_ms=duration_ms,
                reflection="DELETE failed",
            )

    # ------------------------------------------------------------------
    # 7. Ensure next month partition for olympus_heartbeats
    # ------------------------------------------------------------------

    async def ensure_next_partition(self) -> PulseAction | None:
        """Create next month's partition for olympus_heartbeats if missing."""
        # Determine next month boundaries
        sql_bounds = """
            SELECT date_trunc('month', NOW() + INTERVAL '1 month') AS start,
                   date_trunc('month', NOW() + INTERVAL '2 months') AS stop
        """

        async with self._pool.acquire() as conn:
            bounds = await conn.fetchrow(sql_bounds)

        start = bounds["start"]
        stop = bounds["stop"]
        partition_name = f"olympus_heartbeats_{start.strftime('%Y_%m')}"

        # Check if partition already exists
        check_sql = """
            SELECT 1 FROM pg_class
            WHERE relname = $1
              AND relkind = 'r'
        """
        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(check_sql, partition_name)

        if exists:
            logger.debug("Partition %s already exists", partition_name)
            return None

        create_sql = (
            f"CREATE TABLE {partition_name} PARTITION OF olympus_heartbeats "
            f"FOR VALUES FROM ('{start.strftime('%Y-%m-%d')}') "
            f"TO ('{stop.strftime('%Y-%m-%d')}')"
        )

        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(create_sql)
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info("Created partition %s", partition_name)
            return PulseAction(
                action_type="ensure_partition",
                target=partition_name,
                detail={
                    "range_start": start.strftime("%Y-%m-%d"),
                    "range_stop": stop.strftime("%Y-%m-%d"),
                },
                outcome="ok",
                duration_ms=duration_ms,
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("Failed to create partition %s", partition_name)
            return PulseAction(
                action_type="ensure_partition",
                target=partition_name,
                detail={},
                outcome="error",
                duration_ms=duration_ms,
                reflection="CREATE TABLE partition failed",
            )

    # ------------------------------------------------------------------
    # 8. Full pulse — run all maintenance actions
    # ------------------------------------------------------------------

    async def run_full_pulse(self) -> list[PulseAction]:
        """Execute all pulse maintenance actions and return collected results."""
        actions: list[PulseAction] = []

        actions.extend(await self.vacuum_bloated_tables())
        actions.append(await self.cleanup_audit_trail())
        actions.extend(await self.repair_sequences())
        actions.extend(await self.rebuild_invalid_indexes())
        actions.extend(await self.refresh_materialized_views())
        actions.append(await self.cleanup_expired_sessions())

        partition_action = await self.ensure_next_partition()
        if partition_action is not None:
            actions.append(partition_action)

        logger.info("Full pulse complete: %d actions", len(actions))
        return actions
