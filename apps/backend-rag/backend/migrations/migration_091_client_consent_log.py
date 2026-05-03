"""
Migration 091: Client consent log for PDP Act (UU 27/2022) compliance.

Append-only, immutable table tracking per-purpose consent grants and revocations.
Required by Art. 20 (granular consent) and Art. 31 (processing records).
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "091_client_consent_log"
DESCRIPTION = "S03-S3: Create client_consent_log table for PDP Act compliance"


async def check_if_applied(conn) -> bool:
    result = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'client_consent_log')"
    )
    return result


async def apply(conn) -> None:
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS client_consent_log (
            id BIGSERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id),
            purpose_key VARCHAR(100) NOT NULL,
            action VARCHAR(20) NOT NULL CHECK (action IN ('granted', 'revoked')),
            legal_basis VARCHAR(50) DEFAULT 'consent',
            policy_version VARCHAR(20),
            captured_by VARCHAR(255),
            channel VARCHAR(50),
            ip_address INET,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consent_log_client ON client_consent_log(client_id, purpose_key, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consent_log_active ON client_consent_log(client_id, purpose_key) WHERE action = 'granted'"
    )

    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute("DROP TABLE IF EXISTS client_consent_log CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID
    )
    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
