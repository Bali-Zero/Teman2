#!/usr/bin/env python3
"""
One-time script to apply migration 007 via Fly.io
"""

import os
import sys

import psycopg2


def apply_migration():
    from app.core.config import settings

    database_url = settings.database_url

    if not database_url:
        print("❌ DATABASE_URL not set")
        return False

    # Read migration SQL
    migration_file = "backend/db/migrations/007_crm_system_schema.sql"

    if not os.path.exists(migration_file):
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print(f"📁 Reading {migration_file}...")
    with open(migration_file) as f:
        sql = f.read()

    print("🔌 Connecting to database...")
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        print("⚙️  Executing migration...")
        cursor.execute(sql)

        conn.commit()

        # Verify tables created
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'team_members', 'clients', 'practice_types', 'practices',
                'interactions', 'documents', 'renewal_alerts', 'crm_settings',
                'activity_log'
            )
            ORDER BY table_name
        """
        )

        tables = cursor.fetchall()

        print("\n✅ Migration completed successfully!")
        print(f"\n📊 Created {len(tables)} CRM tables:")
        for table in tables:
            print(f"   ✓ {table[0]}")

        # Show practice types
        cursor.execute("SELECT code, name FROM practice_types ORDER BY code")
        practice_types = cursor.fetchall()

        print(f"\n📋 Loaded {len(practice_types)} practice types:")
        for code, name in practice_types:
            print(f"   • {code}: {name}")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
