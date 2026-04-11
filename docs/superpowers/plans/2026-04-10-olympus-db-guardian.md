# OLIMPO — DB Guardian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Olympus DB Guardian — an integrated, self-healing, self-learning database custodian that lives inside the backend-rag service, monitors PostgreSQL health via multi-rhythm cycles, and shares wisdom across the agent ecosystem.

**Architecture:** Olympus is a Python service at `backend/services/olympus/` integrated into the FastAPI startup via `service_initializer.py`. It runs three async loops (heartbeat 5min, pulse 6h, materialized view refresh 15min) and stores its state in dedicated `olympus_*` PostgreSQL tables. External meta-cognition runs weekly on Pro via `claude --print`.

**Tech Stack:** Python 3.11+, asyncpg, FastAPI, Redis (aioredis), Pydantic v2, Telegram Bot API (via existing AlertService)

**Spec:** `docs/superpowers/specs/2026-04-10-olympus-db-guardian-design.md`

---

## File Structure

### New files to create

```
backend/services/olympus/
  __init__.py              — Package init, exports OlympusGuardian
  models.py                — Pydantic models: HeartbeatSnapshot, PulseAction, OlympusRule, Insight, Skill
  guardian.py               — OlympusGuardian: main class, multi-rhythm loop orchestrator
  heartbeat.py              — Heartbeat rhythm: metrics collection every 5min
  pulse.py                  — Pulse rhythm: maintenance actions every 6h
  rules_engine.py           — Read/apply/update rules from olympus_rules table
  alerts.py                 — Telegram alerting + proposal system via existing AlertService

backend/migrations/
  migration_100_olympus_tables.py      — DDL for olympus_* tables
  migration_101_critical_indexes.py    — Missing indexes found in audit
  migration_102_materialized_views.py  — mv_api_usage_daily, mv_kg_stats, mv_client_activity

backend/app/routers/
  olympus.py               — /health/db and /internal/olympus/* endpoints

tests/services/olympus/
  __init__.py
  test_models.py
  test_heartbeat.py
  test_pulse.py
  test_rules_engine.py
  test_guardian.py
  test_migration_100.py
```

### Existing files to modify

```
backend/app/setup/service_initializer.py:1190  — Add Olympus init after HealthMonitor
backend/app/setup/router_registration.py       — Register olympus router
backend/app/deps/database.py                   — Add get_olympus dependency
```

---

## Task 1: Migration 100 — Olympus Tables

**Files:**
- Create: `backend/migrations/migration_100_olympus_tables.py`
- Test: `tests/services/olympus/test_migration_100.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/migrations/migration_100_olympus_tables.py
"""
Migration 100: Olympus DB Guardian — Core tables for the immortal custodian.

Tables:
  - olympus_heartbeats: Metrics snapshots every 5min (partitioned by month)
  - olympus_actions: Every action taken by heartbeat/pulse/metacognition
  - olympus_rules: Evolvable operational rules with confidence scoring
  - olympus_insights: Shared wisdom accessible by all agents
  - olympus_skills: Reusable SQL procedures learned from experience (Voyager pattern)
"""

MIGRATION_ID = "100_olympus_tables"

UP_SQL = """
-- ============================================================
-- olympus_heartbeats: time-series metrics (partitioned monthly)
-- ============================================================
CREATE TABLE IF NOT EXISTS olympus_heartbeats (
    id BIGSERIAL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pool_size INTEGER,
    pool_idle INTEGER,
    pool_utilization NUMERIC(5,2),
    active_connections INTEGER,
    max_connections INTEGER,
    db_size_bytes BIGINT,
    bloat_top3 JSONB DEFAULT '[]',
    long_queries INTEGER DEFAULT 0,
    lock_waits INTEGER DEFAULT 0,
    alerts_sent INTEGER DEFAULT 0,
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

CREATE TABLE IF NOT EXISTS olympus_heartbeats_2026_04
    PARTITION OF olympus_heartbeats
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS olympus_heartbeats_2026_05
    PARTITION OF olympus_heartbeats
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS olympus_heartbeats_2026_06
    PARTITION OF olympus_heartbeats
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS olympus_heartbeats_default
    PARTITION OF olympus_heartbeats DEFAULT;

CREATE INDEX IF NOT EXISTS idx_olympus_hb_time
    ON olympus_heartbeats USING BRIN (recorded_at);

-- ============================================================
-- olympus_actions: audit trail of every guardian action
-- ============================================================
CREATE TABLE IF NOT EXISTS olympus_actions (
    id BIGSERIAL PRIMARY KEY,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rhythm TEXT NOT NULL CHECK (rhythm IN ('heartbeat', 'pulse', 'metacognition', 'council')),
    action_type TEXT NOT NULL,
    target TEXT,
    detail JSONB DEFAULT '{}',
    outcome TEXT CHECK (outcome IN ('success', 'failure', 'skipped', 'proposed')),
    duration_ms INTEGER,
    rule_applied TEXT,
    reflection TEXT
);

CREATE INDEX IF NOT EXISTS idx_olympus_actions_type_time
    ON olympus_actions (action_type, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_olympus_actions_target
    ON olympus_actions (target, executed_at DESC);

-- ============================================================
-- olympus_rules: evolvable operational rules
-- ============================================================
CREATE TABLE IF NOT EXISTS olympus_rules (
    id SERIAL PRIMARY KEY,
    rule_name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('threshold', 'schedule', 'policy', 'skill')),
    config JSONB NOT NULL,
    source TEXT NOT NULL DEFAULT 'initial',
    confidence NUMERIC(3,2) DEFAULT 1.00,
    applied_count INTEGER DEFAULT 0,
    last_applied TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    superseded_by INTEGER REFERENCES olympus_rules(id)
);

-- Seed initial rules
INSERT INTO olympus_rules (rule_name, category, config, source) VALUES
    ('vacuum_dead_pct_threshold', 'threshold', '{"value": 10, "unit": "percent"}', 'initial'),
    ('audit_retention_days', 'policy', '{"value": 90}', 'initial'),
    ('heartbeat_interval_seconds', 'schedule', '{"value": 300}', 'initial'),
    ('pulse_interval_hours', 'schedule', '{"value": 6}', 'initial'),
    ('connection_alert_pct', 'threshold', '{"value": 70, "unit": "percent"}', 'initial'),
    ('pool_alert_pct', 'threshold', '{"value": 80, "unit": "percent"}', 'initial'),
    ('long_query_threshold_seconds', 'threshold', '{"value": 30}', 'initial'),
    ('growth_anomaly_pct', 'threshold', '{"value": 20, "unit": "percent_weekly"}', 'initial'),
    ('partition_suggest_threshold', 'threshold', '{"value": 500000, "unit": "rows"}', 'initial'),
    ('mv_refresh_interval_seconds', 'schedule', '{"value": 900}', 'initial')
ON CONFLICT (rule_name) DO NOTHING;

-- ============================================================
-- olympus_insights: shared wisdom (queryable by all agents)
-- ============================================================
CREATE TABLE IF NOT EXISTS olympus_insights (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    insight_type TEXT NOT NULL CHECK (insight_type IN ('pattern', 'correlation', 'anomaly', 'recommendation', 'skill')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    evidence JSONB DEFAULT '{}',
    source TEXT NOT NULL,
    confidence NUMERIC(3,2),
    applicable_to TEXT[] DEFAULT '{}',
    accessed_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    superseded_by INTEGER REFERENCES olympus_insights(id)
);

CREATE INDEX IF NOT EXISTS idx_olympus_insights_type
    ON olympus_insights (insight_type);
CREATE INDEX IF NOT EXISTS idx_olympus_insights_applicable
    ON olympus_insights USING GIN (applicable_to);

-- ============================================================
-- olympus_skills: reusable SQL procedures (Voyager pattern)
-- ============================================================
CREATE TABLE IF NOT EXISTS olympus_skills (
    id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    sql_template TEXT NOT NULL,
    parameters JSONB DEFAULT '{}',
    preconditions TEXT[] DEFAULT '{}',
    success_criteria TEXT,
    times_used INTEGER DEFAULT 0,
    times_succeeded INTEGER DEFAULT 0,
    last_used TIMESTAMPTZ,
    learned_from TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS olympus_skills CASCADE;
DROP TABLE IF EXISTS olympus_insights CASCADE;
DROP TABLE IF EXISTS olympus_rules CASCADE;
DROP TABLE IF EXISTS olympus_actions CASCADE;
DROP TABLE IF EXISTS olympus_heartbeats_2026_04;
DROP TABLE IF EXISTS olympus_heartbeats_2026_05;
DROP TABLE IF EXISTS olympus_heartbeats_2026_06;
DROP TABLE IF EXISTS olympus_heartbeats_default;
DROP TABLE IF EXISTS olympus_heartbeats CASCADE;
"""


async def apply(conn) -> None:
    """Apply migration."""
    await conn.execute(UP_SQL)


async def rollback(conn) -> None:
    """Rollback migration."""
    await conn.execute(DOWN_SQL)
```

- [ ] **Step 2: Write test for migration**

```python
# tests/services/olympus/test_migration_100.py
"""Test that migration 100 creates all olympus tables correctly."""
import pytest


@pytest.mark.asyncio
async def test_olympus_tables_exist_in_up_sql():
    """Verify UP_SQL contains all required CREATE TABLE statements."""
    from backend.migrations.migration_100_olympus_tables import UP_SQL

    assert "olympus_heartbeats" in UP_SQL
    assert "olympus_actions" in UP_SQL
    assert "olympus_rules" in UP_SQL
    assert "olympus_insights" in UP_SQL
    assert "olympus_skills" in UP_SQL
    assert "PARTITION BY RANGE" in UP_SQL


def test_migration_id():
    from backend.migrations.migration_100_olympus_tables import MIGRATION_ID

    assert MIGRATION_ID == "100_olympus_tables"


def test_down_sql_drops_all():
    from backend.migrations.migration_100_olympus_tables import DOWN_SQL

    for table in ["olympus_skills", "olympus_insights", "olympus_rules",
                  "olympus_actions", "olympus_heartbeats"]:
        assert table in DOWN_SQL
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_migration_100.py -v`
Expected: 3 PASSED

- [ ] **Step 4: Apply migration to local DB**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python -c "
import asyncio, asyncpg
from backend.migrations.migration_100_olympus_tables import apply
async def main():
    conn = await asyncpg.connect('postgresql://nuzantara:@localhost:5432/nuzantara_dev')
    await apply(conn)
    tables = await conn.fetch(\"SELECT tablename FROM pg_tables WHERE tablename LIKE 'olympus_%'\")
    print(f'Created {len(tables)} olympus tables: {[t[\"tablename\"] for t in tables]}')
    rules = await conn.fetchval('SELECT COUNT(*) FROM olympus_rules')
    print(f'Seeded {rules} initial rules')
    await conn.close()
asyncio.run(main())
"`
Expected: `Created 5 olympus tables` (heartbeats counted once despite partitions), `Seeded 10 initial rules`

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/migration_100_olympus_tables.py tests/services/olympus/__init__.py tests/services/olympus/test_migration_100.py
git commit -m "feat(olympus): migration 100 — create olympus_* tables with partitioning and seed rules"
```

---

## Task 2: Migration 101 — Critical Missing Indexes

**Files:**
- Create: `backend/migrations/migration_101_critical_indexes.py`

- [ ] **Step 1: Write the migration**

```python
# backend/migrations/migration_101_critical_indexes.py
"""
Migration 101: Critical missing indexes found during Olympus DB audit.

Fixes:
  - conversations.session_id: primary lookup key, NO INDEX existed
  - practices.assigned_to: RBAC filter on every query
  - practices.client_id: most frequent join target
"""

MIGRATION_ID = "101_critical_indexes"

UP_SQL = """
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_session_id
    ON conversations (session_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_assigned_to
    ON practices (assigned_to) WHERE assigned_to IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_client_id
    ON practices (client_id);
"""

DOWN_SQL = """
DROP INDEX IF EXISTS idx_conversations_session_id;
DROP INDEX IF EXISTS idx_practices_assigned_to;
DROP INDEX IF EXISTS idx_practices_client_id;
"""


async def apply(conn) -> None:
    # CONCURRENTLY cannot run inside a transaction
    # Each index must be created in its own statement outside a transaction block
    for idx_sql in [
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_session_id ON conversations (session_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_assigned_to ON practices (assigned_to) WHERE assigned_to IS NOT NULL",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_client_id ON practices (client_id)",
    ]:
        await conn.execute(idx_sql)


async def rollback(conn) -> None:
    await conn.execute(DOWN_SQL)
```

- [ ] **Step 2: Apply to local DB**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python -c "
import asyncio, asyncpg
from backend.migrations.migration_101_critical_indexes import apply
async def main():
    conn = await asyncpg.connect('postgresql://nuzantara:@localhost:5432/nuzantara_dev')
    await apply(conn)
    indexes = await conn.fetch(\"SELECT indexname FROM pg_indexes WHERE indexname LIKE 'idx_conversations_session%' OR indexname LIKE 'idx_practices_%'\")
    print(f'Created indexes: {[i[\"indexname\"] for i in indexes]}')
    await conn.close()
asyncio.run(main())
"`
Expected: 3 indexes created

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/migration_101_critical_indexes.py
git commit -m "feat(olympus): migration 101 — add critical missing indexes on conversations.session_id and practices"
```

---

## Task 3: Migration 102 — Materialized Views

**Files:**
- Create: `backend/migrations/migration_102_materialized_views.py`

- [ ] **Step 1: Write the migration**

```python
# backend/migrations/migration_102_materialized_views.py
"""
Migration 102: Materialized views for dashboard performance.

Creates:
  - mv_api_usage_daily: API endpoint usage aggregated by day (replaces scanning 870K+ api_audit_trail)
  - mv_kg_stats: Knowledge graph node/edge counts by type
  - mv_client_activity: Client activity summary for CRM dashboard
"""

MIGRATION_ID = "102_materialized_views"

UP_SQL = """
-- API usage by endpoint per day (replaces full-scan on 870K+ rows)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_api_usage_daily AS
SELECT
    endpoint,
    method,
    COUNT(*) AS requests,
    AVG(response_time_ms)::INTEGER AS avg_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)::INTEGER AS p95_ms,
    COUNT(CASE WHEN response_status >= 500 THEN 1 END) AS server_errors,
    DATE(created_at) AS date
FROM api_audit_trail
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY endpoint, method, DATE(created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_api_usage_daily_pk
    ON mv_api_usage_daily (endpoint, method, date);

-- KG stats by entity/relationship type
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_kg_stats AS
SELECT 'nodes' AS category, entity_type AS type, COUNT(*) AS count,
       AVG(confidence)::NUMERIC(4,2) AS avg_confidence
FROM kg_nodes GROUP BY entity_type
UNION ALL
SELECT 'edges', relationship_type, COUNT(*), AVG(confidence)::NUMERIC(4,2)
FROM kg_edges GROUP BY relationship_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_kg_stats_pk
    ON mv_kg_stats (category, type);

-- Client activity summary for CRM dashboard
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_client_activity AS
SELECT
    c.id AS client_id,
    c.name AS client_name,
    c.status,
    COUNT(DISTINCT p.id) AS practices,
    COUNT(DISTINCT i.id) AS interactions,
    MAX(i.created_at) AS last_interaction,
    MAX(p.created_at) AS last_practice
FROM clients c
LEFT JOIN practices p ON p.client_id = c.id
LEFT JOIN interactions i ON i.client_id = c.id
GROUP BY c.id, c.name, c.status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_client_activity_pk
    ON mv_client_activity (client_id);
"""

DOWN_SQL = """
DROP MATERIALIZED VIEW IF EXISTS mv_client_activity;
DROP MATERIALIZED VIEW IF EXISTS mv_kg_stats;
DROP MATERIALIZED VIEW IF EXISTS mv_api_usage_daily;
"""


async def apply(conn) -> None:
    await conn.execute(UP_SQL)


async def rollback(conn) -> None:
    await conn.execute(DOWN_SQL)
```

- [ ] **Step 2: Apply to local DB and verify**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python -c "
import asyncio, asyncpg
from backend.migrations.migration_102_materialized_views import apply
async def main():
    conn = await asyncpg.connect('postgresql://nuzantara:@localhost:5432/nuzantara_dev')
    await apply(conn)
    mvs = await conn.fetch(\"SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'\")
    print(f'Materialized views: {[m[\"matviewname\"] for m in mvs]}')
    await conn.close()
asyncio.run(main())
"`
Expected: 3 materialized views listed

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/migration_102_materialized_views.py
git commit -m "feat(olympus): migration 102 — materialized views for API usage, KG stats, client activity"
```

---

## Task 4: Pydantic Models

**Files:**
- Create: `backend/services/olympus/__init__.py`
- Create: `backend/services/olympus/models.py`
- Test: `tests/services/olympus/test_models.py`

- [ ] **Step 1: Write the test**

```python
# tests/services/olympus/test_models.py
"""Test Olympus Pydantic models."""
import pytest
from datetime import datetime, timezone


def test_heartbeat_snapshot_defaults():
    from backend.services.olympus.models import HeartbeatSnapshot

    hb = HeartbeatSnapshot(
        pool_size=5, pool_idle=3, active_connections=10, max_connections=100,
        db_size_bytes=1_000_000_000,
    )
    assert hb.pool_utilization == pytest.approx(0.4)
    assert hb.long_queries == 0
    assert hb.alerts_sent == 0


def test_heartbeat_pool_utilization_zero_pool():
    from backend.services.olympus.models import HeartbeatSnapshot

    hb = HeartbeatSnapshot(
        pool_size=0, pool_idle=0, active_connections=0, max_connections=100,
        db_size_bytes=0,
    )
    assert hb.pool_utilization == 0.0


def test_pulse_action_valid():
    from backend.services.olympus.models import PulseAction

    action = PulseAction(
        action_type="vacuum", target="api_audit_trail",
        outcome="success", duration_ms=1200,
    )
    assert action.rhythm == "pulse"
    assert action.detail == {}


def test_olympus_rule_from_db_row():
    from backend.services.olympus.models import OlympusRule

    rule = OlympusRule(
        id=1, rule_name="vacuum_dead_pct_threshold",
        category="threshold",
        config={"value": 10, "unit": "percent"},
        source="initial", confidence=1.0,
    )
    assert rule.get_value() == 10


def test_olympus_rule_get_value_nested():
    from backend.services.olympus.models import OlympusRule

    rule = OlympusRule(
        id=2, rule_name="test", category="threshold",
        config={"value": 42, "extra": "ignored"},
        source="initial", confidence=0.8,
    )
    assert rule.get_value() == 42
    assert rule.get_value("extra") == "ignored"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.olympus'`

- [ ] **Step 3: Write the models**

```python
# backend/services/olympus/__init__.py
"""Olympus — The Immortal Database Guardian."""
```

```python
# backend/services/olympus/models.py
"""Pydantic models for the Olympus DB Guardian."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, computed_field


class HeartbeatSnapshot(BaseModel):
    """Metrics collected every heartbeat (5 min)."""

    pool_size: int
    pool_idle: int
    active_connections: int
    max_connections: int
    db_size_bytes: int
    bloat_top3: list[dict[str, Any]] = Field(default_factory=list)
    long_queries: int = 0
    lock_waits: int = 0
    alerts_sent: int = 0
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def pool_utilization(self) -> float:
        if self.pool_size == 0:
            return 0.0
        return round(1 - (self.pool_idle / self.pool_size), 2)


class PulseAction(BaseModel):
    """A single action taken during a pulse cycle."""

    rhythm: str = "pulse"
    action_type: str
    target: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    outcome: str | None = None  # success, failure, skipped, proposed
    duration_ms: int | None = None
    rule_applied: str | None = None
    reflection: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OlympusRule(BaseModel):
    """An operational rule read from olympus_rules."""

    id: int
    rule_name: str
    category: str
    config: dict[str, Any]
    source: str
    confidence: float = 1.0
    applied_count: int = 0
    last_applied: datetime | None = None
    superseded_by: int | None = None

    def get_value(self, key: str = "value") -> Any:
        """Extract a value from the config dict."""
        return self.config.get(key)


class Insight(BaseModel):
    """A piece of shared wisdom."""

    insight_type: str  # pattern, correlation, anomaly, recommendation, skill
    title: str
    content: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    confidence: float = 0.8
    applicable_to: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    """A reusable SQL procedure learned from experience (Voyager pattern)."""

    skill_name: str
    description: str
    sql_template: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    success_criteria: str | None = None
    learned_from: str | None = None
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_models.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/__init__.py backend/services/olympus/models.py tests/services/olympus/test_models.py
git commit -m "feat(olympus): pydantic models for heartbeat, pulse, rules, insights, skills"
```

---

## Task 5: Rules Engine

**Files:**
- Create: `backend/services/olympus/rules_engine.py`
- Test: `tests/services/olympus/test_rules_engine.py`

- [ ] **Step 1: Write the test**

```python
# tests/services/olympus/test_rules_engine.py
"""Test Olympus rules engine."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.olympus.models import OlympusRule


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_load_rules(mock_pool):
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool
    conn.fetch.return_value = [
        {
            "id": 1, "rule_name": "vacuum_dead_pct_threshold",
            "category": "threshold", "config": {"value": 10, "unit": "percent"},
            "source": "initial", "confidence": 1.0, "applied_count": 0,
            "last_applied": None, "superseded_by": None,
        }
    ]

    engine = RulesEngine(pool)
    await engine.load_rules()

    assert "vacuum_dead_pct_threshold" in engine.rules
    assert engine.get_threshold("vacuum_dead_pct_threshold") == 10


@pytest.mark.asyncio
async def test_get_threshold_missing_returns_default(mock_pool):
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool
    conn.fetch.return_value = []

    engine = RulesEngine(pool)
    await engine.load_rules()

    assert engine.get_threshold("nonexistent", default=42) == 42


@pytest.mark.asyncio
async def test_record_rule_applied(mock_pool):
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool
    conn.fetch.return_value = [
        {
            "id": 1, "rule_name": "test_rule", "category": "threshold",
            "config": {"value": 5}, "source": "initial", "confidence": 1.0,
            "applied_count": 3, "last_applied": None, "superseded_by": None,
        }
    ]

    engine = RulesEngine(pool)
    await engine.load_rules()
    await engine.record_applied("test_rule")

    conn.execute.assert_called_once()
    assert "applied_count" in conn.execute.call_args[0][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_rules_engine.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the rules engine**

```python
# backend/services/olympus/rules_engine.py
"""Olympus Rules Engine — reads and applies evolvable rules from olympus_rules."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.services.olympus.models import OlympusRule

logger = logging.getLogger("olympus.rules")


class RulesEngine:
    """Manages operational rules for the Olympus guardian."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.rules: dict[str, OlympusRule] = {}

    async def load_rules(self) -> None:
        """Load all active rules from the database."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, rule_name, category, config, source, confidence, "
                "applied_count, last_applied, superseded_by "
                "FROM olympus_rules WHERE superseded_by IS NULL "
                "ORDER BY rule_name"
            )
        self.rules = {
            row["rule_name"]: OlympusRule(**dict(row))
            for row in rows
        }
        logger.info("Loaded %d olympus rules", len(self.rules))

    def get_threshold(self, rule_name: str, default: Any = None) -> Any:
        """Get the 'value' from a rule's config, or default if not found."""
        rule = self.rules.get(rule_name)
        if rule is None:
            return default
        return rule.get_value() if rule.get_value() is not None else default

    def get_rule(self, rule_name: str) -> OlympusRule | None:
        """Get a rule by name."""
        return self.rules.get(rule_name)

    async def record_applied(self, rule_name: str) -> None:
        """Record that a rule was applied (increment counter, update timestamp)."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE olympus_rules SET applied_count = applied_count + 1, "
                "last_applied = $1, updated_at = $1 WHERE rule_name = $2",
                datetime.now(timezone.utc), rule_name,
            )
        rule = self.rules.get(rule_name)
        if rule:
            rule.applied_count += 1
            rule.last_applied = datetime.now(timezone.utc)

    async def lower_confidence(self, rule_name: str, delta: float = -0.1) -> None:
        """Lower a rule's confidence after repeated failures."""
        rule = self.rules.get(rule_name)
        if rule is None:
            return
        new_conf = max(0.0, round(rule.confidence + delta, 2))
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE olympus_rules SET confidence = $1, updated_at = NOW() "
                "WHERE rule_name = $2",
                new_conf, rule_name,
            )
        rule.confidence = new_conf
        logger.warning("Rule '%s' confidence lowered to %.2f", rule_name, new_conf)
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_rules_engine.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/rules_engine.py tests/services/olympus/test_rules_engine.py
git commit -m "feat(olympus): rules engine — load, apply, and evolve operational rules"
```

---

## Task 6: Heartbeat Rhythm

**Files:**
- Create: `backend/services/olympus/heartbeat.py`
- Test: `tests/services/olympus/test_heartbeat.py`

- [ ] **Step 1: Write the test**

```python
# tests/services/olympus/test_heartbeat.py
"""Test Olympus heartbeat rhythm."""
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.get_size.return_value = 5
    pool.get_idle_size.return_value = 3
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_collect_metrics(mock_pool):
    from backend.services.olympus.heartbeat import Heartbeat
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool

    # Mock DB responses
    conn.fetchval.side_effect = [
        15,     # active connections
        "100",  # max_connections (SHOW returns string)
        1_500_000_000,  # db_size_bytes
    ]
    conn.fetch.side_effect = [
        # bloat_top3
        [{"relname": "api_audit_trail", "n_dead_tup": 5000, "n_live_tup": 800000,
          "dead_pct": 0.63}],
        # long_queries
        [],
        # lock_waits
        [],
    ]

    rules = AsyncMock(spec=RulesEngine)
    rules.get_threshold.side_effect = lambda name, default=None: {
        "connection_alert_pct": 70,
        "pool_alert_pct": 80,
        "long_query_threshold_seconds": 30,
    }.get(name, default)

    hb = Heartbeat(pool, rules)
    snapshot = await hb.collect_metrics()

    assert snapshot.pool_size == 5
    assert snapshot.pool_idle == 3
    assert snapshot.active_connections == 15
    assert snapshot.db_size_bytes == 1_500_000_000
    assert len(snapshot.bloat_top3) == 1


@pytest.mark.asyncio
async def test_heartbeat_alerts_on_high_pool(mock_pool):
    from backend.services.olympus.heartbeat import Heartbeat
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool
    pool.get_size.return_value = 10
    pool.get_idle_size.return_value = 1  # 90% utilization

    conn.fetchval.side_effect = [5, "100", 1_000_000]
    conn.fetch.side_effect = [[], [], []]

    rules = AsyncMock(spec=RulesEngine)
    rules.get_threshold.return_value = 80

    hb = Heartbeat(pool, rules)
    hb.alert = AsyncMock()  # mock alert method

    snapshot = await hb.collect_metrics()
    alerts = await hb.check_alerts(snapshot)

    assert hb.alert.called
    assert snapshot.pool_utilization == 0.9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_heartbeat.py -v`
Expected: FAIL

- [ ] **Step 3: Write the heartbeat**

```python
# backend/services/olympus/heartbeat.py
"""Olympus Heartbeat — fast metrics collection every 5 minutes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import asyncpg

from backend.services.olympus.models import HeartbeatSnapshot

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.heartbeat")


class Heartbeat:
    """Collects DB health metrics and raises alerts."""

    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self.db_pool = db_pool
        self.rules = rules
        self._alert_callback: list = []

    async def alert(self, message: str) -> None:
        """Send alert to registered callbacks."""
        for cb in self._alert_callback:
            await cb(message)

    def on_alert(self, callback) -> None:
        """Register an alert callback."""
        self._alert_callback.append(callback)

    async def collect_metrics(self) -> HeartbeatSnapshot:
        """Collect a full snapshot of DB health metrics."""
        pool_size = self.db_pool.get_size()
        pool_idle = self.db_pool.get_idle_size()

        async with self.db_pool.acquire() as conn:
            active_connections = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
            max_connections_str = await conn.fetchval("SHOW max_connections")
            max_connections = int(max_connections_str)

            db_size_bytes = await conn.fetchval(
                "SELECT pg_database_size(current_database())"
            )

            bloat_rows = await conn.fetch("""
                SELECT relname, n_dead_tup, n_live_tup,
                       CASE WHEN n_live_tup > 0
                            THEN round(100.0 * n_dead_tup / n_live_tup, 2) ELSE 0
                       END AS dead_pct
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                ORDER BY n_dead_tup DESC LIMIT 3
            """)
            bloat_top3 = [dict(r) for r in bloat_rows]

            threshold = self.rules.get_threshold("long_query_threshold_seconds", default=30)
            long_query_rows = await conn.fetch(f"""
                SELECT pid FROM pg_stat_activity
                WHERE state = 'active'
                AND query_start < now() - interval '{threshold} seconds'
                AND query NOT LIKE '%pg_stat%'
            """)

            lock_rows = await conn.fetch("""
                SELECT 1 FROM pg_locks WHERE NOT granted LIMIT 10
            """)

        return HeartbeatSnapshot(
            pool_size=pool_size,
            pool_idle=pool_idle,
            active_connections=active_connections,
            max_connections=max_connections,
            db_size_bytes=db_size_bytes,
            bloat_top3=bloat_top3,
            long_queries=len(long_query_rows),
            lock_waits=len(lock_rows),
        )

    async def check_alerts(self, snapshot: HeartbeatSnapshot) -> list[str]:
        """Check thresholds and emit alerts. Returns list of alert messages."""
        alerts: list[str] = []

        pool_threshold = self.rules.get_threshold("pool_alert_pct", default=80) / 100
        if snapshot.pool_utilization > pool_threshold:
            msg = f"Pool saturation: {snapshot.pool_utilization:.0%} (threshold {pool_threshold:.0%})"
            alerts.append(msg)
            await self.alert(msg)

        conn_threshold = self.rules.get_threshold("connection_alert_pct", default=70) / 100
        conn_ratio = snapshot.active_connections / max(snapshot.max_connections, 1)
        if conn_ratio > conn_threshold:
            msg = f"Connection count high: {snapshot.active_connections}/{snapshot.max_connections}"
            alerts.append(msg)
            await self.alert(msg)

        if snapshot.long_queries > 0:
            msg = f"Long-running queries detected: {snapshot.long_queries}"
            alerts.append(msg)
            await self.alert(msg)

        snapshot.alerts_sent = len(alerts)
        return alerts

    async def persist(self, snapshot: HeartbeatSnapshot) -> None:
        """Save heartbeat snapshot to olympus_heartbeats."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO olympus_heartbeats "
                "(recorded_at, pool_size, pool_idle, pool_utilization, "
                "active_connections, max_connections, db_size_bytes, "
                "bloat_top3, long_queries, lock_waits, alerts_sent) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
                snapshot.recorded_at, snapshot.pool_size, snapshot.pool_idle,
                snapshot.pool_utilization, snapshot.active_connections,
                snapshot.max_connections, snapshot.db_size_bytes,
                snapshot.bloat_top3, snapshot.long_queries, snapshot.lock_waits,
                snapshot.alerts_sent,
            )
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_heartbeat.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/heartbeat.py tests/services/olympus/test_heartbeat.py
git commit -m "feat(olympus): heartbeat rhythm — metrics collection, alerting, persistence"
```

---

## Task 7: Pulse Rhythm

**Files:**
- Create: `backend/services/olympus/pulse.py`
- Test: `tests/services/olympus/test_pulse.py`

- [ ] **Step 1: Write the test**

```python
# tests/services/olympus/test_pulse.py
"""Test Olympus pulse rhythm."""
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.mark.asyncio
async def test_vacuum_bloated_tables(mock_pool):
    from backend.services.olympus.pulse import Pulse
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool

    # Mock: one bloated table
    conn.fetch.return_value = [{"relname": "api_audit_trail", "n_dead_tup": 50000}]
    conn.execute.return_value = "VACUUM"

    rules = AsyncMock(spec=RulesEngine)
    rules.get_threshold.return_value = 10

    pulse = Pulse(pool, rules)
    actions = await pulse.vacuum_bloated_tables()

    assert len(actions) == 1
    assert actions[0].action_type == "vacuum"
    assert actions[0].target == "api_audit_trail"
    assert actions[0].outcome == "success"
    conn.execute.assert_called_once_with("VACUUM ANALYZE api_audit_trail")


@pytest.mark.asyncio
async def test_cleanup_audit_trail(mock_pool):
    from backend.services.olympus.pulse import Pulse
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool
    conn.execute.return_value = "DELETE 1500"

    rules = AsyncMock(spec=RulesEngine)
    rules.get_threshold.return_value = 90

    pulse = Pulse(pool, rules)
    action = await pulse.cleanup_audit_trail()

    assert action.action_type == "cleanup"
    assert action.target == "api_audit_trail"


@pytest.mark.asyncio
async def test_repair_sequences(mock_pool):
    from backend.services.olympus.pulse import Pulse
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool
    # No broken sequences
    conn.fetch.return_value = []

    rules = AsyncMock(spec=RulesEngine)
    pulse = Pulse(pool, rules)
    actions = await pulse.repair_sequences()

    assert actions == []


@pytest.mark.asyncio
async def test_refresh_materialized_views(mock_pool):
    from backend.services.olympus.pulse import Pulse
    from backend.services.olympus.rules_engine import RulesEngine

    pool, conn = mock_pool
    conn.fetch.return_value = [
        {"matviewname": "mv_api_usage_daily"},
        {"matviewname": "mv_kg_stats"},
    ]
    conn.execute.return_value = "REFRESH"

    rules = AsyncMock(spec=RulesEngine)
    pulse = Pulse(pool, rules)
    actions = await pulse.refresh_materialized_views()

    assert len(actions) == 2
    assert all(a.action_type == "mv_refresh" for a in actions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_pulse.py -v`
Expected: FAIL

- [ ] **Step 3: Write the pulse**

```python
# backend/services/olympus/pulse.py
"""Olympus Pulse — maintenance actions every 6 hours."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import asyncpg

from backend.services.olympus.models import PulseAction

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.pulse")

# Tables safe for autonomous VACUUM (no DDL, just DML maintenance)
_SAFE_VACUUM_TABLES = {
    "api_audit_trail", "auth_audit_log", "kg_edges", "kg_nodes",
    "company_documents", "memory_facts", "team_timesheet",
    "whatsapp_message_context", "cell_pulse_log", "user_stats",
    "clients", "ab_test_metrics", "whatsapp_contacts", "documents",
    "query_analytics", "activity_log", "workflow_analytics",
    "cell_episodes", "conversations", "episodic_memories",
    "olympus_heartbeats", "olympus_actions",
}


class Pulse:
    """Executes maintenance actions on the database."""

    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self.db_pool = db_pool
        self.rules = rules

    async def vacuum_bloated_tables(self) -> list[PulseAction]:
        """VACUUM ANALYZE tables with dead tuple ratio above threshold."""
        threshold = self.rules.get_threshold("vacuum_dead_pct_threshold", default=10)
        actions: list[PulseAction] = []

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT relname, n_dead_tup FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                AND CASE WHEN n_live_tup > 0
                    THEN 100.0 * n_dead_tup / n_live_tup ELSE 0 END > $1
            """, float(threshold))

            for row in rows:
                table = row["relname"]
                if table not in _SAFE_VACUUM_TABLES:
                    actions.append(PulseAction(
                        action_type="vacuum_skipped", target=table,
                        detail={"reason": "not in safe list", "dead_tup": row["n_dead_tup"]},
                        outcome="skipped",
                    ))
                    continue

                t0 = time.monotonic()
                try:
                    await conn.execute(f"VACUUM ANALYZE {table}")
                    elapsed = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="vacuum", target=table,
                        detail={"dead_tup_before": row["n_dead_tup"]},
                        outcome="success", duration_ms=elapsed,
                        rule_applied="vacuum_dead_pct_threshold",
                    ))
                    logger.info("VACUUM ANALYZE %s (%d dead tuples, %dms)",
                                table, row["n_dead_tup"], elapsed)
                except Exception as e:
                    actions.append(PulseAction(
                        action_type="vacuum", target=table,
                        detail={"error": str(e)}, outcome="failure",
                    ))
                    logger.error("VACUUM %s failed: %s", table, e)

        return actions

    async def cleanup_audit_trail(self) -> PulseAction:
        """Delete old audit trail entries beyond retention period."""
        retention = self.rules.get_threshold("audit_retention_days", default=90)

        async with self.db_pool.acquire() as conn:
            t0 = time.monotonic()
            result = await conn.execute(
                f"DELETE FROM api_audit_trail WHERE created_at < NOW() - INTERVAL '{retention} days'"
            )
            elapsed = int((time.monotonic() - t0) * 1000)

        return PulseAction(
            action_type="cleanup", target="api_audit_trail",
            detail={"retention_days": retention, "result": result},
            outcome="success", duration_ms=elapsed,
            rule_applied="audit_retention_days",
        )

    async def repair_sequences(self) -> list[PulseAction]:
        """Fix sequences that are out of sync with table max IDs."""
        actions: list[PulseAction] = []

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT t.relname AS tbl, a.attname AS col,
                       pg_get_serial_sequence(t.relname, a.attname) AS seq
                FROM pg_class t
                JOIN pg_attribute a ON a.attrelid = t.oid
                WHERE pg_get_serial_sequence(t.relname, a.attname) IS NOT NULL
                  AND t.relnamespace = 'public'::regnamespace
            """)

            for row in rows:
                try:
                    max_val = await conn.fetchval(
                        f"SELECT COALESCE(MAX({row['col']}), 0) FROM {row['tbl']}"
                    )
                    seq_val = await conn.fetchval(f"SELECT last_value FROM {row['seq']}")
                    if max_val > seq_val:
                        await conn.execute(f"SELECT setval('{row['seq']}', {max_val})")
                        actions.append(PulseAction(
                            action_type="seq_repair", target=f"{row['tbl']}.{row['col']}",
                            detail={"old_val": seq_val, "new_val": max_val},
                            outcome="success",
                        ))
                        logger.warning("Fixed sequence %s: %d -> %d", row["seq"], seq_val, max_val)
                except Exception as e:
                    logger.error("Sequence check failed for %s: %s", row["tbl"], e)

        return actions

    async def rebuild_invalid_indexes(self) -> list[PulseAction]:
        """Rebuild any invalid indexes."""
        actions: list[PulseAction] = []

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT indexrelid::regclass AS idx FROM pg_index WHERE NOT indisvalid"
            )
            for row in rows:
                idx_name = str(row["idx"])
                t0 = time.monotonic()
                try:
                    await conn.execute(f"REINDEX INDEX CONCURRENTLY {idx_name}")
                    elapsed = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="reindex", target=idx_name,
                        outcome="success", duration_ms=elapsed,
                    ))
                except Exception as e:
                    actions.append(PulseAction(
                        action_type="reindex", target=idx_name,
                        detail={"error": str(e)}, outcome="failure",
                    ))

        return actions

    async def refresh_materialized_views(self) -> list[PulseAction]:
        """Refresh all materialized views with CONCURRENTLY."""
        actions: list[PulseAction] = []

        async with self.db_pool.acquire() as conn:
            mvs = await conn.fetch(
                "SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'"
            )
            for mv in mvs:
                name = mv["matviewname"]
                t0 = time.monotonic()
                try:
                    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {name}")
                    elapsed = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="mv_refresh", target=name,
                        outcome="success", duration_ms=elapsed,
                    ))
                except Exception as e:
                    # CONCURRENTLY may fail if no unique index — fall back to regular refresh
                    try:
                        await conn.execute(f"REFRESH MATERIALIZED VIEW {name}")
                        elapsed = int((time.monotonic() - t0) * 1000)
                        actions.append(PulseAction(
                            action_type="mv_refresh", target=name,
                            detail={"fallback": "non-concurrent"},
                            outcome="success", duration_ms=elapsed,
                        ))
                    except Exception as e2:
                        actions.append(PulseAction(
                            action_type="mv_refresh", target=name,
                            detail={"error": str(e2)}, outcome="failure",
                        ))

        return actions

    async def cleanup_expired_sessions(self) -> PulseAction:
        """Clean up expired persistent sessions."""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM persistent_sessions WHERE updated_at < NOW() - INTERVAL '30 days'"
            )
        return PulseAction(
            action_type="cleanup", target="persistent_sessions",
            detail={"result": result}, outcome="success",
        )

    async def ensure_next_partition(self) -> PulseAction | None:
        """Create next month's heartbeat partition if it doesn't exist."""
        async with self.db_pool.acquire() as conn:
            next_start = await conn.fetchval(
                "SELECT date_trunc('month', NOW() + INTERVAL '1 month')::date"
            )
            next_end = await conn.fetchval(
                "SELECT date_trunc('month', NOW() + INTERVAL '2 months')::date"
            )
            partition_name = f"olympus_heartbeats_{next_start.strftime('%Y_%m')}"

            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_class WHERE relname = $1)",
                partition_name,
            )
            if exists:
                return None

            await conn.execute(
                f"CREATE TABLE IF NOT EXISTS {partition_name} "
                f"PARTITION OF olympus_heartbeats "
                f"FOR VALUES FROM ('{next_start}') TO ('{next_end}')"
            )
            logger.info("Created partition %s", partition_name)
            return PulseAction(
                action_type="partition_created", target=partition_name,
                outcome="success",
            )

    async def run_full_pulse(self) -> list[PulseAction]:
        """Execute a complete pulse cycle. Returns all actions taken."""
        actions: list[PulseAction] = []

        actions.extend(await self.vacuum_bloated_tables())
        actions.append(await self.cleanup_audit_trail())
        actions.extend(await self.repair_sequences())
        actions.extend(await self.rebuild_invalid_indexes())
        actions.extend(await self.refresh_materialized_views())
        actions.append(await self.cleanup_expired_sessions())

        partition_action = await self.ensure_next_partition()
        if partition_action:
            actions.append(partition_action)

        return actions
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_pulse.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/pulse.py tests/services/olympus/test_pulse.py
git commit -m "feat(olympus): pulse rhythm — vacuum, cleanup, sequence repair, MV refresh, partitioning"
```

---

## Task 8: Alerts Integration

**Files:**
- Create: `backend/services/olympus/alerts.py`

- [ ] **Step 1: Write the alerts module**

```python
# backend/services/olympus/alerts.py
"""Olympus Alerts — Telegram integration for alerts and proposals."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.monitoring.alert_service import AlertLevel, AlertService

if TYPE_CHECKING:
    pass

logger = logging.getLogger("olympus.alerts")


class OlympusAlerts:
    """Sends alerts and proposals to Zero via Telegram."""

    def __init__(self, alert_service: AlertService) -> None:
        self.alert_service = alert_service

    async def send_alert(self, message: str, level: AlertLevel = AlertLevel.WARNING) -> None:
        """Send an alert to Telegram."""
        formatted = f"[OLIMPO] {message}"
        await self.alert_service.send_alert(
            title="Olympus DB Guardian",
            message=formatted,
            level=level,
        )

    async def send_proposal(self, title: str, detail: str) -> None:
        """Send a structural proposal to Zero for approval."""
        formatted = (
            f"[OLIMPO PROPOSTA]\n\n"
            f"{title}\n\n"
            f"{detail}\n\n"
            f"Rispondi per approvare o rifiutare."
        )
        await self.alert_service.send_alert(
            title="Olympus Proposal",
            message=formatted,
            level=AlertLevel.INFO,
        )

    async def send_pulse_summary(self, actions_count: int, failures: int) -> None:
        """Send a brief summary after each pulse."""
        if failures > 0:
            level = AlertLevel.WARNING
            msg = f"Pulse completato: {actions_count} azioni, {failures} fallimenti"
        else:
            level = AlertLevel.INFO
            msg = f"Pulse completato: {actions_count} azioni, tutto OK"
        await self.send_alert(msg, level)
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/olympus/alerts.py
git commit -m "feat(olympus): telegram alerts integration via existing AlertService"
```

---

## Task 9: OlympusGuardian — Main Orchestrator

**Files:**
- Create: `backend/services/olympus/guardian.py`
- Test: `tests/services/olympus/test_guardian.py`

- [ ] **Step 1: Write the test**

```python
# tests/services/olympus/test_guardian.py
"""Test OlympusGuardian orchestrator."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_guardian_initialize():
    from backend.services.olympus.guardian import OlympusGuardian

    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.fetch.return_value = []  # no rules yet
    conn.fetchval.return_value = True  # table exists check

    alert_service = MagicMock()

    guardian = OlympusGuardian(db_pool=pool, alert_service=alert_service)
    await guardian.initialize()

    assert guardian.rules_engine is not None
    assert guardian.heartbeat is not None
    assert guardian.pulse is not None


@pytest.mark.asyncio
async def test_guardian_single_heartbeat():
    from backend.services.olympus.guardian import OlympusGuardian

    pool = AsyncMock()
    pool.get_size.return_value = 5
    pool.get_idle_size.return_value = 3

    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # For initialize: rules load
    conn.fetch.return_value = []
    conn.fetchval.return_value = True

    alert_service = MagicMock()

    guardian = OlympusGuardian(db_pool=pool, alert_service=alert_service)
    await guardian.initialize()

    # Mock heartbeat methods
    guardian.heartbeat.collect_metrics = AsyncMock(return_value=MagicMock(
        pool_size=5, pool_idle=3, pool_utilization=0.4,
        active_connections=10, max_connections=100,
        db_size_bytes=1_000_000, alerts_sent=0,
        bloat_top3=[], long_queries=0, lock_waits=0,
        recorded_at=MagicMock(),
    ))
    guardian.heartbeat.check_alerts = AsyncMock(return_value=[])
    guardian.heartbeat.persist = AsyncMock()

    await guardian.run_heartbeat_once()

    guardian.heartbeat.collect_metrics.assert_called_once()
    guardian.heartbeat.check_alerts.assert_called_once()
    guardian.heartbeat.persist.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_guardian.py -v`
Expected: FAIL

- [ ] **Step 3: Write the guardian**

```python
# backend/services/olympus/guardian.py
"""OlympusGuardian — The Immortal Database Custodian.

Multi-rhythm orchestrator:
  - Heartbeat: every 5 min (metrics, alerts)
  - Pulse: every 6h (vacuum, cleanup, repair, refresh)
  - Partition check: with pulse (ensure next month's partition exists)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg

from backend.services.monitoring.alert_service import AlertService
from backend.services.olympus.alerts import OlympusAlerts
from backend.services.olympus.heartbeat import Heartbeat
from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse
from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.guardian")


class OlympusGuardian:
    """The Olympus DB Guardian — integrated, self-healing, self-learning."""

    def __init__(self, db_pool: asyncpg.Pool, alert_service: AlertService) -> None:
        self.db_pool = db_pool
        self.alerts = OlympusAlerts(alert_service)
        self.rules_engine: RulesEngine | None = None
        self.heartbeat: Heartbeat | None = None
        self.pulse: Pulse | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def initialize(self) -> None:
        """Initialize all sub-components. Call once at startup."""
        self.rules_engine = RulesEngine(self.db_pool)
        await self.rules_engine.load_rules()

        self.heartbeat = Heartbeat(self.db_pool, self.rules_engine)
        self.heartbeat.on_alert(self.alerts.send_alert)

        self.pulse = Pulse(self.db_pool, self.rules_engine)

        logger.info("Olympus Guardian initialized (%d rules loaded)", len(self.rules_engine.rules))

    async def run_heartbeat_once(self) -> None:
        """Execute a single heartbeat cycle."""
        snapshot = await self.heartbeat.collect_metrics()
        await self.heartbeat.check_alerts(snapshot)
        await self.heartbeat.persist(snapshot)

    async def run_pulse_once(self) -> list[PulseAction]:
        """Execute a single pulse cycle."""
        actions = await self.pulse.run_full_pulse()

        # Persist all actions
        async with self.db_pool.acquire() as conn:
            for action in actions:
                await conn.execute(
                    "INSERT INTO olympus_actions "
                    "(executed_at, rhythm, action_type, target, detail, outcome, "
                    "duration_ms, rule_applied, reflection) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                    action.executed_at, action.rhythm, action.action_type,
                    action.target, action.detail, action.outcome,
                    action.duration_ms, action.rule_applied, action.reflection,
                )

        # Record rules applied
        for action in actions:
            if action.rule_applied:
                await self.rules_engine.record_applied(action.rule_applied)

        # Reflexion: count outcomes
        failures = sum(1 for a in actions if a.outcome == "failure")
        await self.alerts.send_pulse_summary(len(actions), failures)

        logger.info(
            "Pulse complete: %d actions (%d success, %d failure, %d skipped)",
            len(actions),
            sum(1 for a in actions if a.outcome == "success"),
            failures,
            sum(1 for a in actions if a.outcome == "skipped"),
        )
        return actions

    async def _heartbeat_loop(self) -> None:
        """Background loop for heartbeat rhythm."""
        interval = self.rules_engine.get_threshold("heartbeat_interval_seconds", default=300)
        while self._running:
            try:
                await self.run_heartbeat_once()
            except Exception as e:
                logger.error("Heartbeat failed: %s", e)
            await asyncio.sleep(interval)

    async def _pulse_loop(self) -> None:
        """Background loop for pulse rhythm."""
        interval = self.rules_engine.get_threshold("pulse_interval_hours", default=6) * 3600
        # Initial delay: wait 60s after startup before first pulse
        await asyncio.sleep(60)
        while self._running:
            try:
                await self.run_pulse_once()
            except Exception as e:
                logger.error("Pulse failed: %s", e)
                await self.alerts.send_alert(f"Pulse FAILED: {e}")
            await asyncio.sleep(interval)

    async def start(self) -> None:
        """Start all rhythm loops as background tasks."""
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop(), name="olympus-heartbeat"),
            asyncio.create_task(self._pulse_loop(), name="olympus-pulse"),
        ]
        logger.info("Olympus Guardian started (heartbeat + pulse)")

    async def stop(self) -> None:
        """Stop all rhythm loops."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Olympus Guardian stopped")

    async def get_health_summary(self) -> dict[str, Any]:
        """Return current health summary for /health/db endpoint."""
        async with self.db_pool.acquire() as conn:
            last_hb = await conn.fetchrow(
                "SELECT * FROM olympus_heartbeats ORDER BY recorded_at DESC LIMIT 1"
            )
            recent_actions = await conn.fetch(
                "SELECT action_type, target, outcome, executed_at "
                "FROM olympus_actions ORDER BY executed_at DESC LIMIT 10"
            )
            rules_count = await conn.fetchval("SELECT COUNT(*) FROM olympus_rules")

        return {
            "status": "alive",
            "last_heartbeat": dict(last_hb) if last_hb else None,
            "recent_actions": [dict(r) for r in recent_actions],
            "rules_loaded": rules_count,
            "running": self._running,
        }
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/test_guardian.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/guardian.py tests/services/olympus/test_guardian.py
git commit -m "feat(olympus): OlympusGuardian orchestrator — multi-rhythm loop with heartbeat + pulse"
```

---

## Task 10: Router + Dependencies + Service Initializer Wiring

**Files:**
- Create: `backend/app/routers/olympus.py`
- Modify: `backend/app/deps/database.py:56` — add `get_olympus` dependency
- Modify: `backend/app/setup/service_initializer.py:1190` — add Olympus init
- Modify: `backend/app/setup/router_registration.py` — register olympus router

- [ ] **Step 1: Create the router**

```python
# backend/app/routers/olympus.py
"""Olympus DB Guardian — health and management endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.app.deps.database import get_database_pool

logger = logging.getLogger("olympus.router")

router = APIRouter(prefix="/health", tags=["olympus"])


@router.get("/db")
async def db_health(request: Request) -> dict[str, Any]:
    """Database health summary from Olympus Guardian."""
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return {"status": "not_initialized", "detail": "Olympus Guardian not running"}
    return await olympus.get_health_summary()


internal_router = APIRouter(prefix="/internal/olympus", tags=["olympus-internal"])


@internal_router.post("/pulse")
async def trigger_pulse(request: Request) -> dict[str, Any]:
    """Manually trigger a pulse cycle."""
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return {"error": "Olympus not initialized"}
    actions = await olympus.run_pulse_once()
    return {
        "actions": len(actions),
        "successes": sum(1 for a in actions if a.outcome == "success"),
        "failures": sum(1 for a in actions if a.outcome == "failure"),
    }


@internal_router.get("/rules")
async def list_rules(request: Request) -> list[dict[str, Any]]:
    """List all active Olympus rules."""
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return []
    return [r.model_dump() for r in olympus.rules_engine.rules.values()]
```

- [ ] **Step 2: Add Olympus init to service_initializer.py**

Add after line 1190 (after HealthMonitor init), before step 12 (LangGraph):

```python
    # 10c. Olympus DB Guardian
    if db_pool:
        try:
            from backend.services.olympus.guardian import OlympusGuardian

            olympus = OlympusGuardian(db_pool=db_pool, alert_service=alert_service)
            await olympus.initialize()
            await olympus.start()
            app.state.olympus = olympus
            service_registry.register("olympus", ServiceStatus.HEALTHY, critical=False)
            logger.info("✅ Olympus DB Guardian: Active (heartbeat + pulse)")
        except Exception as e:
            service_registry.register(
                "olympus", ServiceStatus.DEGRADED, error=str(e), critical=False,
            )
            logger.error(f"❌ Failed to initialize Olympus: {e}")
    else:
        logger.warning("⚠️ Olympus skipped: no db_pool")
```

- [ ] **Step 3: Register router in router_registration.py**

Find where other routers are registered and add:

```python
from backend.app.routers.olympus import router as olympus_router, internal_router as olympus_internal_router

app.include_router(olympus_router)
app.include_router(olympus_internal_router)
```

- [ ] **Step 4: Run import chain validation**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && python -c "from backend.services.olympus.guardian import OlympusGuardian; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Run all Olympus tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest tests/services/olympus/ -v`
Expected: All PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/olympus.py backend/app/deps/database.py backend/app/setup/service_initializer.py backend/app/setup/router_registration.py
git commit -m "feat(olympus): wire guardian into FastAPI — /health/db endpoint, service initializer, router registration"
```

---

## Task 11: Apply Migrations to Fly (Production)

- [ ] **Step 1: Run pre-deploy checks**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest tests/services/olympus/ -v --tb=short
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no
```

- [ ] **Step 2: Apply migration 100 to Fly via proxy**

```bash
# Ensure proxy is running
fly proxy 15432:5432 -a nuzantara-postgres &
sleep 3

cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg
from backend.migrations.migration_100_olympus_tables import apply
async def main():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable')
    await apply(conn)
    tables = await conn.fetch(\"SELECT tablename FROM pg_tables WHERE tablename LIKE 'olympus_%'\")
    print(f'Fly: Created {len(tables)} tables: {[t[\"tablename\"] for t in tables]}')
    await conn.close()
asyncio.run(main())
"
```

- [ ] **Step 3: Apply migration 101 (indexes) to Fly**

```bash
PYTHONPATH=. python -c "
import asyncio, asyncpg
from backend.migrations.migration_101_critical_indexes import apply
async def main():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable')
    await apply(conn)
    print('Fly: Indexes created')
    await conn.close()
asyncio.run(main())
"
```

- [ ] **Step 4: Apply migration 102 (materialized views) to Fly**

```bash
PYTHONPATH=. python -c "
import asyncio, asyncpg
from backend.migrations.migration_102_materialized_views import apply
async def main():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable')
    await apply(conn)
    mvs = await conn.fetch(\"SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'\")
    print(f'Fly: MVs created: {[m[\"matviewname\"] for m in mvs]}')
    await conn.close()
asyncio.run(main())
"
```

- [ ] **Step 5: Deploy backend to Fly**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
fly deploy --strategy rolling
```

- [ ] **Step 6: Verify Olympus is alive**

```bash
curl -s https://nuzantara-rag.fly.dev/health/db | python3 -m json.tool
```
Expected: `{"status": "alive", "last_heartbeat": {...}, ...}`

- [ ] **Step 7: Commit deploy marker**

```bash
git add -A
git commit -m "deploy(olympus): migrations 100-102 applied to Fly, Olympus Guardian live"
```

---

## Summary

| Task | What | Files | Tests |
|---|---|---|---|
| 1 | Migration 100: olympus tables | 1 new | 1 test file |
| 2 | Migration 101: missing indexes | 1 new | manual verify |
| 3 | Migration 102: materialized views | 1 new | manual verify |
| 4 | Pydantic models | 2 new | 1 test file |
| 5 | Rules engine | 1 new | 1 test file |
| 6 | Heartbeat rhythm | 1 new | 1 test file |
| 7 | Pulse rhythm | 1 new | 1 test file |
| 8 | Alerts integration | 1 new | — |
| 9 | Guardian orchestrator | 1 new | 1 test file |
| 10 | Router + wiring | 1 new + 3 modified | import chain |
| 11 | Fly deploy | — | production verify |

**Total: 11 new files, 3 modified, 6 test files, 11 tasks.**

Phases 3-5 from the spec (Reflexion loop, meta-cognition, Consiglio dell'Olimpo) are designed as **follow-up plans** after Phase 1-2 is live and collecting data. The meta-cognition requires accumulated heartbeat/pulse data to analyze.
