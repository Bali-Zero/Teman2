"""
Migration 104: Olympus v3 — heartbeat columns + pgss rule

Adds four new metric columns to olympus_heartbeats for v3 insights:
  - cache_hit_ratio: buffer cache efficiency (NUMERIC 5,2)
  - top_tables_by_size: JSON array of largest tables (JSONB)
  - idx_scan_ratio: index vs seq scan ratio (NUMERIC 5,2)
  - health_score: composite DB health score 0-100 (SMALLINT)

Also seeds two olympus_rules required by the v3 collection pipeline:
  - pgss_last_reset: tracks pg_stat_statements reset cadence (weekly)
  - health_score_alert_threshold: alert below this score (default 60)

Note: olympus_heartbeats is PARTITIONED BY RANGE (recorded_at).
ALTER TABLE ADD COLUMN IF NOT EXISTS propagates to all partitions in PG16.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "104_olympus_v3_columns"

UP_SQL = """
-- ============================================================
-- 1. New metric columns on olympus_heartbeats (partitioned)
-- ============================================================
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS cache_hit_ratio NUMERIC(5,2);
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS top_tables_by_size JSONB;
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS idx_scan_ratio NUMERIC(5,2);
ALTER TABLE olympus_heartbeats ADD COLUMN IF NOT EXISTS health_score SMALLINT;

-- ============================================================
-- 2. Seed olympus_rules for v3 schedule + threshold rules
-- ============================================================
INSERT INTO olympus_rules (rule_name, category, config, source)
VALUES (
    'pgss_last_reset',
    'schedule',
    '{"value": null, "reset_interval_hours": 168}'::jsonb,
    'v3'
)
ON CONFLICT DO NOTHING;

INSERT INTO olympus_rules (rule_name, category, config, source)
VALUES (
    'health_score_alert_threshold',
    'threshold',
    '{"value": 60}'::jsonb,
    'v3'
)
ON CONFLICT DO NOTHING;
"""

DOWN_SQL = """
-- ============================================================
-- 1. Remove v3 metric columns from olympus_heartbeats
-- ============================================================
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS cache_hit_ratio;
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS top_tables_by_size;
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS idx_scan_ratio;
ALTER TABLE olympus_heartbeats DROP COLUMN IF EXISTS health_score;

-- ============================================================
-- 2. Remove v3 rules
-- ============================================================
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
