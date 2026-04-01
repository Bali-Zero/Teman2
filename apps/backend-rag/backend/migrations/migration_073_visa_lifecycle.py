"""
Migration 073: Visa document lifecycle support.

Adds:
- clients.current_visa_type (VARCHAR 50) — extracted by OCR
- clients.current_visa_sponsor (VARCHAR 255) — extracted by OCR
- documents.subfolder (VARCHAR 100) — tracks subfolder within category (e.g. "Actual Visa")
- Index on documents(client_id, subfolder) for fast actual visa lookup
"""
import logging

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = "073"
DESCRIPTION = "Visa document lifecycle: client visa fields + document subfolder tracking"


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration."""
    await conn.execute("""
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS current_visa_type VARCHAR(50);
    """)
    await conn.execute("""
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS current_visa_sponsor VARCHAR(255);
    """)
    await conn.execute("""
        ALTER TABLE documents ADD COLUMN IF NOT EXISTS subfolder VARCHAR(100);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_client_subfolder
        ON documents(client_id, subfolder)
        WHERE is_archived IS NOT TRUE;
    """)
    logger.info("Migration 073 applied: visa lifecycle columns added")


async def down(conn: asyncpg.Connection) -> None:
    """Rollback migration."""
    await conn.execute("DROP INDEX IF EXISTS idx_documents_client_subfolder;")
    await conn.execute("ALTER TABLE documents DROP COLUMN IF EXISTS subfolder;")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS current_visa_sponsor;")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS current_visa_type;")
    logger.info("Migration 073 rolled back")
