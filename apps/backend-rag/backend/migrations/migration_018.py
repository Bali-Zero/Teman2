"""
Migration 018: Collective Memory System
Creates tables for shared knowledge learned from multiple users
"""

import asyncio
import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


class Migration018:
    """Collective Memory System Migration"""

    migration_number = 18
    description = "Create collective memory tables for shared knowledge"
    dependencies = [2]  # Depends on memory system (migration 002)

    def __init__(self):
        self.sql_file = (
            Path(__file__).parent.parent / "db" / "migrations" / "018_collective_memory.sql"
        )

    async def apply(self, conn: asyncpg.Connection) -> bool:
        """Apply the migration"""
        try:
            # Check if already applied
            if await self.is_applied(conn):
                logger.info("Migration 018 already applied, skipping")
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
                "migration_018",
                self.migration_number,
                self.description,
            )

            logger.info("Migration 018 applied successfully")
            return True

        except Exception as e:
            logger.error(f"Migration 018 failed: {e}")
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
        tables = ["collective_memories", "collective_memory_sources"]
        for table in tables:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                table,
            )
            if not exists:
                logger.error(f"Table {table} not found")
                return False
        return True


async def run_migration():
    """Run migration standalone"""
    import os

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://balizero:test1234@localhost:5432/balizero"
    )

    conn = await asyncpg.connect(database_url)
    try:
        migration = Migration018()
        success = await migration.apply(conn)
        if success:
            verified = await migration.verify(conn)
            if verified:
                print("Migration 018 completed and verified")
            else:
                print("Migration 018 applied but verification failed")
        else:
            print("Migration 018 failed")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
