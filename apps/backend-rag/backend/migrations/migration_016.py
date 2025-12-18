#!/usr/bin/env python3
"""
Migration 016: Add Summary to Parent Documents
Adds summary column to parent_documents table
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration016(BaseMigration):
    """Add Summary to Parent Documents Migration"""

    def __init__(self):
        super().__init__(
            migration_number=16,
            sql_file="016_add_summary_to_parent_docs.sql",
            description="Add summary column to parent_documents table",
            dependencies=[13],  # Depends on migration 013 (parent_documents table)
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify summary column was added"""
        result = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'parent_documents'
                AND column_name = 'summary'
            )
        """
        )
        return bool(result)


async def main():
    migration = Migration016()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)










