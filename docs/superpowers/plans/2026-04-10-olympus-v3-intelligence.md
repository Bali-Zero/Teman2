# Olympus v3 Intelligence Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the PostgreSQL database observable by extending Olympus heartbeat with cache/size/index metrics, a composite Health Score, and populating the empty `olympus_insights` table with query regression detection, bloat intelligence, and autovacuum recommendations.

**Architecture:** Extends the existing v2 module (6 files) with 1 new file (`insights.py`) and a migration. `InsightsCollector` runs during pulse; extended metrics run during heartbeat. `pg_stat_statements` is a soft dependency — absent = skip with warning.

**Tech Stack:** Python 3.11, asyncpg, Pydantic, pytest (mock-based)

**Spec:** `docs/superpowers/specs/2026-04-10-olympus-v3-intelligence-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| CREATE | `backend/services/olympus/insights.py` | InsightsCollector: query intelligence + bloat intelligence |
| CREATE | `backend/migrations/migration_104_olympus_v3_columns.py` | Add 4 columns to olympus_heartbeats + seed pgss_last_reset rule |
| CREATE | `backend/tests/services/olympus/test_insights.py` | Tests for InsightsCollector |
| MODIFY | `backend/services/olympus/models.py` | +InsightRecord, +HeartbeatSnapshot fields, +health_score helper |
| MODIFY | `backend/services/olympus/heartbeat.py` | +cache_hit, +table_sizes, +idx_ratio, +health_score, +persist columns |
| MODIFY | `backend/services/olympus/pulse.py` | +autovacuum_advisor, +partition-aware cleanup, +run insights |
| MODIFY | `backend/services/olympus/guardian.py` | Wire InsightsCollector into pulse, pass to persist |
| MODIFY | `backend/tests/services/olympus/test_heartbeat.py` | +health_score tests, +extended metric tests |
| MODIFY | `backend/tests/services/olympus/test_pulse.py` | +autovacuum_advisor tests, +partition-aware cleanup tests |
| MODIFY | `backend/tests/services/olympus/test_models.py` | +InsightRecord tests, +extended HeartbeatSnapshot tests |

---

### Task 1: Migration 104 — Add columns to olympus_heartbeats

**Files:**
- Create: `backend/migrations/migration_104_olympus_v3_columns.py`

- [ ] **Step 1: Create migration file**

```python
"""
Migration 104: Olympus v3 — Extended heartbeat columns + pgss rule

Adds cache_hit_ratio, top_tables_by_size, idx_scan_ratio, health_score
to olympus_heartbeats. Seeds pgss_last_reset rule for stats reset tracking.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "104_olympus_v3_columns"

UP_SQL = """
-- Add v3 columns to olympus_heartbeats (nullable for backward compat)
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS cache_hit_ratio NUMERIC(5,2);
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS top_tables_by_size JSONB;
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS idx_scan_ratio NUMERIC(5,2);
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS health_score SMALLINT;

-- Seed rule for pg_stat_statements reset tracking
INSERT INTO olympus_rules (rule_name, category, config, source)
VALUES ('pgss_last_reset', 'schedule', '{"value": null, "reset_interval_hours": 168}', 'v3')
ON CONFLICT (rule_name) DO NOTHING;

-- Seed health score alert threshold
INSERT INTO olympus_rules (rule_name, category, config, source)
VALUES ('health_score_alert_threshold', 'threshold', '{"value": 60}', 'v3')
ON CONFLICT (rule_name) DO NOTHING;
"""

DOWN_SQL = """
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS cache_hit_ratio;
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS top_tables_by_size;
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS idx_scan_ratio;
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS health_score;

DELETE FROM olympus_rules WHERE rule_name IN ('pgss_last_reset', 'health_score_alert_threshold');
"""


async def upgrade(conn) -> None:
    logger.info("Applying migration %s ...", MIGRATION_ID)
    await conn.execute(UP_SQL)
    logger.info("Migration %s applied successfully", MIGRATION_ID)


async def downgrade(conn) -> None:
    logger.info("Rolling back migration %s ...", MIGRATION_ID)
    await conn.execute(DOWN_SQL)
    logger.info("Migration %s rolled back", MIGRATION_ID)
```

- [ ] **Step 2: Verify migration imports cleanly**

Run: `cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.migrations.migration_104_olympus_v3_columns import MIGRATION_ID; print(f'OK: {MIGRATION_ID}')"`
Expected: `OK: 104_olympus_v3_columns`

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/migration_104_olympus_v3_columns.py
git commit -m "feat(olympus): migration 104 — v3 heartbeat columns + pgss rule"
```

---

### Task 2: Extend models — InsightRecord + HeartbeatSnapshot fields + health_score

**Files:**
- Modify: `backend/services/olympus/models.py`
- Modify: `backend/tests/services/olympus/test_models.py`

- [ ] **Step 1: Write failing tests for InsightRecord and extended HeartbeatSnapshot**

Append to `backend/tests/services/olympus/test_models.py`:

```python
from backend.services.olympus.models import InsightRecord


class TestInsightRecord:
    def test_defaults(self):
        r = InsightRecord(
            insight_type="pattern",
            title="Top query",
            content="SELECT * FROM clients",
            evidence={"total_ms": 1234},
            source="query_intelligence",
        )
        assert r.confidence == 1.0
        assert r.applicable_to == []

    def test_all_types_accepted(self):
        for t in ("pattern", "anomaly", "recommendation"):
            r = InsightRecord(
                insight_type=t, title="t", content="c",
                evidence={}, source="test",
            )
            assert r.insight_type == t


class TestHeartbeatSnapshotV3:
    def test_v3_fields_default_none(self):
        s = HeartbeatSnapshot(
            pool_size=5, pool_idle=3, active_connections=2,
            max_connections=100, db_size_bytes=1000,
        )
        assert s.cache_hit_ratio is None
        assert s.top_tables_by_size == []
        assert s.idx_scan_ratio is None
        assert s.health_score is None

    def test_health_score_perfect(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
            cache_hit_ratio=99.0, idx_scan_ratio=95.0,
        )
        score = s.compute_health_score(dead_tuple_ratio=0.5)
        assert score == 100

    def test_health_score_degraded(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=1, active_connections=8,
            max_connections=100, db_size_bytes=1000,
            long_queries=3, lock_waits=1,
            cache_hit_ratio=85.0, idx_scan_ratio=40.0,
        )
        score = s.compute_health_score(dead_tuple_ratio=10.0)
        assert 0 <= score <= 100
        assert score < 50  # heavily degraded

    def test_health_score_zero_floor(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=0, active_connections=10,
            max_connections=10, db_size_bytes=1000,
            long_queries=20, lock_waits=10,
            cache_hit_ratio=50.0, idx_scan_ratio=10.0,
        )
        score = s.compute_health_score(dead_tuple_ratio=50.0)
        assert score >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_models.py -v --tb=short 2>&1 | tail -20`
Expected: FAIL — `ImportError: cannot import name 'InsightRecord'`

- [ ] **Step 3: Implement models**

Add to `backend/services/olympus/models.py`, after the `OlympusRule` class:

```python
class InsightRecord(BaseModel):
    """A record to persist in olympus_insights."""

    insight_type: str  # pattern | anomaly | recommendation
    title: str
    content: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    source: str  # query_intelligence | bloat_intelligence | autovacuum_advisor
    confidence: float = Field(default=1.0)
    applicable_to: list[str] = Field(default_factory=list)
```

Extend `HeartbeatSnapshot` — add fields after `alerts_sent`:

```python
    # v3 extended metrics
    cache_hit_ratio: float | None = Field(default=None)
    top_tables_by_size: list[dict[str, Any]] = Field(default_factory=list)
    idx_scan_ratio: float | None = Field(default=None)
    health_score: int | None = Field(default=None)
```

Add method to `HeartbeatSnapshot`:

```python
    def compute_health_score(self, dead_tuple_ratio: float = 0.0) -> int:
        """Compute composite health score 0-100."""
        score = 0.0

        # Cache hit ratio: 25pt at >=95%, linear below
        if self.cache_hit_ratio is not None:
            score += min(25.0, 25.0 * min(self.cache_hit_ratio, 95.0) / 95.0)
        else:
            score += 25.0  # assume healthy if no data yet

        # Pool utilization: 20pt at <50%, linear above
        pool_pct = self.pool_utilization * 100
        if pool_pct <= 50:
            score += 20.0
        else:
            score += max(0.0, 20.0 * (100 - pool_pct) / 50.0)

        # Dead tuple ratio: 20pt at <2%, linear above
        if dead_tuple_ratio <= 2.0:
            score += 20.0
        else:
            score += max(0.0, 20.0 * (1 - (dead_tuple_ratio - 2.0) / 20.0))

        # Index scan ratio: 15pt at >80%, linear below
        if self.idx_scan_ratio is not None:
            score += min(15.0, 15.0 * min(self.idx_scan_ratio, 80.0) / 80.0)
        else:
            score += 15.0  # assume healthy if no data yet

        # Long queries: 10pt at 0, -2pt per query
        score += max(0.0, 10.0 - self.long_queries * 2.0)

        # Lock waits: 10pt at 0, -5pt per lock
        score += max(0.0, 10.0 - self.lock_waits * 5.0)

        return max(0, min(100, int(round(score))))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_models.py -v --tb=short`
Expected: 15 passed (8 existing + 7 new)

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/models.py backend/tests/services/olympus/test_models.py
git commit -m "feat(olympus): v3 models — InsightRecord, extended HeartbeatSnapshot, health_score"
```

---

### Task 3: Extended Heartbeat — cache_hit, table_sizes, idx_ratio, health_score

**Files:**
- Modify: `backend/services/olympus/heartbeat.py`
- Modify: `backend/tests/services/olympus/test_heartbeat.py`

- [ ] **Step 1: Write failing tests for extended metrics**

Append to `backend/tests/services/olympus/test_heartbeat.py`:

```python
class TestHeartbeatExtendedMetrics:
    @pytest.mark.asyncio
    async def test_collect_metrics_includes_v3_fields(self, mock_rules):
        """v3 metrics (cache_hit, table_sizes, idx_ratio) are collected."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        pool.get_size.return_value = 10
        pool.get_idle_size.return_value = 5

        # Mock all DB calls in order
        conn.fetchrow.side_effect = [
            {"cnt": 3},         # active_connections
            {"max_connections": "100"},  # SHOW max_connections
            {"size": 50000000}, # pg_database_size
            {"ratio": 98.5},    # cache_hit_ratio
        ]
        conn.fetch.side_effect = [
            [{"relname": "t1", "n_dead_tup": 2000, "n_live_tup": 50000}],  # bloat_top3
            [{"relname": "clients", "total_bytes": 10000000},               # top_tables
             {"relname": "kg_nodes", "total_bytes": 8000000}],
        ]
        conn.fetchval.side_effect = [
            75.3,  # idx_scan_ratio
            1.5,   # dead_tuple_ratio
        ]

        hb = Heartbeat(pool, mock_rules)
        snapshot = await hb.collect_metrics()

        assert snapshot.cache_hit_ratio == 98.5
        assert len(snapshot.top_tables_by_size) == 2
        assert snapshot.idx_scan_ratio == 75.3
        assert snapshot.health_score is not None
        assert 0 <= snapshot.health_score <= 100

    @pytest.mark.asyncio
    async def test_health_score_alert_when_low(self, mock_rules):
        """Alert fires when health_score < threshold."""
        mock_rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
            "long_query_threshold_seconds": 30,
            "pool_alert_pct": 80,
            "connection_alert_pct": 70,
            "health_score_alert_threshold": 60,
        }.get(name, default))

        hb = Heartbeat(AsyncMock(), mock_rules)
        alert_msgs = []
        async def on_alert(msg):
            alert_msgs.append(msg)
        hb.on_alert(on_alert)

        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
            health_score=45,
        )
        await hb.check_alerts(snapshot)
        assert any("Health score" in m for m in alert_msgs)

    @pytest.mark.asyncio
    async def test_no_health_alert_when_healthy(self, mock_rules):
        mock_rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
            "long_query_threshold_seconds": 30,
            "pool_alert_pct": 80,
            "connection_alert_pct": 70,
            "health_score_alert_threshold": 60,
        }.get(name, default))

        hb = Heartbeat(AsyncMock(), mock_rules)
        alert_fired = False
        async def on_alert(msg):
            nonlocal alert_fired
            if "Health score" in msg:
                alert_fired = True
        hb.on_alert(on_alert)

        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
            health_score=85,
        )
        await hb.check_alerts(snapshot)
        assert not alert_fired

    @pytest.mark.asyncio
    async def test_persist_includes_v3_columns(self, mock_rules):
        """persist() sends v3 columns to DB."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        hb = Heartbeat(pool, mock_rules)
        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=5, active_connections=3,
            max_connections=100, db_size_bytes=5000,
            cache_hit_ratio=97.5,
            top_tables_by_size=[{"table": "clients", "bytes": 1000}],
            idx_scan_ratio=88.0,
            health_score=92,
        )
        await hb.persist(snapshot)

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        sql = call_args[0]
        assert "cache_hit_ratio" in sql
        assert "top_tables_by_size" in sql
        assert "idx_scan_ratio" in sql
        assert "health_score" in sql
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_heartbeat.py -v --tb=short 2>&1 | tail -20`
Expected: FAIL — new tests fail (collect_metrics doesn't return v3 fields)

- [ ] **Step 3: Implement extended heartbeat**

Replace `heartbeat.py` `collect_metrics` method body — after existing metric collection, add:

```python
        # v3 extended metrics
        cache_hit_ratio = await self._get_cache_hit_ratio(conn)
        top_tables = await self._get_top_tables_by_size(conn)
        idx_scan_ratio = await self._get_idx_scan_ratio(conn)
        dead_tuple_ratio = await self._get_dead_tuple_ratio(conn)
```

And assign to snapshot:

```python
        snapshot = HeartbeatSnapshot(
            pool_size=pool_size, pool_idle=pool_idle,
            active_connections=active_connections, max_connections=max_connections,
            db_size_bytes=db_size_bytes, bloat_top3=bloat_top3,
            long_queries=long_queries, lock_waits=lock_waits,
            cache_hit_ratio=cache_hit_ratio,
            top_tables_by_size=top_tables,
            idx_scan_ratio=idx_scan_ratio,
        )
        snapshot.health_score = snapshot.compute_health_score(dead_tuple_ratio)
```

Add static helper methods:

```python
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
```

Add health_score alert in `check_alerts`:

```python
        health_threshold: int = self._rules.get_threshold("health_score_alert_threshold", default=60)
        if snapshot.health_score is not None and snapshot.health_score < health_threshold:
            msg = f"Health score {snapshot.health_score} below threshold {health_threshold}"
            await self.alert(msg)
            messages.append(msg)
```

Update `persist` to include v3 columns:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_heartbeat.py -v --tb=short`
Expected: 7 passed (3 existing + 4 new)

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/heartbeat.py backend/tests/services/olympus/test_heartbeat.py
git commit -m "feat(olympus): v3 heartbeat — cache_hit, table_sizes, idx_ratio, health_score"
```

---

### Task 4: InsightsCollector — Query Intelligence + Bloat Intelligence

**Files:**
- Create: `backend/services/olympus/insights.py`
- Create: `backend/tests/services/olympus/test_insights.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/olympus/test_insights.py`:

```python
"""Tests for Olympus v3 InsightsCollector."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.olympus.insights import InsightsCollector


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_threshold = MagicMock(return_value=None)
    rules.record_applied = AsyncMock()
    return rules


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


class TestQueryIntelligence:
    @pytest.mark.asyncio
    async def test_skip_when_pgss_not_available(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetchval.return_value = None  # pg_stat_statements not installed
        collector = InsightsCollector(pool, mock_rules)
        actions = await collector.collect_query_insights()
        assert len(actions) == 1
        assert actions[0].outcome == "skipped"
        assert "not available" in actions[0].reflection

    @pytest.mark.asyncio
    async def test_collects_top_queries(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1  # extension exists
        conn.fetch.side_effect = [
            # top queries
            [
                {"queryid": 123, "query": "SELECT * FROM clients", "calls": 100,
                 "total_exec_time": 5000.0, "mean_exec_time": 50.0, "rows": 1000},
            ],
            # previous insights (empty — first run)
            [],
        ]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_query_insights()
        assert any(a.action_type == "query_intelligence" and a.outcome == "success" for a in actions)
        collector._persist_insight.assert_called()

    @pytest.mark.asyncio
    async def test_detects_regression(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1  # extension exists
        conn.fetch.side_effect = [
            # top queries — mean_exec_time = 100ms
            [
                {"queryid": 123, "query": "SELECT * FROM clients", "calls": 100,
                 "total_exec_time": 10000.0, "mean_exec_time": 100.0, "rows": 1000},
            ],
            # previous insight for same queryid — mean was 50ms (>30% regression)
            [
                {"evidence": '{"mean_exec_time": 50.0, "queryid": 123}'},
            ],
        ]
        alert_msgs = []
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        collector._alert = AsyncMock(side_effect=lambda m: alert_msgs.append(m))
        actions = await collector.collect_query_insights()
        assert any(a.action_type == "query_regression" for a in actions)
        assert len(alert_msgs) > 0


class TestBloatIntelligence:
    @pytest.mark.asyncio
    async def test_detects_unused_indexes(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetch.side_effect = [
            # unused indexes: idx_scan=0, size > 1MB
            [
                {"indexrelname": "idx_old_unused", "relname": "clients",
                 "idx_scan": 0, "idx_size": 2000000},
            ],
            # tables with low idx ratio (empty for this test)
            [],
        ]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_bloat_insights()
        assert any(a.action_type == "unused_index" for a in actions)

    @pytest.mark.asyncio
    async def test_detects_missing_indexes(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetch.side_effect = [
            # unused indexes (empty)
            [],
            # tables with low idx ratio, large size
            [
                {"relname": "big_table", "seq_scan": 1000, "idx_scan": 100,
                 "table_size": 50000000, "idx_ratio": 9.1},
            ],
        ]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_bloat_insights()
        assert any(a.action_type == "missing_index" for a in actions)

    @pytest.mark.asyncio
    async def test_no_insights_when_healthy(self, mock_pool, mock_rules):
        pool, conn = mock_pool
        conn.fetch.side_effect = [
            [],  # no unused indexes
            [],  # no missing indexes
        ]
        collector = InsightsCollector(pool, mock_rules)
        collector._persist_insight = AsyncMock()
        actions = await collector.collect_bloat_insights()
        assert len(actions) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_insights.py -v --tb=short 2>&1 | tail -10`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.olympus.insights'`

- [ ] **Step 3: Implement InsightsCollector**

Create `backend/services/olympus/insights.py`:

```python
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
        self._alert: Any = None  # set by guardian

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

            # Check for regressions against previous insights
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

            # Regression detection
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
            # Unused indexes (idx_scan=0, size > 1MB)
            unused = await conn.fetch(
                "SELECT indexrelname, relname, idx_scan, "
                "pg_relation_size(indexrelid) AS idx_size "
                "FROM pg_stat_user_indexes "
                "WHERE idx_scan = 0 AND schemaname = 'public' "
                "AND pg_relation_size(indexrelid) > 1048576 "
                "ORDER BY pg_relation_size(indexrelid) DESC LIMIT 10",
            )

            # Tables with low idx_scan ratio and large size
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_insights.py -v --tb=short`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/insights.py backend/tests/services/olympus/test_insights.py
git commit -m "feat(olympus): v3 InsightsCollector — query intelligence + bloat intelligence"
```

---

### Task 5: Pulse extensions — Autovacuum Advisor + Partition-Aware Cleanup

**Files:**
- Modify: `backend/services/olympus/pulse.py`
- Modify: `backend/tests/services/olympus/test_pulse.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/services/olympus/test_pulse.py`:

```python
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
        "vacuum_dead_pct_threshold": 5,
        "audit_retention_days": 90,
    }.get(name, default))
    return rules


class TestAutovacuumAdvisor:
    @pytest.mark.asyncio
    async def test_proposes_tuning_for_untuned_table(self, mock_rules):
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.fetch.return_value = [
            {"relname": "big_table", "reloptions": None,
             "n_dead_tup": 50000, "n_tup_upd": 10000, "n_tup_ins": 5000},
        ]
        pulse = Pulse(pool, mock_rules)
        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 1
        assert actions[0].outcome == "proposed"
        assert actions[0].action_type == "autovacuum_tuning"

    @pytest.mark.asyncio
    async def test_skips_already_tuned_table(self, mock_rules):
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.fetch.return_value = [
            {"relname": "tuned_table",
             "reloptions": ["autovacuum_vacuum_scale_factor=0.02"],
             "n_dead_tup": 50000, "n_tup_upd": 10000, "n_tup_ins": 5000},
        ]
        pulse = Pulse(pool, mock_rules)
        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 0

    @pytest.mark.asyncio
    async def test_skips_low_dead_tuples(self, mock_rules):
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.fetch.return_value = [
            {"relname": "small_table", "reloptions": None,
             "n_dead_tup": 500, "n_tup_upd": 100, "n_tup_ins": 5000},
        ]
        pulse = Pulse(pool, mock_rules)
        actions = await pulse.autovacuum_advisor()
        assert len(actions) == 0


class TestPartitionAwareCleanup:
    @pytest.mark.asyncio
    async def test_delete_when_not_partitioned(self, mock_rules):
        """Falls back to DELETE when api_audit_trail is not partitioned."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.fetchval.return_value = "r"  # regular table, not partitioned
        conn.execute.return_value = "DELETE 42"

        pulse = Pulse(pool, mock_rules)
        action = await pulse.cleanup_audit_trail()
        assert action.outcome == "success"
        assert action.detail.get("method") == "delete"

    @pytest.mark.asyncio
    async def test_detach_drop_when_partitioned(self, mock_rules):
        """Uses DETACH+DROP when api_audit_trail is partitioned."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.fetchval.return_value = "p"  # partitioned table
        conn.fetch.return_value = [
            {"child_name": "api_audit_trail_2026_01"},
        ]

        pulse = Pulse(pool, mock_rules)
        action = await pulse.cleanup_audit_trail()
        assert action.outcome == "success"
        assert action.detail.get("method") == "detach_drop"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_pulse.py -v --tb=short 2>&1 | tail -15`
Expected: FAIL — `Pulse.autovacuum_advisor` not found

- [ ] **Step 3: Implement autovacuum_advisor and partition-aware cleanup**

Add to `backend/services/olympus/pulse.py`, in the `Pulse` class:

```python
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
                "suggestion": "ALTER TABLE {t} SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02)".format(t=row["relname"]),
            }
            if suggest_fillfactor:
                detail["fillfactor_suggestion"] = f"ALTER TABLE {row['relname']} SET (fillfactor = 85)"

            actions.append(PulseAction(
                action_type="autovacuum_tuning",
                target=row["relname"],
                detail=detail,
                outcome="proposed",
                reflection=f"No custom autovacuum, {row['n_dead_tup']} dead tuples",
            ))
            logger.info("Proposed autovacuum tuning for %s (%d dead tuples)", row["relname"], row["n_dead_tup"])

        return actions
```

Replace `cleanup_audit_trail` method entirely:

```python
    async def cleanup_audit_trail(self) -> PulseAction:
        retention: int = self._rules.get_threshold("audit_retention_days", default=90)
        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                # Check if api_audit_trail is partitioned
                relkind = await conn.fetchval(
                    "SELECT relkind FROM pg_class WHERE relname = 'api_audit_trail'",
                )

                if relkind == "p":
                    # Partitioned: DETACH + DROP old partitions
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
                        action_type="cleanup_audit_trail", target="api_audit_trail",
                        detail={"retention_days": retention, "method": "detach_drop",
                                "partitions_dropped": dropped},
                        outcome="success",
                        duration_ms=duration_ms,
                        rule_applied="audit_retention_days",
                    )
                else:
                    # Not partitioned: DELETE (current behavior)
                    sql = f"DELETE FROM api_audit_trail WHERE created_at < NOW() - INTERVAL '{retention} days'"
                    result = await conn.execute(sql)
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    deleted = int(result.split()[-1]) if result else 0
                    return PulseAction(
                        action_type="cleanup_audit_trail", target="api_audit_trail",
                        detail={"retention_days": retention, "rows_deleted": deleted, "method": "delete"},
                        outcome="success",
                        duration_ms=duration_ms,
                        rule_applied="audit_retention_days",
                    )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("cleanup_audit_trail failed")
            return PulseAction(
                action_type="cleanup_audit_trail", target="api_audit_trail",
                detail={"retention_days": retention},
                outcome="failure",
                duration_ms=duration_ms,
                rule_applied="audit_retention_days",
                reflection="Cleanup failed",
            )
```

Update `run_full_pulse` to include autovacuum_advisor:

```python
    async def run_full_pulse(self) -> list[PulseAction]:
        actions: list[PulseAction] = []
        actions.extend(await self.vacuum_bloated_tables())
        actions.append(await self.cleanup_audit_trail())
        actions.extend(await self.repair_sequences())
        actions.extend(await self.rebuild_invalid_indexes())
        actions.extend(await self.refresh_materialized_views())
        actions.append(await self.cleanup_expired_sessions())
        partition = await self.ensure_next_partition()
        if partition is not None:
            actions.append(partition)
        actions.extend(await self.autovacuum_advisor())
        logger.info("Full pulse: %d actions", len(actions))
        return actions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_pulse.py -v --tb=short`
Expected: 7 passed (2 existing + 5 new)

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/pulse.py backend/tests/services/olympus/test_pulse.py
git commit -m "feat(olympus): v3 pulse — autovacuum advisor + partition-aware cleanup"
```

---

### Task 6: Wire InsightsCollector into Guardian

**Files:**
- Modify: `backend/services/olympus/guardian.py`
- Modify: `backend/tests/services/olympus/test_guardian.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/services/olympus/test_guardian.py`:

```python
class TestGuardianV3Insights:
    @pytest.mark.asyncio
    async def test_pulse_runs_insights(self):
        """v3: pulse runs InsightsCollector and persists actions."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
        ])
        guardian.insights = MagicMock()
        guardian.insights.collect_query_insights = AsyncMock(return_value=[
            PulseAction(action_type="query_intelligence", target="pg_stat_statements", outcome="success"),
        ])
        guardian.insights.collect_bloat_insights = AsyncMock(return_value=[
            PulseAction(action_type="unused_index", target="idx_old", outcome="proposed"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        actions = await guardian.run_pulse_once()

        assert len(actions) == 3
        guardian.insights.collect_query_insights.assert_called_once()
        guardian.insights.collect_bloat_insights.assert_called_once()
        assert guardian._persist_action.call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/test_guardian.py::TestGuardianV3Insights -v --tb=short`
Expected: FAIL — `guardian.insights` not set

- [ ] **Step 3: Implement guardian wiring**

In `guardian.py`, add import at top:

```python
from backend.services.olympus.insights import InsightsCollector
```

In `__init__`, add:

```python
        self.insights: InsightsCollector | None = None
```

In `initialize`, after pulse creation:

```python
        self.insights = InsightsCollector(self._pool, self.rules_engine)
        self.insights.set_alert_callback(self.alerts.send_alert)
```

In `run_pulse_once`, after `actions = await self.pulse.run_full_pulse()`, add:

```python
        # v3: Insights collection
        if self.insights is not None:
            try:
                actions.extend(await self.insights.collect_query_insights())
                actions.extend(await self.insights.collect_bloat_insights())
            except Exception:
                logger.exception("Insights collection failed")
```

- [ ] **Step 4: Run all tests**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/ -v --tb=short`
Expected: 43+ passed (28 existing + 15 new)

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/guardian.py backend/tests/services/olympus/test_guardian.py
git commit -m "feat(olympus): v3 guardian — wire InsightsCollector into pulse cycle"
```

---

### Task 7: Import chain verification + full test run

**Files:** None (verification only)

- [ ] **Step 1: Verify import chain**

Run: `cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.app.dependencies import get_current_user; print('OK')"`
Expected: `OK`

- [ ] **Step 2: Run full Olympus test suite**

Run: `PYTHONPATH=. pytest backend/tests/services/olympus/ -v --tb=short`
Expected: 43+ passed, 0 failed

- [ ] **Step 3: Run RAG core tests (regression check)**

Run: `PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no`
Expected: 24 passed

- [ ] **Step 4: Final commit (if any lint fixes needed)**

```bash
git add -A
git commit -m "fix(olympus): lint fixes for v3"
```

- [ ] **Step 5: Deploy**

```bash
fly deploy --strategy rolling
```

- [ ] **Step 6: Verify health**

```bash
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool
curl -s https://nuzantara-rag.fly.dev/internal/olympus/health | python3 -m json.tool
```
