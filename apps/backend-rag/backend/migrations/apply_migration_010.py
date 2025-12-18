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
    print("❌ asyncpg not installed. Install with: pip install asyncpg")
    sys.exit(1)


async def apply_migration():
    """Apply migration 010 to fix team_members schema"""
    from app.core.config import settings

    database_url = settings.database_url

    if not database_url:
        print("❌ DATABASE_URL not set")
        return False

    # Read migration SQL
    migration_file = (
        Path(__file__).parent.parent / "db" / "migrations" / "010_fix_team_members_schema.sql"
    )

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print(f"📁 Reading {migration_file.name}...")
    with open(migration_file) as f:
        sql = f.read()

    print("🔌 Connecting to database...")
    try:
        conn = await asyncpg.connect(database_url)

        print("⚙️  Executing migration...")
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

        print("\n✅ Migration completed successfully!")
        print("\n📊 Verified columns in team_members table:")
        for col in columns:
            nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
            print(f"   ✓ {col['column_name']}: {col['data_type']} ({nullable})")

        # Check indexes
        indexes_query = """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'team_members'
            AND indexname LIKE 'idx_team_members_%'
            ORDER BY indexname
        """
        indexes = await conn.fetch(indexes_query)

        print("\n📑 Indexes created:")
        for idx in indexes:
            print(f"   ✓ {idx['indexname']}")

        await conn.close()

        return True

    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio

    print("=" * 70)
    print("MIGRATION 010: Fix team_members schema alignment")
    print("=" * 70)
    print()

    success = asyncio.run(apply_migration())

    if success:
        print("\n" + "=" * 70)
        print("✅ Migration 010 applied successfully!")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("❌ Migration 010 failed!")
        print("=" * 70)
        sys.exit(1)
