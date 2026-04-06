"""
Migration 090: Security audit log table for S03 Sprint 2.

Tracks security-sensitive actions: login, logout, token refresh,
token revocation, RBAC violations, API key usage, data exports.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "090_security_audit_log"
DESCRIPTION = "S03-S2: Create security_audit_log table for security event tracking"


async def check_if_applied(conn) -> bool:
    """Check if migration has been applied."""
    result = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'security_audit_log')"
    )
    return result


async def apply(conn) -> None:
    """Apply migration: create security_audit_log table."""
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS security_audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id VARCHAR(255),
            user_email VARCHAR(255),
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100),
            resource_id VARCHAR(255),
            ip_address INET,
            user_agent TEXT,
            details JSONB,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_security_audit_user ON security_audit_log(user_email, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_security_audit_action ON security_audit_log(action, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_security_audit_created ON security_audit_log(created_at)"
    )

    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    """Rollback migration."""
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute("DROP TABLE IF EXISTS security_audit_log CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID
    )
    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
