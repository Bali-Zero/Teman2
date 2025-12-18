"""
Apply Migration 012: Fix Production Schema Issues
Adds missing conversation_id column to interactions table
"""

import os
import sys
from pathlib import Path

import psycopg2

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def apply_migration_012():
    """Apply migration 012 to fix production schema issues"""

    migration_file = (
        Path(__file__).parent.parent / "db" / "migrations" / "012_fix_production_schema.sql"
    )

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print("🔄 Connecting to production database...")

    try:
        # Connect to PostgreSQL
        db_url = settings.database_url or os.getenv("DATABASE_URL")
        if not db_url:
            print("❌ DATABASE_URL not found in settings or environment")
            return False

        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        print("✅ Connected to database")

        # Read migration file
        with open(migration_file, encoding="utf-8") as f:
            migration_sql = f.read()

        print(f"📄 Loaded migration from: {migration_file.name}")
        print("🚀 Applying migration...")

        # Execute migration
        cursor.execute(migration_sql)
        conn.commit()

        print("✅ Migration 012 applied successfully!")

        # Verify the fix
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'interactions'
            AND column_name = 'conversation_id'
        """
        )

        result = cursor.fetchone()
        if result:
            print("✅ Verified: conversation_id column exists")
            print(f"   - Type: {result[1]}")
            print(f"   - Nullable: {result[2]}")
        else:
            print("⚠️  Warning: Could not verify conversation_id column")

        cursor.close()
        conn.close()

        return True

    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Migration 012: Fix Production Schema Issues")
    print("=" * 60)

    success = apply_migration_012()

    if success:
        print("\n🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
