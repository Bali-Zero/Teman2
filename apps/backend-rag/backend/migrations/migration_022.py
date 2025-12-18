"""
Migration 022: Performance Indexes
Adds critical indexes for memory_facts and user_stats tables to prevent full table scans.
"""

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


class Migration022:
    """Performance Indexes Migration"""

    migration_number = 22
    description = "Add performance indexes for memory_facts and user_stats"
    dependencies = [21]

    async def apply(self, conn: asyncpg.Connection) -> bool:
        """Apply the migration"""
        try:
            # Check if already applied
            if await self.is_applied(conn):
                logger.info("Migration 022 already applied, skipping")
                return True

            # Create indexes (IF NOT EXISTS for safety)
            await conn.execute("""
                -- Index on memory_facts.user_id for fast user lookups
                CREATE INDEX IF NOT EXISTS idx_memory_facts_user_id
                ON memory_facts(user_id);

                -- Index on user_stats.user_id for fast stat lookups
                CREATE INDEX IF NOT EXISTS idx_user_stats_user_id
                ON user_stats(user_id);

                -- Composite index for memory_facts queries with ordering
                CREATE INDEX IF NOT EXISTS idx_memory_facts_user_created
                ON memory_facts(user_id, created_at DESC);

                -- Index on conversations.user_id for history lookups
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                ON conversations(user_id);

                -- Composite index for conversations with timestamp ordering
                CREATE INDEX IF NOT EXISTS idx_conversations_user_created
                ON conversations(user_id, created_at DESC);
            """)

            # Record migration
            await conn.execute(
                """
                INSERT INTO schema_migrations (migration_name, migration_number, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (migration_name) DO NOTHING
                """,
                "migration_022",
                self.migration_number,
                self.description,
            )

            logger.info("Migration 022 applied successfully - performance indexes created")
            return True

        except Exception as e:
            logger.error(f"Migration 022 failed: {e}")
            return False

    async def is_applied(self, conn: asyncpg.Connection) -> bool:
        """Check if migration was already applied"""
        try:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE migration_number = $1)",
                self.migration_number,
            )
            return result
        except Exception:
            return False

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify migration was applied correctly"""
        try:
            indexes_to_check = [
                "idx_memory_facts_user_id",
                "idx_user_stats_user_id",
                "idx_memory_facts_user_created",
                "idx_conversations_user_id",
                "idx_conversations_user_created",
            ]

            for idx_name in indexes_to_check:
                idx_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = $1)",
                    idx_name,
                )
                if not idx_exists:
                    logger.error(f"Index {idx_name} not found")
                    return False

            logger.info("Migration 022 verified successfully - all indexes present")
            return True

        except Exception as e:
            logger.error(f"Migration 022 verification failed: {e}")
            return False


async def run_migration():
    """Run migration standalone"""
    import os
    import sys

    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    try:
        from app.core.config import settings
        database_url = settings.database_url
    except ImportError:
        database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        return

    conn = await asyncpg.connect(database_url)
    try:
        migration = Migration022()
        success = await migration.apply(conn)
        if success:
            verified = await migration.verify(conn)
            if verified:
                print("Migration 022 completed and verified")
            else:
                print("Migration 022 applied but verification failed")
        else:
            print("Migration 022 failed")
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration())
