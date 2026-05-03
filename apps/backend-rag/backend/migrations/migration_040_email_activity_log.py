"""
Migration 040: Email Activity Log

Creates tables for tracking email operations for weekly reporting.

Created: 2026-01-05
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create email activity log table."""

    logger.info("Applying migration 040: Email Activity Log")

    # Create email_activity_log table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS email_activity_log (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
            user_email TEXT NOT NULL,
            operation VARCHAR(50) NOT NULL,
            email_subject TEXT,
            recipient_email TEXT,
            has_attachments BOOLEAN DEFAULT FALSE,
            attachment_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_activity_user
        ON email_activity_log(user_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_activity_created
        ON email_activity_log(created_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_activity_user_created
        ON email_activity_log(user_id, created_at);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_activity_operation
        ON email_activity_log(operation);
    """)

    logger.info("Migration 040 applied successfully")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop email activity log table."""

    logger.info("Rolling back migration 040: Email Activity Log")

    await conn.execute("DROP TABLE IF EXISTS email_activity_log;")

    logger.info("Migration 040 rolled back successfully")
