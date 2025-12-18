"""
Migration 021: Memory-Knowledge Graph Integration
Links memory_facts and episodic_memories to kg_entities
"""

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


class Migration021:
    """Memory-Knowledge Graph Integration Migration"""

    migration_number = 21
    description = "Link memory_facts and episodic_memories to kg_entities"
    dependencies = [
        19,
        20,
    ]  # Depends on episodic_memories table (019) and collective memory embeddings (020)

    def __init__(self):
        self.sql_file = (
            Path(__file__).parent.parent / "db" / "migrations" / "021_memory_kg_integration.sql"
        )

    async def apply(self, conn: asyncpg.Connection) -> bool:
        """Apply the migration"""
        try:
            # Check if already applied
            if await self.is_applied(conn):
                logger.info("Migration 021 already applied, skipping")
                return True

            # Read and execute SQL
            sql = self.sql_file.read_text()
            await conn.execute(sql)

            # Record migration
            await conn.execute(
                """
                INSERT INTO schema_migrations (migration_name, migration_number, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (migration_name) DO NOTHING
                """,
                "migration_021",
                self.migration_number,
                self.description,
            )

            logger.info("Migration 021 applied successfully")
            return True

        except Exception as e:
            logger.error(f"Migration 021 failed: {e}")
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
            # Check related_entities column in memory_facts
            col_exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'memory_facts' AND column_name = 'related_entities'
                )
                """
            )
            if not col_exists:
                logger.error("Column related_entities not found in memory_facts")
                return False

            # Check kg_entity_ids column in episodic_memories
            col_exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'episodic_memories' AND column_name = 'kg_entity_ids'
                )
                """
            )
            if not col_exists:
                logger.error("Column kg_entity_ids not found in episodic_memories")
                return False

            # Check indexes exist
            for idx_name in ["idx_memory_facts_entities", "idx_episodic_kg_entities"]:
                idx_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = $1)",
                    idx_name,
                )
                if not idx_exists:
                    logger.error(f"Index {idx_name} not found")
                    return False

            # Check view exists
            view_exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.views
                    WHERE table_name = 'memory_facts_with_entities'
                )
                """
            )
            if not view_exists:
                logger.error("View memory_facts_with_entities not found")
                return False

            # Check function exists
            func_exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.routines
                    WHERE routine_name = 'get_user_memory_entities'
                )
                """
            )
            if not func_exists:
                logger.error("Function get_user_memory_entities not found")
                return False

            logger.info("Migration 021 verified successfully")
            return True

        except Exception as e:
            logger.error(f"Migration 021 verification failed: {e}")
            return False


async def run_migration():
    """Run migration standalone"""
    import os
    import sys

    # Add backend to path for config import
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    # FIX: Use centralized config instead of hardcoded credentials
    # This follows the NO_HARDCODING rule
    try:
        from app.core.config import settings

        database_url = settings.database_url
    except ImportError:
        # Fallback to environment variable only (NO hardcoded default with credentials)
        database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Please set DATABASE_URL in your .env file or environment.")
        return

    conn = await asyncpg.connect(database_url)
    try:
        migration = Migration021()
        success = await migration.apply(conn)
        if success:
            verified = await migration.verify(conn)
            if verified:
                print("Migration 021 completed and verified")
            else:
                print("Migration 021 applied but verification failed")
        else:
            print("Migration 021 failed")
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_migration())
