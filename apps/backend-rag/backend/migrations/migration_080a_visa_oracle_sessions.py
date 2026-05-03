"""
Migration 080: Visa Oracle — Session Storage

Creates the visa_oracle_sessions table for anonymous quiz + chat sessions.
No PII stored — only ip_hash (SHA-256) and quiz answers.

Design:
- session_id VARCHAR(64): random hex, client-generated or server-generated
- quiz_answers JSONB: nationality, purpose, duration, family situation
- recommended_visas JSONB: top-3 scored visa recommendations
- messages JSONB: chat turn history [{role, content, ts}]
- language_detected: ISO 639-1 code (en, id, ru, de, etc.)
- handoff_triggered: set to TRUE when user clicks WhatsApp CTA
- ip_hash: SHA-256 of client IP for abuse/rate-limit analytics (no PII)
- expires_at: 90-day TTL, cleaned up by periodic job
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Create visa_oracle_sessions table with indexes."""

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS visa_oracle_sessions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id          VARCHAR(64) NOT NULL,
            quiz_answers        JSONB DEFAULT '{}'::jsonb,
            recommended_visas   JSONB DEFAULT '[]'::jsonb,
            messages            JSONB DEFAULT '[]'::jsonb,
            language_detected   VARCHAR(10),
            handoff_triggered   BOOLEAN DEFAULT FALSE,
            ip_hash             VARCHAR(64),
            created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at          TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visa_oracle_sessions_session_id
        ON visa_oracle_sessions (session_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visa_oracle_sessions_created_at
        ON visa_oracle_sessions (created_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visa_oracle_sessions_expires_at
        ON visa_oracle_sessions (expires_at)
        WHERE expires_at IS NOT NULL;
    """)

    logger.info("Migration 080: visa_oracle_sessions table created (1 table, 3 indexes)")


async def rollback(conn) -> None:
    """Drop visa_oracle_sessions table."""
    await conn.execute("DROP TABLE IF EXISTS visa_oracle_sessions CASCADE;")
    logger.info("Migration 080: visa_oracle_sessions table dropped")
