"""
Migration 078: Add step tracking to post_publish_queue

Adds completed_steps JSONB column to track which pipeline steps succeeded,
enabling partial retry (only re-run failed steps, not the entire pipeline).
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Add completed_steps column."""
    await conn.execute("""
        ALTER TABLE post_publish_queue
        ADD COLUMN IF NOT EXISTS completed_steps JSONB DEFAULT '{}'::jsonb;
    """)
    logger.info("Migration 078: added completed_steps to post_publish_queue")


async def rollback(conn) -> None:
    """Remove completed_steps column."""
    await conn.execute("""
        ALTER TABLE post_publish_queue DROP COLUMN IF EXISTS completed_steps;
    """)
    logger.info("Migration 078: removed completed_steps from post_publish_queue")
