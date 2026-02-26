#!/usr/bin/env python
"""
Apply Zantara Media Database Migration
Applies migration 017 directly via Python
"""

import os
import sys
import asyncpg
from pathlib import Path


async def apply_migration():
    """Apply the database migration."""
    # Get database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("   Set it with: export DATABASE_URL='postgresql://...'")
        sys.exit(1)

    print("=" * 80)
    print("ZANTARA MEDIA - Database Migration 017")
    print("=" * 80)
    print()
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else 'localhost'}")
    print()

    # Read migration file
    migration_file = (
        Path(__file__).parent.parent.parent
        / "backend-rag"
        / "backend"
        / "db"
        / "migrations"
        / "017_zantara_media_content.sql"
    )

    if not migration_file.exists():
        print("❌ ERROR: Migration file not found")
        print(f"   Looking for: {migration_file}")
        sys.exit(1)

    print(f"Migration file: {migration_file.name}")
    print()

    with open(migration_file) as f:
        migration_sql = f.read()

    # Connect and execute
    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(db_url)
        print("✓ Connected")
        print()

        print("Executing migration...")
        await conn.execute(migration_sql)
        print("✓ Migration executed successfully")
        print()

        # Verify tables created
        print("Verifying tables...")
        tables = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'zantara_%'
            ORDER BY tablename
        """
        )

        if tables:
            print("✓ Tables created:")
            for row in tables:
                print(f"  • {row['tablename']}")
        else:
            print("⚠️  No zantara_* tables found (may have been created before)")

        await conn.close()

        print()
        print("=" * 80)
        print("✅ MIGRATION COMPLETE")
        print("=" * 80)
        print()
        print("You can now start the zantara-media service:")
        print("  cd apps/zantara-media/backend")
        print("  uvicorn app.main:app --port 8001")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(apply_migration())
