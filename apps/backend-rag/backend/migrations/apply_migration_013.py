"""
Apply Migration 013: Agentic RAG Tables
Creates tables for Parent-Child Retrieval and Golden Router
"""

import os
import sys
from pathlib import Path

import psycopg2

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

logger = logging.getLogger(__name__)

from backend.app.core.config import settings


def apply_migration_013():
    """Apply migration 013 to create Agentic RAG tables"""

    migration_file = (
        Path(__file__).parent.parent / "db" / "migrations" / "013_agentic_rag_tables.sql"
    )

    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False

    logger.info("Connecting to database...")

    try:
        # Connect to PostgreSQL
        db_url = settings.database_url or os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL not found in settings or environment")
            return False

        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        logger.info("Connected to database")

        # Read migration file
        with open(migration_file, encoding="utf-8") as f:
            migration_sql = f.read()

        logger.info(f"Loaded migration from: {migration_file.name}")
        logger.info("Applying migration...")

        # Execute migration
        cursor.execute(migration_sql)
        conn.commit()

        logger.info("Migration 013 applied successfully!")

        # Verify the tables
        tables_to_check = ["parent_documents", "golden_routes", "query_route_clusters"]
        for table in tables_to_check:
            cursor.execute(
                f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = '{table}'
                )
            """,
            )
            exists = cursor.fetchone()[0]
            if exists:
                logger.info(f"✅ Verified: table '{table}' exists")
            else:
                logger.error(f"❌ Error: table '{table}' was not created")

        cursor.close()
        conn.close()

        return True

    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Migration 013: Agentic RAG Tables")
    logger.info("=" * 60)

    success = apply_migration_013()

    if success:
        logger.info("\n🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n❌ Migration failed!")
        sys.exit(1)
