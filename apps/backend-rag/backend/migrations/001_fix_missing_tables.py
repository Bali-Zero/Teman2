#!/usr/bin/env python3
"""
Migration: Fix missing PostgreSQL tables
Date: 2025-10-19
Purpose: Create cultural_knowledge, query_clusters tables and fix memory_facts.id
"""

import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def run_migration():
    """Run database migration to create missing tables"""

    from app.core.config import settings

    database_url = settings.database_url
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found")
        return False

    try:
        print("🔌 Connecting to PostgreSQL...")
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print("✅ Connected")

        # Create cultural_knowledge table
        print("📊 Creating cultural_knowledge table...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cultural_knowledge (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                language VARCHAR(10) DEFAULT 'en',
                category VARCHAR(50),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_cultural_knowledge_language ON cultural_knowledge(language);
            CREATE INDEX IF NOT EXISTS idx_cultural_knowledge_category ON cultural_knowledge(category);
        """
        )
        print("✅ cultural_knowledge created")

        # Create query_clusters table
        print("📊 Creating query_clusters table...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS query_clusters (
                id SERIAL PRIMARY KEY,
                query TEXT NOT NULL,
                cluster_id INTEGER,
                similarity_score FLOAT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_query_clusters_cluster_id ON query_clusters(cluster_id);
        """
        )
        print("✅ query_clusters created")

        # Fix memory_facts table
        print("📊 Fixing memory_facts table...")
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_name = 'memory_facts'
            );
        """
        )
        if cursor.fetchone()[0]:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'memory_facts' AND column_name = 'id'
                );
            """
            )
            if not cursor.fetchone()[0]:
                cursor.execute("ALTER TABLE memory_facts ADD COLUMN id SERIAL PRIMARY KEY;")
                print("✅ Added id to memory_facts")
            else:
                print("✅ memory_facts.id exists")
        else:
            print("ℹ️  memory_facts will be created by app")

        cursor.close()
        conn.close()
        print("🎉 Migration completed!")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    sys.exit(0 if run_migration() else 1)
