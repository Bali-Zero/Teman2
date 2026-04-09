"""
Migration 100: Olympus DB Guardian — Core tables

Tables:
  - olympus_heartbeats: Time-series metrics (partitioned by month)
  - olympus_actions: Audit trail of all guardian actions
  - olympus_rules: Evolvable rules with confidence tracking
  - olympus_insights: Shared wisdom / pattern repository
  - olympus_skills: Reusable SQL procedures (Voyager pattern)

Seeds 10 initial rules with ON CONFLICT DO NOTHING.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "100_olympus_tables"

UP_SQL = """
-- ============================================================
-- 1. olympus_heartbeats — Partitioned by RANGE (recorded_at)
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

-- Monthly partitions
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

-- BRIN index on recorded_at (optimal for time-series append-only)
CREATE INDEX IF NOT EXISTS idx_olympus_heartbeats_recorded_brin
    ON olympus_heartbeats USING BRIN (recorded_at);

-- ============================================================
-- 2. olympus_actions — Audit trail
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

CREATE INDEX IF NOT EXISTS idx_olympus_actions_target_time
    ON olympus_actions (target, executed_at DESC);

-- ============================================================
-- 3. olympus_rules — Evolvable rules with confidence
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

-- ============================================================
-- 4. olympus_insights — Shared wisdom
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

CREATE INDEX IF NOT EXISTS idx_olympus_insights_applicable_gin
    ON olympus_insights USING GIN (applicable_to);

-- ============================================================
-- 5. olympus_skills — Reusable SQL procedures (Voyager pattern)
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

-- ============================================================
-- Seed initial rules
-- ============================================================
INSERT INTO olympus_rules (rule_name, category, config, source)
VALUES
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
"""

DOWN_SQL = """
DROP TABLE IF EXISTS olympus_skills;
DROP TABLE IF EXISTS olympus_insights;
DROP TABLE IF EXISTS olympus_actions;
DROP TABLE IF EXISTS olympus_rules;
DROP TABLE IF EXISTS olympus_heartbeats_2026_04;
DROP TABLE IF EXISTS olympus_heartbeats_2026_05;
DROP TABLE IF EXISTS olympus_heartbeats_2026_06;
DROP TABLE IF EXISTS olympus_heartbeats_default;
DROP TABLE IF EXISTS olympus_heartbeats;
"""


async def up(pool) -> None:
    """Apply migration: create olympus_* tables and seed rules."""
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)
    logger.info("Migration %s applied successfully", MIGRATION_ID)


async def down(pool) -> None:
    """Rollback migration: drop all olympus_* tables."""
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
    logger.info("Migration %s rolled back successfully", MIGRATION_ID)
