"""Olympus v3 — Insights Collector.

Query Intelligence: reads pg_stat_statements, detects regression.
Bloat Intelligence: unused indexes, missing index suggestions.

pg_stat_statements is a SOFT dependency — absent = skip with warning.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import asyncpg

from backend.services.olympus.models import InsightRecord, PulseAction

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.insights")

_REGRESSION_THRESHOLD_PCT = 30.0


class InsightsCollector:
    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self._pool = db_pool
        self._rules = rules
        self._alert: Any = None

    def set_alert_callback(self, callback: Any) -> None:
        self._alert = callback

    async def _has_pgss(self, conn: asyncpg.Connection) -> bool:
        val = await conn.fetchval(
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'",
        )
        return val is not None

    async def collect_query_insights(self) -> list[PulseAction]:
        actions: list[PulseAction] = []
        async with self._pool.acquire() as conn:
            if not await self._has_pgss(conn):
                actions.append(PulseAction(
                    action_type="query_intelligence", target="pg_stat_statements",
                    outcome="skipped",
                    reflection="pg_stat_statements not available",
                ))
                logger.warning("pg_stat_statements not available — skipping query intelligence")
                return actions

            top_queries = await conn.fetch(
                "SELECT queryid, LEFT(query, 200) AS query, calls, "
                "total_exec_time, mean_exec_time, rows "
                "FROM pg_stat_statements "
                "WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) "
                "ORDER BY total_exec_time DESC LIMIT 10",
            )

            if not top_queries:
                return actions

            prev_insights = await conn.fetch(
                "SELECT evidence FROM olympus_insights "
                "WHERE source = 'query_intelligence' AND insight_type = 'pattern' "
                "ORDER BY created_at DESC LIMIT 10",
            )

        prev_by_qid: dict[int, float] = {}
        for row in prev_insights:
            ev = row["evidence"] if isinstance(row["evidence"], dict) else json.loads(row["evidence"])
            qid = ev.get("queryid")
            mean = ev.get("mean_exec_time")
            if qid is not None and mean is not None:
                prev_by_qid[int(qid)] = float(mean)

        for q in top_queries:
            qid = q["queryid"]
            mean = float(q["mean_exec_time"])
            insight = InsightRecord(
                insight_type="pattern",
                title=f"Top query #{qid}",
                content=q["query"],
                evidence={
                    "queryid": qid, "calls": q["calls"],
                    "total_exec_time": round(q["total_exec_time"], 2),
                    "mean_exec_time": round(mean, 2),
                    "rows": q["rows"],
                },
                source="query_intelligence",
                applicable_to=[],
            )
            await self._persist_insight(insight)

            prev_mean = prev_by_qid.get(qid)
            if prev_mean is not None and prev_mean > 0:
                pct_change = ((mean - prev_mean) / prev_mean) * 100
                if pct_change > _REGRESSION_THRESHOLD_PCT:
                    anomaly = InsightRecord(
                        insight_type="anomaly",
                        title=f"Query regression: #{qid} +{pct_change:.0f}%",
                        content=q["query"],
                        evidence={
                            "queryid": qid,
                            "previous_mean_ms": round(prev_mean, 2),
                            "current_mean_ms": round(mean, 2),
                            "pct_change": round(pct_change, 1),
                        },
                        source="query_intelligence",
                    )
                    await self._persist_insight(anomaly)
                    actions.append(PulseAction(
                        action_type="query_regression", target=str(qid),
                        detail={"pct_change": round(pct_change, 1)},
                        outcome="success",
                    ))
                    if self._alert:
                        await self._alert(
                            f"Query regression: #{qid} mean {prev_mean:.0f}ms → {mean:.0f}ms (+{pct_change:.0f}%)"
                        )

        actions.append(PulseAction(
            action_type="query_intelligence", target="pg_stat_statements",
            detail={"queries_analyzed": len(top_queries)},
            outcome="success",
        ))
        return actions

    async def collect_bloat_insights(self) -> list[PulseAction]:
        actions: list[PulseAction] = []

        async with self._pool.acquire() as conn:
            unused = await conn.fetch(
                "SELECT indexrelname, relname, idx_scan, "
                "pg_relation_size(indexrelid) AS idx_size "
                "FROM pg_stat_user_indexes "
                "WHERE idx_scan = 0 AND schemaname = 'public' "
                "AND pg_relation_size(indexrelid) > 1048576 "
                "ORDER BY pg_relation_size(indexrelid) DESC LIMIT 10",
            )

            low_idx = await conn.fetch(
                "SELECT relname, seq_scan, idx_scan, "
                "pg_total_relation_size(relid) AS table_size, "
                "round(100.0 * idx_scan / nullif(seq_scan + idx_scan, 0), 1) AS idx_ratio "
                "FROM pg_stat_user_tables "
                "WHERE seq_scan + idx_scan > 100 "
                "AND pg_total_relation_size(relid) > 10485760 "
                "AND idx_scan * 1.0 / nullif(seq_scan + idx_scan, 0) < 0.5 "
                "ORDER BY seq_scan DESC LIMIT 10",
            )

        for idx in unused:
            insight = InsightRecord(
                insight_type="recommendation",
                title=f"Unused index: {idx['indexrelname']}",
                content=f"Index on {idx['relname']} has 0 scans, size {idx['idx_size']} bytes. Candidate for DROP.",
                evidence={
                    "index": idx["indexrelname"], "table": idx["relname"],
                    "idx_scan": idx["idx_scan"], "size_bytes": idx["idx_size"],
                },
                source="bloat_intelligence",
                applicable_to=[idx["indexrelname"]],
            )
            await self._persist_insight(insight)
            actions.append(PulseAction(
                action_type="unused_index", target=idx["indexrelname"],
                detail={"table": idx["relname"], "size_bytes": idx["idx_size"]},
                outcome="proposed",
            ))

        for tbl in low_idx:
            insight = InsightRecord(
                insight_type="recommendation",
                title=f"Missing index: {tbl['relname']}",
                content=f"Table {tbl['relname']} has {tbl['seq_scan']} seq scans vs {tbl['idx_scan']} idx scans ({tbl['idx_ratio']}%). Consider adding indexes.",
                evidence={
                    "table": tbl["relname"], "seq_scan": tbl["seq_scan"],
                    "idx_scan": tbl["idx_scan"], "table_size": tbl["table_size"],
                    "idx_ratio": float(tbl["idx_ratio"]) if tbl["idx_ratio"] else 0,
                },
                source="bloat_intelligence",
                applicable_to=[tbl["relname"]],
            )
            await self._persist_insight(insight)
            actions.append(PulseAction(
                action_type="missing_index", target=tbl["relname"],
                detail={"seq_scan": tbl["seq_scan"], "idx_ratio": float(tbl["idx_ratio"] or 0)},
                outcome="proposed",
            ))

        return actions

    async def _persist_insight(self, insight: InsightRecord) -> None:
        query = """
            INSERT INTO olympus_insights (
                insight_type, title, content, evidence, source,
                confidence, applicable_to
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
        """
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    insight.insight_type, insight.title, insight.content,
                    json.dumps(insight.evidence), insight.source,
                    insight.confidence, insight.applicable_to,
                )
        except Exception:
            logger.exception("Failed to persist insight: %s", insight.title)
