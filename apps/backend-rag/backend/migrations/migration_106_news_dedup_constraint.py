"""
Migration 106: News items — dedup constraint + title index

Adds a unique partial index on (title, source) for approved news to prevent
the scraper from re-ingesting the same article multiple times.

Also adds a covering index on (status, published_at DESC) used by the list
endpoint to avoid seq scans as the table grows.

Note: uses UNIQUE INDEX (not UNIQUE constraint) so it can be partial.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "106_news_dedup_constraint"

UP_SQL = """
-- ============================================================
-- 1. Unique partial index: prevent duplicate title+source
--    Only enforced for approved items (active content).
-- ============================================================
CREATE UNIQUE INDEX IF NOT EXISTS uix_news_items_title_source
    ON news_items (title, source)
    WHERE status = 'approved';

-- ============================================================
-- 2. Covering index for list endpoint (status filter + sort)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_news_items_status_published
    ON news_items (status, published_at DESC);
"""

DOWN_SQL = """
DROP INDEX IF EXISTS uix_news_items_title_source;
DROP INDEX IF EXISTS idx_news_items_status_published;
"""


async def upgrade(conn) -> None:
    logger.info("Applying migration %s ...", MIGRATION_ID)
    await conn.execute(UP_SQL)
    logger.info("Migration %s applied successfully", MIGRATION_ID)


async def downgrade(conn) -> None:
    logger.info("Rolling back migration %s ...", MIGRATION_ID)
    await conn.execute(DOWN_SQL)
    logger.info("Migration %s rolled back", MIGRATION_ID)
