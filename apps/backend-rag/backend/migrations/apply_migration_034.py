#!/usr/bin/env python3
"""
Apply Company-Centric CRM Migration (034)
Creates companies, client_company_links, company_documents, tax_records tables
"""

import sys
from pathlib import Path

import psycopg2


def apply_migration():
    """Apply Company-Centric CRM schema migration"""

    # Get DATABASE_URL
    from backend.app.core.config import settings

    database_url = settings.database_url
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print()
        print("To run this migration:")
        print("1. Get your DATABASE_URL from Fly.io dashboard or .env")
        print("2. Run: export DATABASE_URL='postgresql://...'")
        print("3. Run: python apply_migration_034.py")
        return False

    # Read migration SQL
    migration_file = (
        Path(__file__).parent.parent / "backend/db/migrations_v2/034_company_centric_crm.sql"
    )

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    print("=" * 70)
    print("ZANTARA - Company-Centric CRM Migration")
    print("=" * 70)
    print()
    print(f"📁 Migration file: {migration_file.name}")
    print(
        f"🗄️  Target database: {database_url.split('@')[1] if '@' in database_url else 'PostgreSQL'}",
    )
    print()

    # Read SQL
    with open(migration_file, encoding="utf-8") as f:
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
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'companies', 'client_company_links',
                'company_documents', 'tax_records', 'tax_documents'
            )
            ORDER BY table_name
        """,
        )

        tables = cursor.fetchall()

        # Verify indexes
        cursor.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename IN (
                'companies', 'client_company_links',
                'company_documents', 'tax_records', 'tax_documents'
            )
            ORDER BY tablename, indexname
        """,
        )
        indexes = cursor.fetchall()

        print()
        print("✅ Migration completed successfully!")
        print()
        print(f"📊 Created {len(tables)} tables:")
        for table in tables:
            print(f"   ✓ {table[0]}")

        print()
        print(f"📈 Created {len(indexes)} indexes:")
        for idx in indexes:
            print(f"   ✓ {idx[0]}")

        # Show views
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            AND table_name LIKE '%company%'
            ORDER BY table_name
        """,
        )
        views = cursor.fetchall()

        if views:
            print()
            print(f"👁️  Created {len(views)} views:")
            for view in views:
                print(f"   ✓ {view[0]}")

        cursor.close()
        conn.close()

        print()
        print("=" * 70)
        print("🎉 Company-Centric CRM is ready!")
        print()
        print("Next steps:")
        print("  1. Deploy the backend to Fly.io")
        print("  2. Add Company and Tax tabs to the frontend")
        print("  3. Start linking clients to companies")
        print("=" * 70)

        return True

    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
