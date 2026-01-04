"""
Migration: Create KBLI Blueprints Table
Version: 035
Date: 2026-01-01
Description: Stores high-quality KBLI Blueprint metadata and file references for Workspace and Client Portal.
"""

from typing import Any


async def apply(conn: Any) -> None:
    # 1. Create Blueprints Table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS kbli_blueprints (
            kbli_code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            pdf_path TEXT NOT NULL,
            risk_level TEXT,
            min_capital TEXT,
            summary TEXT,
            access_level TEXT DEFAULT 'client', -- 'public', 'client', 'internal'
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_kbli_blueprints_risk ON kbli_blueprints(risk_level);
    """)

    # 2. Add to migrations table
    await conn.execute(
        "INSERT INTO migrations (migration_name) VALUES ('035_kbli_blueprints') ON CONFLICT DO NOTHING;"
    )

    print("✅ Applied migration 035: KBLI Blueprints table created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS kbli_blueprints;")
    print("Rollback migration 035: KBLI Blueprints table dropped")
