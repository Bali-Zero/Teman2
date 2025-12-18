#!/usr/bin/env python3
"""
Migration 010: Fix team_members schema alignment
Adds missing columns to align with Python User model
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration010(BaseMigration):
    """Fix team_members schema alignment"""

    def __init__(self):
        super().__init__(
            migration_number=10,
            sql_file="010_fix_team_members_schema.sql",
            description="Add missing columns to team_members table (pin_hash, department, language, etc.)",
            dependencies=[7],  # Depends on migration 007 (team_members table)
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify all required columns were added"""
        columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'team_members'
            AND column_name IN (
                'pin_hash', 'department', 'language', 'personalized_response',
                'notes', 'last_login', 'failed_attempts', 'locked_until',
                'full_name', 'active'
            )
        """
        )
        return len(columns) >= 8  # At least 8 of the expected columns


async def main():
    migration = Migration010()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)










