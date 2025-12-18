#!/usr/bin/env python3
"""
Migration 012: Fix Production Schema Issues
Adds missing conversation_id column to interactions table
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration012(BaseMigration):
    """Fix Production Schema Issues"""

    def __init__(self):
        super().__init__(
            migration_number=12,
            sql_file="012_fix_production_schema.sql",
            description="Add conversation_id column to interactions table and fix auto_logout function",
            dependencies=[7],  # Depends on migration 007 (interactions table)
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify conversation_id column exists"""
        result = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'interactions'
                AND column_name = 'conversation_id'
            )
        """
        )
        return bool(result)


async def main():
    migration = Migration012()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)










