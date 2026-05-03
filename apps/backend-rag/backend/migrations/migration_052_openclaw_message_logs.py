"""
Migration 052: OpenClaw Message Logs

Purpose:
- Create openclaw_message_logs table for CRM interaction tracking
- Store message logs received from OpenClaw webhook
- Enable comprehensive communication history and analytics

Use Cases:
1. Track all customer interactions across channels (WhatsApp, SMS, etc.)
2. Maintain audit trail for compliance and quality assurance
3. Enable analytics on communication patterns and response times
4. Support session-based conversation threading

Author: Cascade (Windsurf)
Date: 2026-02-03
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create openclaw_message_logs table."""

    logger.info("Applying migration 052: OpenClaw Message Logs")

    # 1. Create openclaw_message_logs table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS openclaw_message_logs (
            message_id VARCHAR(255) PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            channel VARCHAR(50) NOT NULL,
            direction VARCHAR(20) NOT NULL,
            from_number VARCHAR(50) NOT NULL,
            to_number VARCHAR(50) NOT NULL,
            contact_name VARCHAR(255),
            message_text TEXT,
            media_type VARCHAR(50),
            session_id VARCHAR(255),
            reply_to VARCHAR(255),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    logger.info("✅ Created openclaw_message_logs table")

    # 2. Create indexes for efficient queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_openclaw_timestamp
        ON openclaw_message_logs(timestamp);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_openclaw_session_id
        ON openclaw_message_logs(session_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_openclaw_from_number
        ON openclaw_message_logs(from_number);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_openclaw_to_number
        ON openclaw_message_logs(to_number);
    """)

    logger.info("✅ Created indexes on openclaw_message_logs")

    # 3. Add helpful comments
    await conn.execute("""
        COMMENT ON TABLE openclaw_message_logs IS
        'Message logs from OpenClaw webhook for CRM interaction tracking';
    """)

    await conn.execute("""
        COMMENT ON COLUMN openclaw_message_logs.message_id IS
        'Unique message ID from OpenClaw (primary key)';
    """)

    await conn.execute("""
        COMMENT ON COLUMN openclaw_message_logs.session_id IS
        'Session ID for conversation threading';
    """)

    await conn.execute("""
        COMMENT ON COLUMN openclaw_message_logs.reply_to IS
        'Message ID this message is replying to';
    """)

    logger.info("Migration 052 applied successfully: OpenClaw Message Logs table created")
    print("✅ Applied migration 052: OpenClaw Message Logs")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop openclaw_message_logs table."""

    logger.info("Rolling back migration 052: OpenClaw Message Logs")

    # Drop indexes first
    await conn.execute("DROP INDEX IF EXISTS idx_openclaw_timestamp;")
    await conn.execute("DROP INDEX IF EXISTS idx_openclaw_session_id;")
    await conn.execute("DROP INDEX IF EXISTS idx_openclaw_from_number;")
    await conn.execute("DROP INDEX IF EXISTS idx_openclaw_to_number;")

    # Then drop table
    await conn.execute("DROP TABLE IF EXISTS openclaw_message_logs;")

    logger.info("Migration 052 rolled back successfully")
    print("⏪ Rolled back migration 052: OpenClaw Message Logs")
