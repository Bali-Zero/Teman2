#!/usr/bin/env python3
"""
Migration 013: Agentic RAG Tables
Creates tables for Parent-Child Retrieval and Golden Router
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration013(BaseMigration):
    """Agentic RAG Tables Migration"""

    def __init__(self):
        super().__init__(
            migration_number=13,
            sql_file="013_agentic_rag_tables.sql",
            description="Create tables for Parent-Child Retrieval and Golden Router",
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify all tables were created"""
        tables_to_check = ["parent_documents", "golden_routes", "query_route_clusters"]
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
    migration = Migration013()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)










