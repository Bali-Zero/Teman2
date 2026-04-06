"""
Migration 086: Channel Dead Letter Queue (DLQ) table.

Stores failed outbound messages for retry with exponential backoff.
Ensures no message is silently lost when channel APIs are down.
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS failed_messages (
            id BIGSERIAL PRIMARY KEY,
            channel TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            sender_id TEXT,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}'::jsonb,
            error_message TEXT,
            error_type TEXT DEFAULT 'send_failure',
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            next_retry_at TIMESTAMPTZ,
            status TEXT DEFAULT 'pending'
                CHECK (status IN ('pending', 'retrying', 'exhausted', 'delivered')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_failed_msg_retry
            ON failed_messages (status, next_retry_at)
            WHERE status IN ('pending', 'retrying');

        CREATE INDEX IF NOT EXISTS idx_failed_msg_channel
            ON failed_messages (channel, created_at DESC);
    """)
    logger.info("✅ Migration 086: failed_messages DLQ table created")


async def rollback(conn) -> None:
    await conn.execute("DROP TABLE IF EXISTS failed_messages;")
    logger.info("⏪ Migration 086: failed_messages table dropped")
