"""
Migration 089: API Key Records table for S03 security hardening.

Replaces name-based role inference with explicit DB-backed role assignment.
Keys are stored as SHA256 hashes, never plaintext.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "089_api_key_records"
DESCRIPTION = "S03: Create api_key_records table for explicit API key role mapping"


async def check_if_applied(conn) -> bool:
    """Check if migration has been applied."""
    result = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'api_key_records')"
    )
    return result


async def apply(conn) -> None:
    """Apply migration: create api_key_records table."""
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS api_key_records (
            id SERIAL PRIMARY KEY,
            key_hash VARCHAR(64) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'user',
            permissions TEXT[] NOT NULL DEFAULT '{}',
            source VARCHAR(50) NOT NULL DEFAULT 'manual',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ,
            last_used_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_key_records_hash ON api_key_records(key_hash)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_key_records_active ON api_key_records(is_active) WHERE is_active = TRUE"
    )

    # Track migration
    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    """Rollback migration."""
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute("DROP TABLE IF EXISTS api_key_records CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID
    )
    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
