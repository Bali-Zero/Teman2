#!/usr/bin/env python3
"""
Migration 015: Add Drive Columns
Adds Google Drive metadata to parent_documents table
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration015(BaseMigration):
    """Add Drive Columns Migration"""

    def __init__(self):
        super().__init__(
            migration_number=15,
            sql_file="015_add_drive_columns.sql",
            description="Add Google Drive metadata columns to parent_documents",
            dependencies=[13],  # Depends on migration 013 (parent_documents table)
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify columns were added"""
        columns = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'parent_documents'
            AND column_name IN ('drive_file_id', 'drive_web_view_link', 'mime_type')
        """
        )
        return len(columns) == 3


async def main():
    migration = Migration015()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)










