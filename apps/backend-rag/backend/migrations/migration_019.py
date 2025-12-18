"""
Migration 019: Episodic Memory System
Creates table for storing timeline of user events and experiences
"""

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


class Migration019:
    """Episodic Memory System Migration"""

    migration_number = 19
    description = "Create episodic memory table for user timeline events"
    dependencies = [18]  # Depends on collective memory (migration 018)

    def __init__(self):
        self.sql_file = (
            Path(__file__).parent.parent / "db" / "migrations" / "019_episodic_memory.sql"
        )

    async def apply(self, conn: asyncpg.Connection) -> bool:
        """Apply the migration"""
        try:
            # Check if already applied
            if await self.is_applied(conn):
                logger.info("Migration 019 already applied, skipping")
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
                "migration_019",
                self.migration_number,
                self.description,
            )

            logger.info("Migration 019 applied successfully")
            return True

        except Exception as e:
            logger.error(f"Migration 019 failed: {e}")
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
            # Check table exists
            table_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                "episodic_memories",
            )
            if not table_exists:
                logger.error("Table episodic_memories not found")
                return False

            # Check required columns
            required_columns = [
                "id",
                "user_id",
                "event_type",
                "title",
                "description",
                "emotion",
                "occurred_at",
                "related_entities",
                "metadata",
            ]
            for col in required_columns:
                col_exists = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'episodic_memories' AND column_name = $1
                    )
                    """,
                    col,
                )
                if not col_exists:
                    logger.error(f"Column {col} not found in episodic_memories")
                    return False

            # Check index exists
            idx_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = $1)",
                "idx_episodic_user_time",
            )
            if not idx_exists:
                logger.error("Index idx_episodic_user_time not found")
                return False

            logger.info("Migration 019 verified successfully")
            return True

        except Exception as e:
            logger.error(f"Migration 019 verification failed: {e}")
            return False


async def run_migration():
    """Run migration standalone"""
    import os

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://balizero:test1234@localhost:5432/balizero"
    )

    conn = await asyncpg.connect(database_url)
    try:
        migration = Migration019()
        success = await migration.apply(conn)
        if success:
            verified = await migration.verify(conn)
            if verified:
                print("Migration 019 completed and verified")
            else:
                print("Migration 019 applied but verification failed")
        else:
            print("Migration 019 failed")
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_migration())
