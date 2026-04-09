"""
Migration 103: PostgreSQL production tuning

Based on full DB audit (2026-04-10). Closes 3 critical gaps:
  1. Enable pg_stat_statements extension (query observability)
  2. Per-table autovacuum tuning for high-churn tables (reduce bloat 5-10x)
  3. fillfactor for high-UPDATE tables (enable HOT updates)
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "103_pg_tuning"

UP_SQL = """
-- ============================================================
-- 1. pg_stat_statements — query observability (requires shared_preload_libraries)
-- ============================================================
-- NOTE: shared_preload_libraries must include 'pg_stat_statements' (PG restart required).
-- If not configured, CREATE EXTENSION will fail gracefully via IF NOT EXISTS + DO block.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
  RAISE NOTICE 'pg_stat_statements extension enabled';
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'pg_stat_statements not available (shared_preload_libraries not configured): %', SQLERRM;
END
$$;

-- ============================================================
-- 2. Per-table autovacuum tuning — high-churn tables
-- ============================================================
-- Default is scale_factor=0.2 (20% dead tuples before vacuum).
-- For high-churn tables, this is far too late. Tune individually.

-- KG tables: heavy JSONB append (properties || $1::jsonb)
ALTER TABLE kg_edges SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_analyze_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 100
);
ALTER TABLE kg_nodes SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_analyze_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 100
);

-- Conversations: frequent message array appends
ALTER TABLE conversations SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 200
);

-- Conversation messages: append-only, high volume
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversation_messages') THEN
    EXECUTE 'ALTER TABLE conversation_messages SET (
        autovacuum_vacuum_scale_factor = 0.05,
        autovacuum_analyze_scale_factor = 0.02,
        autovacuum_vacuum_threshold = 200
    )';
  END IF;
END $$;

-- API audit trail: high volume, 90-day retention DELETE generates bloat
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_audit_trail') THEN
    EXECUTE 'ALTER TABLE api_audit_trail SET (
        autovacuum_vacuum_scale_factor = 0.05,
        autovacuum_analyze_scale_factor = 0.02,
        autovacuum_vacuum_threshold = 500
    )';
  END IF;
END $$;

-- Olympus heartbeats: append-only time-series
ALTER TABLE olympus_heartbeats SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- Olympus actions: append-only audit trail
ALTER TABLE olympus_actions SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- Clients: moderate update frequency (status changes, metadata)
ALTER TABLE clients SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- Practices: status state machine, frequent updates
ALTER TABLE practices SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- ============================================================
-- 3. fillfactor for high-UPDATE tables (enables HOT updates)
-- ============================================================
-- Leaves free space per page so UPDATEs can stay on the same page (no index update needed)
ALTER TABLE conversations SET (fillfactor = 85);
ALTER TABLE kg_edges SET (fillfactor = 85);
ALTER TABLE kg_nodes SET (fillfactor = 90);
ALTER TABLE clients SET (fillfactor = 90);
ALTER TABLE practices SET (fillfactor = 90);
"""

DOWN_SQL = """
-- Reset autovacuum to defaults
ALTER TABLE kg_edges RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor, autovacuum_vacuum_threshold);
ALTER TABLE kg_nodes RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor, autovacuum_vacuum_threshold);
ALTER TABLE conversations RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor, autovacuum_vacuum_threshold);
ALTER TABLE olympus_heartbeats RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor);
ALTER TABLE olympus_actions RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor);
ALTER TABLE clients RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor);
ALTER TABLE practices RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversation_messages') THEN
    EXECUTE 'ALTER TABLE conversation_messages RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor, autovacuum_vacuum_threshold)';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_audit_trail') THEN
    EXECUTE 'ALTER TABLE api_audit_trail RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor, autovacuum_vacuum_threshold)';
  END IF;
END $$;

-- Reset fillfactor to default (100)
ALTER TABLE conversations SET (fillfactor = 100);
ALTER TABLE kg_edges SET (fillfactor = 100);
ALTER TABLE kg_nodes SET (fillfactor = 100);
ALTER TABLE clients SET (fillfactor = 100);
ALTER TABLE practices SET (fillfactor = 100);

-- pg_stat_statements: leave extension (harmless to keep)
"""


async def upgrade(conn) -> None:
    logger.info("Applying migration %s ...", MIGRATION_ID)
    await conn.execute(UP_SQL)
    logger.info("Migration %s applied successfully", MIGRATION_ID)


async def downgrade(conn) -> None:
    logger.info("Rolling back migration %s ...", MIGRATION_ID)
    await conn.execute(DOWN_SQL)
    logger.info("Migration %s rolled back", MIGRATION_ID)
