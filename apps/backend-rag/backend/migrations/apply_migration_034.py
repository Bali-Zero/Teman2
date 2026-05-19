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
        return False

    # Read migration SQL
    migration_file = (
        Path(__file__).parent.parent / "backend/db/migrations_v2/034_company_centric_crm.sql"
    )

    if not migration_file.exists():
        return False


    # Read SQL
    with open(migration_file, encoding="utf-8") as f:
        sql = f.read()

    # Connect and execute
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

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

        for _table in tables:
            pass

        for _idx in indexes:
            pass

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
            for _view in views:
                pass

        cursor.close()
        conn.close()


        return True

    except psycopg2.Error:
        return False
    except Exception:
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
