#!/usr/bin/env python3
"""
Migration 007: CRM System Schema
Creates tables for CRM system (team_members, clients, practices, interactions, etc.)
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from db.migration_base import BaseMigration


class Migration007(BaseMigration):
    """CRM System Schema Migration"""

    def __init__(self):
        super().__init__(
            migration_number=7,
            sql_file="007_crm_system_schema.sql",
            description="Create CRM system tables (team_members, clients, practices, interactions, etc.)",
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify all CRM tables were created"""
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'team_members', 'clients', 'practice_types', 'practices',
                'interactions', 'documents', 'renewal_alerts', 'crm_settings',
                'activity_log'
            )
        """
        )
        return len(tables) == 9


async def main():
    migration = Migration007()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)










