#!/usr/bin/env python3
"""
Migration 026: Review Queue System
Adds review_queue table for feedback correction logic
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from backend.db.migration_base import BaseMigration

logger = logging.getLogger(__name__)


class Migration026(BaseMigration):
    """Review Queue System Migration"""

    def __init__(self):
        super().__init__(
            migration_number=26,
            sql_file="026_review_queue.sql",
            description="Add review_queue table for feedback correction logic",
            dependencies=[25],  # Depends on migration 025 (conversation_ratings)
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify review_queue table was created"""
        # Check review_queue table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'review_queue'
            )
            """
        )

        if not table_exists:
            logger.error("review_queue table not found")
            return False

        # Check required columns exist
        required_columns = [
            "id",
            "source_feedback_id",
            "status",
            "priority",
            "created_at",
        ]
        for col in required_columns:
            col_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'review_queue' AND column_name = $1
                )
                """,
                col,
            )
            if not col_exists:
                logger.error(f"Column {col} not found in review_queue")
                return False

        # Check indexes exist
        indexes = await conn.fetch(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'review_queue'
            """
        )
        index_names = [idx["indexname"] for idx in indexes]
        required_indexes = [
            "idx_review_queue_status",
            "idx_review_queue_created",
            "idx_review_queue_feedback_id",
        ]
        for idx_name in required_indexes:
            if idx_name not in index_names:
                logger.warning(f"Index {idx_name} not found (may be created automatically)")

        # Check foreign key constraint exists
        fk_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'review_queue'
                    AND tc.constraint_type = 'FOREIGN KEY'
                    AND kcu.column_name = 'source_feedback_id'
            )
            """
        )

        if not fk_exists:
            logger.error("Foreign key constraint on source_feedback_id not found")
            return False

        logger.info("✅ Migration 026 verified: review_queue table created")
        return True


async def main():
    """Run migration standalone"""
    # Try to get DATABASE_URL from environment or settings
    try:
        from backend.app.core.config import settings

        database_url = settings.database_url
    except (ImportError, AttributeError):
        database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Set DATABASE_URL or ensure app.core.config.settings.database_url is configured.")
        return False

    migration = Migration026()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
