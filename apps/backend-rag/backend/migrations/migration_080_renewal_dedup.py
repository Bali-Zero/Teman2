"""
Migration 080: Add last_notified_at to renewal_alerts for deduplication.

Prevents duplicate notifications when crm_automation_engine (cron 07:00)
and chain_compliance_autopilot (MCP on-demand) run overlapping checks.

Security audit 2026-04-03: AU1 race condition fix.
"""

import asyncio
import os

import asyncpg


async def apply(conn: asyncpg.Connection) -> None:
    """Add last_notified_at column and unique constraint."""
    await conn.execute("""
        ALTER TABLE renewal_alerts
        ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ DEFAULT NULL
    """)

    # Unique constraint prevents duplicate alerts for same practice+type+date
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_renewal_alerts_dedup
        ON renewal_alerts (practice_id, alert_type, DATE(created_at))
    """)


async def downgrade(conn: asyncpg.Connection) -> None:
    """Remove dedup column and constraint."""
    await conn.execute("DROP INDEX IF EXISTS uq_renewal_alerts_dedup")
    await conn.execute("ALTER TABLE renewal_alerts DROP COLUMN IF EXISTS last_notified_at")


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL not set")
        return
    conn = await asyncpg.connect(url)
    try:
        await apply(conn)
        print("Migration 080 applied successfully")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
