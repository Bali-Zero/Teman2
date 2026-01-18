"""
Migration 051: Client-Messaging Cross-Channel Link

Purpose:
- Add client_id to messaging_users for omnichannel client recognition
- Link messaging identities (Telegram, WhatsApp, etc.) to CRM clients
- Enable unified customer view across all communication channels

Use Cases:
1. Cliente scrive su WhatsApp poi passa a Telegram → Zantara riconosce stesso cliente
2. Team member riceve notifica Telegram → vede profilo CRM completo
3. Analytics omnichannel → "Quanti clienti usano Telegram vs WhatsApp?"

Author: Claude Sonnet 4.5
Date: 2026-01-19
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - add client_id to messaging_users."""

    logger.info("Applying migration 051: Client-Messaging Cross-Channel Link")

    # 1. Add client_id column to messaging_users
    await conn.execute("""
        ALTER TABLE messaging_users
        ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL;
    """)

    logger.info("✅ Added client_id column to messaging_users")

    # 2. Create index for fast lookups
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messaging_users_client
        ON messaging_users(client_id);
    """)

    logger.info("✅ Created index on messaging_users(client_id)")

    # 3. Auto-link existing data via email matching
    # Link messaging_users → clients when user_profiles.email = clients.email
    result = await conn.execute("""
        UPDATE messaging_users mu
        SET client_id = c.id
        FROM user_profiles up
        JOIN clients c ON c.email = up.email
        WHERE mu.user_id = up.id
          AND mu.client_id IS NULL
          AND up.email IS NOT NULL
          AND c.email IS NOT NULL;
    """)

    rows_affected = result.split()[-1] if result else "0"
    logger.info(f"✅ Auto-linked {rows_affected} messaging_users to clients via email")

    # 4. Add helpful comment
    await conn.execute("""
        COMMENT ON COLUMN messaging_users.client_id IS
        'Link to CRM client. Enables omnichannel recognition: same client across Telegram/WhatsApp/etc.';
    """)

    logger.info("Migration 051 applied successfully: Client-Messaging Link created")
    print("✅ Applied migration 051: Client-Messaging Cross-Channel Link")


async def rollback(conn: Any) -> None:
    """Rollback the migration - remove client_id column."""

    logger.info("Rolling back migration 051: Client-Messaging Cross-Channel Link")

    # Drop index first
    await conn.execute("DROP INDEX IF EXISTS idx_messaging_users_client;")

    # Then drop column
    await conn.execute("ALTER TABLE messaging_users DROP COLUMN IF EXISTS client_id;")

    logger.info("Migration 051 rolled back successfully")
    print("⏪ Rolled back migration 051: Client-Messaging Cross-Channel Link")
