"""
Migration 072: Welcome Email Queue

Creates welcome_email_queue table for deferred welcome email delivery.
Replaces the in-process APScheduler delay (not resilient to auto_stop).
Processed every 15 min by Air cron → /api/cron/notifiers/welcome-pending.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS welcome_email_queue (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            scheduled_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (client_id)
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_welcome_email_queue_scheduled
        ON welcome_email_queue (scheduled_at ASC)
        WHERE scheduled_at IS NOT NULL
    """)

    logger.info("Migration 072 applied: welcome_email_queue created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS welcome_email_queue")
    logger.info("Migration 072 rolled back")
