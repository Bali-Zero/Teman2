"""
Migration 067: Add indexes for clients soft-delete filter

Purpose:
- Add partial index on clients.id WHERE deleted_at IS NULL
- Add partial index on clients.created_at DESC WHERE deleted_at IS NULL
- These indexes optimize all CRM/Portal queries that filter out soft-deleted clients

Context:
- 10,258 of 11,283 clients are soft-deleted
- Without these indexes, every client list query scans all 11K rows
- Partial index covers only the 1,025 active clients

Author: Claude Opus 4.6
Date: 2026-03-29
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def upgrade(conn: Any) -> None:
    """Add soft-delete partial indexes on clients."""

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_clients_active
        ON clients (id)
        WHERE deleted_at IS NULL
        """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_clients_active_created
        ON clients (created_at DESC)
        WHERE deleted_at IS NULL
        """
    )

    logger.info("✅ Migration 067: Created soft-delete partial indexes on clients")


async def downgrade(conn: Any) -> None:
    """Remove soft-delete partial indexes."""
    await conn.execute("DROP INDEX IF EXISTS idx_clients_active")
    await conn.execute("DROP INDEX IF EXISTS idx_clients_active_created")
    logger.info("✅ Migration 067 rolled back: Removed soft-delete indexes")
