"""
Migration 107: bridge_outbox table for Pro<->Fly bidirectional bridge.

Purpose:
- Accumulate events (crm.*, compliance.*, rag.*) for the Pro to pull via
  GET /api/bridge/events?after_id={cursor}
- BIGSERIAL id is used as the cursor (monotonic, gap-free, timezone-free)
- 30-day retention via separate cron (DELETE WHERE created_at < NOW() - INTERVAL '30 days')

Note: The plan originally referenced migration_101, but 101-106 already exist
in main (critical_indexes, materialized_views, pg_tuning, olympus_v3_columns,
covering_indexes, news_dedup_constraint). We use 107 to avoid collision.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4

Author: Claude Opus 4.6
Date: 2026-04-14
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply migration 107 — create bridge_outbox table and indexes."""
    logger.info("Applying migration 107: bridge_outbox table")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bridge_outbox (
            id BIGSERIAL PRIMARY KEY,
            type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    logger.info("Created table bridge_outbox")

    # Note: id index implicit via PRIMARY KEY, but we add a named idx for
    # clarity in monitoring queries.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_id ON bridge_outbox (id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_type ON bridge_outbox (type);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_created_at
            ON bridge_outbox (created_at);
    """)
    logger.info("Created indexes on bridge_outbox (id, type, created_at)")

    logger.info("Applied migration 107: bridge_outbox table")


async def rollback(conn: Any) -> None:
    """Rollback migration 107 — drop bridge_outbox table."""
    logger.info("Rolling back migration 107: bridge_outbox table")

    await conn.execute("DROP INDEX IF EXISTS idx_outbox_created_at;")
    await conn.execute("DROP INDEX IF EXISTS idx_outbox_type;")
    await conn.execute("DROP INDEX IF EXISTS idx_outbox_id;")
    await conn.execute("DROP TABLE IF EXISTS bridge_outbox;")

    logger.info("Rolled back migration 107: bridge_outbox table")
