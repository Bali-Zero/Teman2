#!/usr/bin/env python3
"""
Migration 001: Fix missing PostgreSQL tables
Creates cultural_knowledge and query_clusters tables, fixes memory_facts.id
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration001(BaseMigration):
    """Fix missing PostgreSQL tables"""

    def __init__(self):
        super().__init__(
            migration_number=1,
            sql_file="001_fix_missing_tables.sql",
            description="Create cultural_knowledge and query_clusters tables, fix memory_facts.id",
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify tables were created"""
        # Check cultural_knowledge
        cultural_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'cultural_knowledge'
            )
        """
        )

        # Check query_clusters
        clusters_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'query_clusters'
            )
        """
        )

        return bool(cultural_exists) and bool(clusters_exists)


async def main():
    migration = Migration001()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
