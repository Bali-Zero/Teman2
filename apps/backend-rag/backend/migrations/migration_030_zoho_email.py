"""
Migration 030: Zoho Email Integration Schema

Creates tables for Zoho OAuth token storage and email caching.

Created: 2025-12-30
"""

from typing import Any
import logging

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create Zoho email integration tables."""

    logger.info("Applying migration 030: Zoho Email Integration")

    # Create zoho_email_tokens table for OAuth token storage
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS zoho_email_tokens (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
            account_id TEXT NOT NULL,
            email_address TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            token_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            scopes TEXT[],
            api_domain TEXT DEFAULT 'https://mail.zoho.com',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT zoho_tokens_user_account_unique UNIQUE(user_id, account_id)
        );
    """)

    # Create indexes for zoho_email_tokens
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoho_tokens_user
        ON zoho_email_tokens(user_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoho_tokens_expires
        ON zoho_email_tokens(token_expires_at);
    """)

    # Create zoho_email_cache table for offline access and performance
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS zoho_email_cache (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
            message_id TEXT NOT NULL,
            folder_id TEXT NOT NULL,
            thread_id TEXT,
            subject TEXT,
            sender_email TEXT,
            sender_name TEXT,
            recipients JSONB DEFAULT '{"to": [], "cc": [], "bcc": []}'::jsonb,
            snippet TEXT,
            has_attachments BOOLEAN DEFAULT FALSE,
            is_read BOOLEAN DEFAULT FALSE,
            is_flagged BOOLEAN DEFAULT FALSE,
            received_at TIMESTAMP WITH TIME ZONE,
            cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT zoho_cache_user_message_unique UNIQUE(user_id, message_id)
        );
    """)

    # Create indexes for zoho_email_cache
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoho_cache_user_folder
        ON zoho_email_cache(user_id, folder_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoho_cache_received
        ON zoho_email_cache(received_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zoho_cache_unread
        ON zoho_email_cache(user_id, is_read) WHERE is_read = FALSE;
    """)

    logger.info("Migration 030 applied successfully")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop Zoho email integration tables."""

    logger.info("Rolling back migration 030: Zoho Email Integration")

    # Drop tables in reverse order (cache first due to no FK, then tokens)
    await conn.execute("DROP TABLE IF EXISTS zoho_email_cache;")
    await conn.execute("DROP TABLE IF EXISTS zoho_email_tokens;")

    logger.info("Migration 030 rolled back successfully")
