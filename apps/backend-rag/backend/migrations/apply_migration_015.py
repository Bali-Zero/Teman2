"""
Apply Migration 015: Add Drive Columns
"""

import os
import sys
from pathlib import Path

import psycopg2

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.core.config import settings


def apply_migration_015():
    """Apply migration 015"""

    migration_file = (
        Path(__file__).parent.parent / "db" / "migrations" / "015_add_drive_columns.sql"
    )

    if not migration_file.exists():
        return False


    try:
        # Connect to PostgreSQL
        db_url = settings.database_url or os.getenv("DATABASE_URL")
        if not db_url:
            return False

        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()


        # Read migration file
        with open(migration_file, encoding="utf-8") as f:
            migration_sql = f.read()


        # Execute migration
        cursor.execute(migration_sql)
        conn.commit()


        cursor.close()
        conn.close()

        return True

    except psycopg2.Error:
        return False
    except Exception:
        return False


if __name__ == "__main__":

    success = apply_migration_015()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
