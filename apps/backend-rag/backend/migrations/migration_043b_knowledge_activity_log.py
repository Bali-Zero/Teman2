"""
Migration 043: Knowledge Activity Log

Creates table for tracking knowledge base views and downloads.

Created: 2026-01-13
"""

import asyncio
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create knowledge activity log table."""

    logger.info("Applying migration 043: Knowledge Activity Log")

    # Create knowledge_activity_log table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_activity_log (
            id SERIAL PRIMARY KEY,
            user_email TEXT NOT NULL,
            action_type VARCHAR(50) NOT NULL,  -- 'view' or 'download'
            resource_type VARCHAR(50) NOT NULL,  -- 'visa', 'article', 'document', etc.
            resource_id VARCHAR(255),
            resource_title TEXT,
            resource_category VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_activity_user
        ON knowledge_activity_log(user_email);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_activity_created
        ON knowledge_activity_log(created_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_activity_type
        ON knowledge_activity_log(action_type);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_knowledge_activity_resource
        ON knowledge_activity_log(resource_type, resource_id);
    """)

    logger.info("Migration 043 applied successfully")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop knowledge activity log table."""

    logger.info("Rolling back migration 043: Knowledge Activity Log")

    await conn.execute("DROP TABLE IF EXISTS knowledge_activity_log;")

    logger.info("Migration 043 rolled back successfully")


async def run_migration():
    """Run migration directly."""
    from backend.app.core.config import settings

    if not settings.database_url:
        print("ERROR: DATABASE_URL not found")
        return False

    try:
        print("Connecting to PostgreSQL...")
        conn = await asyncpg.connect(settings.database_url)
        print("Connected")

        await apply(conn)

        await conn.close()
        print("Migration 043 completed successfully!")
        return True

    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys

    result = asyncio.run(run_migration())
    sys.exit(0 if result else 1)
