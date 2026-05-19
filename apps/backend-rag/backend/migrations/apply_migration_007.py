#!/usr/bin/env python3
"""
One-time script to apply migration 007 via Fly.io
"""

import os
import sys

import psycopg2


def apply_migration():
    from backend.app.core.config import settings

    database_url = settings.database_url

    if not database_url:
        return False

    # Read migration SQL
    migration_file = "backend/db/migrations/007_crm_system_schema.sql"

    if not os.path.exists(migration_file):
        return False

    with open(migration_file) as f:
        sql = f.read()

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
                'team_members', 'clients', 'practice_types', 'practices',
                'interactions', 'documents', 'renewal_alerts', 'crm_settings',
                'activity_log'
            )
            ORDER BY table_name
        """,
        )

        tables = cursor.fetchall()

        for _table in tables:
            pass

        # Show practice types
        cursor.execute("SELECT code, name FROM practice_types ORDER BY code")
        practice_types = cursor.fetchall()

        for _code, _name in practice_types:
            pass

        cursor.close()
        conn.close()

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
