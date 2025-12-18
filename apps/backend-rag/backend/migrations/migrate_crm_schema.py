#!/usr/bin/env python3
"""
Apply CRM System Schema Migration
Connects to Fly.io PostgreSQL and applies migration 007
"""

import sys
import psycopg2
from pathlib import Path

def apply_crm_migration():
    """Apply CRM schema migration to PostgreSQL"""

    # Get DATABASE_URL
    from app.core.config import settings
    database_url = settings.database_url
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print()
        print("To run this migration:")
        print("1. Get your DATABASE_URL from Fly.io dashboard")
        print("2. Run: export DATABASE_URL='postgresql://...'")
        print("3. Run: python migrate_crm_schema.py")
        return False

    # Read migration SQL
    migration_file = Path(__file__).parent / "backend/db/migrations/007_crm_system_schema.sql"

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print("=" * 70)
    print("ZANTARA CRM SYSTEM - Database Migration")
    print("=" * 70)
    print()
    print(f"📁 Migration file: {migration_file.name}")
    print(f"🗄️  Target database: {database_url.split('@')[1] if '@' in database_url else 'Fly.io PostgreSQL'}")
    print()

    # Read SQL
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Connect and execute
    try:
        print("🔌 Connecting to PostgreSQL...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        print("⚙️  Executing migration...")
        cursor.execute(sql)

        conn.commit()

        # Verify tables created
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'team_members', 'clients', 'practice_types', 'practices',
                'interactions', 'documents', 'renewal_alerts', 'crm_settings',
                'activity_log'
            )
            ORDER BY table_name
        """)

        tables = cursor.fetchall()

        print()
        print("✅ Migration completed successfully!")
        print()
        print(f"📊 Created {len(tables)} CRM tables:")
        for table in tables:
            print(f"   ✓ {table[0]}")

        # Show practice types
        cursor.execute("SELECT code, name FROM practice_types ORDER BY code")
        practice_types = cursor.fetchall()

        print()
        print(f"📋 Loaded {len(practice_types)} practice types:")
        for code, name in practice_types:
            print(f"   • {code}: {name}")

        # Show views
        cursor.execute("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            AND table_name LIKE '%_view'
            ORDER BY table_name
        """)
        views = cursor.fetchall()

        if views:
            print()
            print(f"👁️  Created {len(views)} views:")
            for view in views:
                print(f"   • {view[0]}")

        cursor.close()
        conn.close()

        print()
        print("🚀 CRM System is ready!")
        print()
        print("Next steps:")
        print("1. Create API endpoints: python create_crm_routers.py")
        print("2. Test CRM: python test_crm_system.py")
        print("3. Deploy to production")
        print()
        print("=" * 70)

        return True

    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        print()
        print("Troubleshooting:")
        print("- Check that DATABASE_URL is correct")
        print("- Verify PostgreSQL service is running on Fly.io")
        print("- Check network connection")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = apply_crm_migration()
    sys.exit(0 if success else 1)
