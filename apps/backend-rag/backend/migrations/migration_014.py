#!/usr/bin/env python3
"""
Migration 014: Knowledge Graph Tables
Creates tables for Knowledge Graph
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration014(BaseMigration):
    """Knowledge Graph Tables Migration"""

    def __init__(self):
        super().__init__(
            migration_number=14,
            sql_file="014_knowledge_graph_tables.sql",
            description="Create tables for Knowledge Graph (kg_entities, kg_relationships)",
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify all tables were created"""
        tables_to_check = ["kg_entities", "kg_relationships"]
        for table in tables_to_check:
            exists = await conn.fetchval(
                f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = '{table}'
                )
            """
            )
            if not exists:
                return False
        return True


async def main():
    migration = Migration014()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)










