"""
Apply Migration 015: Add Drive Columns
"""

import os
import sys
from pathlib import Path

import psycopg2

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def apply_migration_015():
    """Apply migration 015"""

    migration_file = (
        Path(__file__).parent.parent / "db" / "migrations" / "015_add_drive_columns.sql"
    )

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print("🔄 Connecting to database...")

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

        print("✅ Migration 015 applied successfully!")

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
    print("Migration 015: Add Drive Columns")
    print("=" * 60)

    success = apply_migration_015()

    if success:
        print("\n🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
