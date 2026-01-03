"""
Migration 033: Newsletter Subscribers Schema

Creates tables for blog newsletter subscriptions.

Created: 2025-12-31
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create newsletter subscribers table."""

    logger.info("Applying migration 033: Newsletter Subscribers")

    # Create newsletter_subscribers table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS newsletter_subscribers (
            id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
            email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255),
            categories TEXT[] DEFAULT ARRAY[]::TEXT[],
            frequency VARCHAR(20) DEFAULT 'weekly',
            language VARCHAR(5) DEFAULT 'en',
            confirmed BOOLEAN DEFAULT FALSE,
            confirmation_token VARCHAR(64),
            confirmation_sent_at TIMESTAMP WITH TIME ZONE,
            confirmed_at TIMESTAMP WITH TIME ZONE,
            unsubscribed_at TIMESTAMP WITH TIME ZONE,
            source VARCHAR(50) DEFAULT 'blog',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Create indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_newsletter_email
        ON newsletter_subscribers(email);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_newsletter_confirmed
        ON newsletter_subscribers(confirmed) WHERE confirmed = TRUE;
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_newsletter_frequency
        ON newsletter_subscribers(frequency) WHERE confirmed = TRUE AND unsubscribed_at IS NULL;
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_newsletter_categories
        ON newsletter_subscribers USING GIN(categories);
    """)

    # Create newsletter_send_log table for tracking sent newsletters
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS newsletter_send_log (
            id SERIAL PRIMARY KEY,
            article_id VARCHAR(255),
            newsletter_type VARCHAR(50) DEFAULT 'article',
            recipient_count INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_newsletter_log_sent
        ON newsletter_send_log(sent_at DESC);
    """)

    logger.info("Migration 033 applied successfully")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop newsletter tables."""

    logger.info("Rolling back migration 033: Newsletter Subscribers")

    await conn.execute("DROP TABLE IF EXISTS newsletter_send_log;")
    await conn.execute("DROP TABLE IF EXISTS newsletter_subscribers;")

    logger.info("Migration 033 rolled back successfully")
