"""Migration 074: Add content_hash to documents for dedup."""
import logging

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = "074"
DESCRIPTION = "Add content_hash column to documents for content-based deduplication"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32);")
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_content_hash
        ON documents(client_id, content_hash)
        WHERE content_hash IS NOT NULL;
    """)
    logger.info("Migration 074 applied: content_hash column + index")


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_documents_content_hash;")
    await conn.execute("ALTER TABLE documents DROP COLUMN IF EXISTS content_hash;")
    logger.info("Migration 074 rolled back")
