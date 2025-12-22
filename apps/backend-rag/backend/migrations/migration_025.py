#!/usr/bin/env python3
"""
Migration 025: Conversation Ratings System
Adds conversation ratings table and view for ConversationTrainer agent
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration

logger = logging.getLogger(__name__)


class Migration025(BaseMigration):
    """Conversation Ratings System Migration"""

    def __init__(self):
        super().__init__(
            migration_number=25,
            sql_file="025_conversation_ratings.sql",
            description="Add conversation ratings table and view for ConversationTrainer agent",
            dependencies=[23],  # Depends on migration 023 (conversation_history, user_profiles)
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify conversation_ratings table and view were created"""
        # Check conversation_ratings table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'conversation_ratings'
            )
            """
        )

        if not table_exists:
            logger.error("conversation_ratings table not found")
            return False

        # Check required columns exist
        required_columns = ["id", "session_id", "rating", "feedback_type", "feedback_text", "created_at"]
        for col in required_columns:
            col_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'conversation_ratings' AND column_name = $1
                )
                """,
                col,
            )
            if not col_exists:
                logger.error(f"Column {col} not found in conversation_ratings")
                return False

        # Check indexes exist
        indexes = await conn.fetch(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'conversation_ratings'
            """
        )
        index_names = [idx["indexname"] for idx in indexes]
        required_indexes = [
            "idx_conv_ratings_session",
            "idx_conv_ratings_rating",
            "idx_conv_ratings_created",
        ]
        for idx_name in required_indexes:
            if idx_name not in index_names:
                logger.warning(f"Index {idx_name} not found (may be created automatically)")

        # Check view exists
        view_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views
                WHERE table_name = 'v_rated_conversations'
            )
            """
        )

        if not view_exists:
            logger.error("v_rated_conversations view not found")
            return False

        logger.info("✅ Migration 025 verified: conversation_ratings table and v_rated_conversations view created")
        return True


async def main():
    """Run migration standalone"""
    # Try to get DATABASE_URL from environment or settings
    try:
        from app.core.config import settings

        database_url = settings.database_url
    except (ImportError, AttributeError):
        database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Set DATABASE_URL or ensure app.core.config.settings.database_url is configured.")
        return False

    migration = Migration025()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    success = asyncio.run(main())
    sys.exit(0 if success else 1)

