#!/usr/bin/env python3
"""
Migration 035: Team Departments & Drive Folder Access
Adds department-based folder filtering for Google Drive
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration036(BaseMigration):
    """Team Departments Migration"""

    def __init__(self):
        super().__init__(
            migration_number=36,
            sql_file="036_team_departments.sql",
            description="Add department-based Google Drive folder access",
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify migration was applied"""
        # Check if department column exists
        result = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'team_members' AND column_name = 'department'
            )
            """
        )
        if not result:
            return False

        # Check if departments table exists
        result = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'departments'
            )
            """
        )
        return result


async def main():
    migration = Migration036()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
