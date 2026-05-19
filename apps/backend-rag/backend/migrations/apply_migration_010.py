#!/usr/bin/env python3
"""
One-time script to apply migration 010 via Fly.io or local
Migration: Fix team_members schema alignment
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import asyncpg
except ImportError:
    sys.exit(1)


async def apply_migration():
    """Apply migration 010 to fix team_members schema"""
    from backend.app.core.config import settings

    database_url = settings.database_url

    if not database_url:
        return False

    # Read migration SQL
    migration_file = (
        Path(__file__).parent.parent / "db" / "migrations" / "010_fix_team_members_schema.sql"
    )

    if not migration_file.exists():
        return False

    with open(migration_file) as f:
        sql = f.read()

    try:
        conn = await asyncpg.connect(database_url)

        await conn.execute(sql)

        # Verify columns added
        columns_query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'team_members'
            AND column_name IN (
                'pin_hash', 'department', 'language', 'personalized_response',
                'notes', 'last_login', 'failed_attempts', 'locked_until',
                'full_name', 'active'
            )
            ORDER BY column_name
        """

        columns = await conn.fetch(columns_query)

        for col in columns:
            "NULL" if col["is_nullable"] == "YES" else "NOT NULL"

        # Check indexes
        indexes_query = """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'team_members'
            AND indexname LIKE 'idx_team_members_%'
            ORDER BY indexname
        """
        indexes = await conn.fetch(indexes_query)

        for _idx in indexes:
            pass

        await conn.close()

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio


    success = asyncio.run(apply_migration())

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
