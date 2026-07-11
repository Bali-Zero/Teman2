"""Olympus v2 — Pulse Rhythm.

Periodic maintenance: vacuum, audit cleanup, sequence repair,
index rebuild, MV refresh, session cleanup, partitioning.

IMPORTANT: outcome values MUST be "success", "failure", or "skipped"
to match the CHECK constraint on olympus_actions.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import asyncpg

from backend.services.olympus.models import PulseAction
from backend.services.olympus.safety import PulseBudget, action_timeouts

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.pulse")

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
    "news_items",
    "conversation_messages",
}


class Pulse:
    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self._pool = db_pool
        self._rules = rules

    async def vacuum_bloated_tables(self) -> list[PulseAction]:
        threshold: int = self._rules.get_threshold("vacuum_dead_pct_threshold", default=5)
        query = """
            SELECT relname, n_live_tup, n_dead_tup,
                   CASE WHEN n_live_tup + n_dead_tup = 0 THEN 0
                        ELSE (n_dead_tup * 100.0 / (n_live_tup + n_dead_tup))
                   END AS dead_pct
            FROM pg_stat_user_tables WHERE n_dead_tup > 0
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            table, dead_pct = row["relname"], float(row["dead_pct"])
            if dead_pct <= threshold:
                continue
            if table not in _SAFE_VACUUM_TABLES:
                actions.append(
                    PulseAction(
                        action_type="vacuum",
                        target=table,
                        detail={"dead_pct": dead_pct},
                        outcome="skipped",
                        rule_applied="vacuum_dead_pct_threshold",
                        reflection="Not in safe-list",
                    )
                )
                logger.info(
                    "Skipped VACUUM on %s (dead_pct=%.1f%%, not in safe-list)", table, dead_pct
                )
                continue

            t0 = time.monotonic()
            try:
                # P0.1 — bound how long the VACUUM may run / wait for locks so a
                # single maintenance statement can never stall the shared pool.
                st = int(self._rules.get_threshold("action_statement_timeout_s", default=300))
                lk = int(self._rules.get_threshold("action_lock_timeout_s", default=5))
                async with action_timeouts(self._pool, st, lk) as conn:
                    await conn.execute(f"VACUUM ANALYZE {table}")
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(
                    PulseAction(
                        action_type="vacuum",
                        target=table,
                        detail={"dead_pct": dead_pct},
                        outcome="success",
                        duration_ms=duration_ms,
                        rule_applied="vacuum_dead_pct_threshold",
                    )
                )
                logger.info(
                    "VACUUM ANALYZE %s in %dms (dead_pct=%.1f%%)", table, duration_ms, dead_pct
                )
            except Exception:
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(
                    PulseAction(
                        action_type="vacuum",
                        target=table,
                        detail={"dead_pct": dead_pct},
                        outcome="failure",
                        duration_ms=duration_ms,
                        rule_applied="vacuum_dead_pct_threshold",
                        reflection="VACUUM failed",
                    )
                )
                logger.exception("VACUUM ANALYZE %s failed", table)
        return actions

    async def cleanup_audit_trail(self) -> PulseAction:
        retention: int = self._rules.get_threshold("audit_retention_days", default=90)
        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                relkind = await conn.fetchval(
                    "SELECT relkind FROM pg_class WHERE relname = 'api_audit_trail'",
                )

                if relkind == "p":
                    old_parts = await conn.fetch(
                        "SELECT c.relname AS child_name "
                        "FROM pg_inherits i "
                        "JOIN pg_class c ON c.oid = i.inhrelid "
                        "JOIN pg_class p ON p.oid = i.inhparent "
                        "WHERE p.relname = 'api_audit_trail' "
                        "AND c.relname != 'api_audit_trail_default' "
                        "AND to_date(right(c.relname, 7), 'YYYY_MM') < "
                        "    date_trunc('month', NOW() - make_interval(days => $1))",
                        retention,
                    )
                    dropped = []
                    for part in old_parts:
                        name = part["child_name"]
                        await conn.execute(f"ALTER TABLE api_audit_trail DETACH PARTITION {name}")
                        await conn.execute(f"DROP TABLE {name}")
                        dropped.append(name)

                    duration_ms = int((time.monotonic() - t0) * 1000)
                    return PulseAction(
                        action_type="cleanup_audit_trail",
                        target="api_audit_trail",
                        detail={
                            "retention_days": retention,
                            "method": "detach_drop",
                            "partitions_dropped": dropped,
                        },
                        outcome="success",
                        duration_ms=duration_ms,
                        rule_applied="audit_retention_days",
                    )
                else:
                    sql = f"DELETE FROM api_audit_trail WHERE created_at < NOW() - INTERVAL '{retention} days'"
                    result = await conn.execute(sql)
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    deleted = int(result.split()[-1]) if result else 0
                    return PulseAction(
                        action_type="cleanup_audit_trail",
                        target="api_audit_trail",
                        detail={
                            "retention_days": retention,
                            "rows_deleted": deleted,
                            "method": "delete",
                        },
                        outcome="success",
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
                outcome="failure",
                duration_ms=duration_ms,
                rule_applied="audit_retention_days",
                reflection="Cleanup failed",
            )

    async def autovacuum_advisor(self) -> list[PulseAction]:
        query = """
            SELECT c.relname, c.reloptions, s.n_dead_tup, s.n_tup_upd, s.n_tup_ins
            FROM pg_class c
            JOIN pg_stat_user_tables s ON s.relname = c.relname
            WHERE c.relkind = 'r' AND s.schemaname = 'public'
              AND s.n_dead_tup > 10000
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            reloptions = row["reloptions"] or []
            has_custom = any("autovacuum" in str(opt) for opt in reloptions)
            if has_custom:
                continue

            total_writes = (row["n_tup_upd"] or 0) + (row["n_tup_ins"] or 0)
            update_ratio = (row["n_tup_upd"] or 0) / max(total_writes, 1)
            suggest_fillfactor = update_ratio > 0.5

            detail: dict[str, Any] = {
                "n_dead_tup": row["n_dead_tup"],
                "suggestion": "ALTER TABLE {t} SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02)".format(
                    t=row["relname"]
                ),
            }
            if suggest_fillfactor:
                detail["fillfactor_suggestion"] = (
                    f"ALTER TABLE {row['relname']} SET (fillfactor = 85)"
                )

            actions.append(
                PulseAction(
                    action_type="autovacuum_tuning",
                    target=row["relname"],
                    detail=detail,
                    outcome="proposed",
                    reflection=f"No custom autovacuum, {row['n_dead_tup']} dead tuples",
                )
            )
            logger.info(
                "Proposed autovacuum tuning for %s (%d dead tuples)",
                row["relname"],
                row["n_dead_tup"],
            )

        return actions

    async def repair_sequences(self) -> list[PulseAction]:
        query = """
            SELECT t.relname AS table_name, a.attname AS column_name,
                   pg_get_serial_sequence(t.relname::text, a.attname::text) AS seq
            FROM pg_class t
            JOIN pg_attribute a ON a.attrelid = t.oid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE t.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
              AND n.nspname = 'public'
              AND pg_get_serial_sequence(t.relname::text, a.attname::text) IS NOT NULL
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
        except Exception:
            logger.exception("repair_sequences: failed to discover sequences")
            return []

        actions: list[PulseAction] = []
        for row in rows:
            table, column, seq = row["table_name"], row["column_name"], row["seq"]
            try:
                async with self._pool.acquire() as conn:
                    max_val = await conn.fetchval(f"SELECT COALESCE(MAX({column}), 0) FROM {table}")
                    last_val = await conn.fetchval(f"SELECT last_value FROM {seq}")
            except Exception as exc:
                actions.append(
                    PulseAction(
                        action_type="repair_sequence",
                        target=seq,
                        detail={
                            "table": table,
                            "column": column,
                            "reason": str(exc),
                        },
                        outcome="skipped",
                        reflection="sequence read failed; check runtime grants",
                    )
                )
                logger.warning(
                    "Skipping sequence repair check for %s: %s",
                    seq,
                    exc,
                    exc_info=True,
                )
                continue

            if max_val is not None and last_val is not None and max_val > last_val:
                t0 = time.monotonic()
                try:
                    async with self._pool.acquire() as conn:
                        await conn.execute(f"SELECT setval('{seq}', {max_val})")
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(
                        PulseAction(
                            action_type="repair_sequence",
                            target=seq,
                            detail={
                                "table": table,
                                "column": column,
                                "old": last_val,
                                "new": max_val,
                            },
                            outcome="success",
                            duration_ms=duration_ms,
                        )
                    )
                    logger.info("Repaired sequence %s: %d -> %d", seq, last_val, max_val)
                except Exception:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(
                        PulseAction(
                            action_type="repair_sequence",
                            target=seq,
                            detail={"table": table, "column": column},
                            outcome="failure",
                            duration_ms=duration_ms,
                            reflection="setval failed",
                        )
                    )
                    logger.exception("Failed to repair sequence %s", seq)
        return actions

    async def rebuild_invalid_indexes(self) -> list[PulseAction]:
        query = """
            SELECT c.relname AS index_name, t.relname AS table_name
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_class t ON t.oid = i.indrelid
            WHERE NOT i.indisvalid
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            idx, table = row["index_name"], row["table_name"]
            t0 = time.monotonic()
            try:
                # P0.1 — bound REINDEX (2 table scans + waits for txns; can run
                # for hours on a large index). lock_timeout keeps it from
                # blocking writers indefinitely.
                st = int(self._rules.get_threshold("action_statement_timeout_s", default=300))
                lk = int(self._rules.get_threshold("action_lock_timeout_s", default=5))
                async with action_timeouts(self._pool, st, lk) as conn:
                    await conn.execute(f"REINDEX INDEX CONCURRENTLY {idx}")
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(
                    PulseAction(
                        action_type="reindex",
                        target=idx,
                        detail={"table": table},
                        outcome="success",
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(
                    PulseAction(
                        action_type="reindex",
                        target=idx,
                        detail={"table": table},
                        outcome="failure",
                        duration_ms=duration_ms,
                        reflection="REINDEX CONCURRENTLY failed",
                    )
                )
                logger.exception("REINDEX CONCURRENTLY %s failed", idx)
        return actions

    async def refresh_materialized_views(self) -> list[PulseAction]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT matviewname FROM pg_matviews")

        actions: list[PulseAction] = []
        for row in rows:
            view = row["matviewname"]
            t0 = time.monotonic()
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(
                    PulseAction(
                        action_type="refresh_matview",
                        target=view,
                        detail={"concurrent": True},
                        outcome="success",
                        duration_ms=duration_ms,
                    )
                )
            except Exception:
                logger.warning("CONCURRENT refresh failed for %s, trying non-concurrent", view)
                t0 = time.monotonic()
                try:
                    async with self._pool.acquire() as conn:
                        await conn.execute(f"REFRESH MATERIALIZED VIEW {view}")
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(
                        PulseAction(
                            action_type="refresh_matview",
                            target=view,
                            detail={"concurrent": False},
                            outcome="success",
                            duration_ms=duration_ms,
                            reflection="Fell back to non-concurrent refresh",
                        )
                    )
                except Exception:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(
                        PulseAction(
                            action_type="refresh_matview",
                            target=view,
                            detail={"concurrent": False},
                            outcome="failure",
                            duration_ms=duration_ms,
                            reflection="Both concurrent and non-concurrent failed",
                        )
                    )
                    logger.exception("Refresh matview %s failed entirely", view)
        return actions

    async def cleanup_expired_sessions(self) -> PulseAction:
        sql = "DELETE FROM persistent_sessions WHERE updated_at < NOW() - INTERVAL '30 days'"
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
                outcome="success",
                duration_ms=duration_ms,
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("cleanup_expired_sessions failed")
            return PulseAction(
                action_type="cleanup_expired_sessions",
                target="persistent_sessions",
                outcome="failure",
                duration_ms=duration_ms,
                reflection="DELETE failed",
            )

    async def ensure_next_partition(self) -> PulseAction | None:
        sql_bounds = """
            SELECT date_trunc('month', NOW() + INTERVAL '1 month') AS start,
                   date_trunc('month', NOW() + INTERVAL '2 months') AS stop
        """
        async with self._pool.acquire() as conn:
            bounds = await conn.fetchrow(sql_bounds)

        start, stop = bounds["start"], bounds["stop"]
        partition_name = f"olympus_heartbeats_{start.strftime('%Y_%m')}"

        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_class WHERE relname = $1 AND relkind = 'r'",
                partition_name,
            )
        if exists:
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
                outcome="success",
                duration_ms=duration_ms,
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("Failed to create partition %s", partition_name)
            return PulseAction(
                action_type="ensure_partition",
                target=partition_name,
                outcome="failure",
                duration_ms=duration_ms,
                reflection="CREATE TABLE partition failed",
            )

    async def cleanup_olympus_self(self) -> list[PulseAction]:
        """P0.5 — Olympus applies its own retention medicine.

        The guardian creates monthly olympus_heartbeats partitions but never
        dropped old ones, and never pruned olympus_actions/olympus_insights →
        unbounded growth. This drops heartbeat partitions older than
        olympus_hb_retention_months and prunes aged actions + superseded/aged
        insights. Mirrors the cleanup_audit_trail DETACH/DROP pattern.
        """
        actions: list[PulseAction] = []
        hb_months = int(self._rules.get_threshold("olympus_hb_retention_months", default=6))
        act_days = int(self._rules.get_threshold("olympus_actions_retention_days", default=90))
        ins_days = int(self._rules.get_threshold("olympus_insights_retention_days", default=90))

        # 1. Drop old olympus_heartbeats partitions (DETACH + DROP).
        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                old_parts = await conn.fetch(
                    "SELECT c.relname AS child_name "
                    "FROM pg_inherits i "
                    "JOIN pg_class c ON c.oid = i.inhrelid "
                    "JOIN pg_class p ON p.oid = i.inhparent "
                    "WHERE p.relname = 'olympus_heartbeats' "
                    "AND c.relname ~ '^olympus_heartbeats_[0-9]{4}_[0-9]{2}$' "
                    "AND to_date(right(c.relname, 7), 'YYYY_MM') < "
                    "    date_trunc('month', NOW() - make_interval(months => $1))",
                    hb_months,
                )
                dropped: list[str] = []
                for part in old_parts:
                    name = part["child_name"]
                    await conn.execute(f"ALTER TABLE olympus_heartbeats DETACH PARTITION {name}")
                    await conn.execute(f"DROP TABLE {name}")
                    dropped.append(name)
            actions.append(
                PulseAction(
                    action_type="cleanup_olympus_self",
                    target="olympus_heartbeats",
                    detail={"retention_months": hb_months, "partitions_dropped": dropped},
                    outcome="success",
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    rule_applied="olympus_hb_retention_months",
                )
            )
        except Exception:
            logger.exception("cleanup_olympus_self: heartbeat partition drop failed")
            actions.append(
                PulseAction(
                    action_type="cleanup_olympus_self",
                    target="olympus_heartbeats",
                    detail={"retention_months": hb_months},
                    outcome="failure",
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    rule_applied="olympus_hb_retention_months",
                    reflection="partition drop failed",
                )
            )

        # 2. Prune aged olympus_actions + superseded/aged olympus_insights.
        for table, rule, days, where in (
            (
                "olympus_actions",
                "olympus_actions_retention_days",
                act_days,
                "executed_at < NOW() - make_interval(days => $1)",
            ),
            (
                "olympus_insights",
                "olympus_insights_retention_days",
                ins_days,
                "(superseded_by IS NOT NULL OR created_at < NOW() - make_interval(days => $1))",
            ),
        ):
            t0 = time.monotonic()
            try:
                async with self._pool.acquire() as conn:
                    # table/where are constant literals from the loop tuple above
                    # (no user input) — not a SQL-injection surface.
                    result = await conn.execute(f"DELETE FROM {table} WHERE {where}", days)
                deleted = int(result.split()[-1]) if result else 0
                actions.append(
                    PulseAction(
                        action_type="cleanup_olympus_self",
                        target=table,
                        detail={"retention_days": days, "rows_deleted": deleted},
                        outcome="success",
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        rule_applied=rule,
                    )
                )
            except Exception:
                logger.exception("cleanup_olympus_self: prune %s failed", table)
                actions.append(
                    PulseAction(
                        action_type="cleanup_olympus_self",
                        target=table,
                        detail={"retention_days": days},
                        outcome="failure",
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        rule_applied=rule,
                        reflection="prune failed",
                    )
                )
        return actions

    async def run_full_pulse(self) -> list[PulseAction]:
        """Run all maintenance groups, bounded by a per-pulse budget (P0.2).

        Each group is gated on the budget so a runaway pulse (e.g. hundreds of
        bloated tables) cannot exhaust the shared asyncpg pool / wall-clock on a
        small machine. When the budget trips, remaining groups are skipped and a
        single `budget_exceeded` action records why.
        """
        max_actions = int(self._rules.get_threshold("max_actions_per_pulse", default=50))
        max_runtime = int(self._rules.get_threshold("max_pulse_runtime_s", default=600))
        budget = PulseBudget(max_actions, max_runtime)

        actions: list[PulseAction] = []
        groups = (
            self.vacuum_bloated_tables,
            self.cleanup_audit_trail,
            self.repair_sequences,
            self.rebuild_invalid_indexes,
            self.refresh_materialized_views,
            self.cleanup_expired_sessions,
            self.ensure_next_partition,
            self.cleanup_olympus_self,
            self.autovacuum_advisor,
        )
        for group in groups:
            if budget.exceeded():
                actions.append(
                    PulseAction(
                        action_type="budget_exceeded",
                        target=group.__name__,
                        detail={"actions_so_far": budget.count},
                        outcome="skipped",
                        reflection=budget.reason(),
                    )
                )
                logger.warning(
                    "Pulse budget tripped before %s: %s", group.__name__, budget.reason()
                )
                break
            result = await group()
            if result is None:
                continue
            new_actions = result if isinstance(result, list) else [result]
            actions.extend(new_actions)
            budget.record(len(new_actions))

        logger.info(
            "Full pulse: %d actions (budget %d/%ds)", len(actions), max_actions, max_runtime
        )
        return actions
