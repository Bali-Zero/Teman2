"""
Migration 034: Google Drive OAuth Tokens Table

Creates the google_drive_tokens table for storing user OAuth tokens.
"""

import asyncpg


async def migrate(conn: asyncpg.Connection) -> None:
    """
    Create Google Drive OAuth tokens table.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS google_drive_tokens (
            user_id VARCHAR(255) PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_gdrive_tokens_expires
        ON google_drive_tokens(expires_at);
    """)

    print("[Migration 034] Created google_drive_tokens table")


async def rollback(conn: asyncpg.Connection) -> None:
    """
    Remove Google Drive OAuth tokens table.
    """
    await conn.execute("DROP TABLE IF EXISTS google_drive_tokens;")
    print("[Migration 034] Dropped google_drive_tokens table")
