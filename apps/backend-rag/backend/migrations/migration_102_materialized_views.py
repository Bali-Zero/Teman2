"""
Migration 102: Materialized views for Olympus DB Guardian

Views:
  - mv_api_usage_daily: API endpoint usage by day (conditional — only if api_audit_trail exists)
  - mv_kg_stats: KG node/edge counts by type with avg confidence
  - mv_client_activity: Client activity summary (practices, interactions, last activity)
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "102_materialized_views"

UP_SQL = """
-- ============================================================
-- 1. mv_api_usage_daily — Conditional on api_audit_trail existence
-- ============================================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_audit_trail') THEN
    EXECUTE '
      CREATE MATERIALIZED VIEW IF NOT EXISTS mv_api_usage_daily AS
      SELECT endpoint, method, COUNT(*) AS requests,
             AVG(response_time_ms)::INTEGER AS avg_ms,
             PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)::INTEGER AS p95_ms,
             COUNT(CASE WHEN response_status >= 500 THEN 1 END) AS server_errors,
             DATE(created_at) AS date
      FROM api_audit_trail
      WHERE created_at >= CURRENT_DATE - INTERVAL ''30 days''
      GROUP BY endpoint, method, DATE(created_at)
    ';
    EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_api_usage_daily_pk ON mv_api_usage_daily (endpoint, method, date)';
  END IF;
END $$;

-- ============================================================
-- 2. mv_kg_stats — KG node/edge counts by type
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_kg_stats AS
SELECT 'nodes' AS category, entity_type AS type, COUNT(*) AS count,
       AVG(confidence)::NUMERIC(4,2) AS avg_confidence
FROM kg_nodes GROUP BY entity_type
UNION ALL
SELECT 'edges', relationship_type, COUNT(*), AVG(confidence)::NUMERIC(4,2)
FROM kg_edges GROUP BY relationship_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_kg_stats_pk ON mv_kg_stats (category, type);

-- ============================================================
-- 3. mv_client_activity — Client activity summary
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_client_activity AS
SELECT c.id AS client_id, c.full_name AS client_name, c.status,
       COUNT(DISTINCT p.id) AS practices,
       COUNT(DISTINCT i.id) AS interactions,
       MAX(i.created_at) AS last_interaction,
       MAX(p.created_at) AS last_practice
FROM clients c
LEFT JOIN practices p ON p.client_id = c.id
LEFT JOIN interactions i ON i.client_id = c.id
GROUP BY c.id, c.full_name, c.status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_client_activity_pk ON mv_client_activity (client_id);
"""

DOWN_SQL = """
DROP MATERIALIZED VIEW IF EXISTS mv_api_usage_daily;
DROP MATERIALIZED VIEW IF EXISTS mv_kg_stats;
DROP MATERIALIZED VIEW IF EXISTS mv_client_activity;
"""


async def up(pool) -> None:
    """Apply migration: create materialized views."""
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)
    logger.info("Migration %s applied successfully", MIGRATION_ID)


async def down(pool) -> None:
    """Rollback migration: drop all materialized views."""
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
    logger.info("Migration %s rolled back successfully", MIGRATION_ID)
