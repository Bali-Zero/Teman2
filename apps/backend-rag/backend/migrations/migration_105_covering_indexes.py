"""
Migration 105: Covering indexes + v4 readiness rule

Closes GAP-12 (covering indexes for dashboard queries) and
seeds v4_insights_threshold rule for Voyager activation.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "105_covering_indexes"

UP_SQL = """
-- Covering indexes for common dashboard queries (index-only scans)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_status_covering
    ON clients (status) INCLUDE (full_name, email);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_status_covering
    ON practices (status, created_at DESC) INCLUDE (client_id, practice_type_code);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interactions_client_covering
    ON interactions (client_id, created_at DESC) INCLUDE (interaction_type, channel);

-- v4 readiness threshold rule
INSERT INTO olympus_rules (rule_name, category, config, source)
VALUES ('v4_insights_threshold', 'threshold', '{"value": 500}', 'v3')
ON CONFLICT (rule_name) DO NOTHING;
"""

DOWN_SQL = """
DROP INDEX IF EXISTS idx_clients_status_covering;
DROP INDEX IF EXISTS idx_practices_status_covering;
DROP INDEX IF EXISTS idx_interactions_client_covering;
DELETE FROM olympus_rules WHERE rule_name = 'v4_insights_threshold';
"""


async def upgrade(conn) -> None:
    logger.info("Applying migration %s ...", MIGRATION_ID)
    # CONCURRENTLY requires running outside transaction
    for stmt in UP_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            await conn.execute(stmt)
    logger.info("Migration %s applied successfully", MIGRATION_ID)


async def downgrade(conn) -> None:
    logger.info("Rolling back migration %s ...", MIGRATION_ID)
    await conn.execute(DOWN_SQL)
    logger.info("Migration %s rolled back", MIGRATION_ID)
