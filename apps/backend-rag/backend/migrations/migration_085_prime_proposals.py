"""
Migration 085: Prime Nexus Proposals table.

Stores investment proposal snapshots generated from Prime Nexus analysis.
Token-based public access for sharing proposals with potential investors.
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS prime_proposals (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE NOT NULL,
            lat DOUBLE PRECISION NOT NULL,
            lng DOUBLE PRECISION NOT NULL,
            zone_code TEXT,
            zone_name TEXT,
            kbli_code TEXT,
            verdict_label TEXT,
            verdict_score INTEGER,
            analysis_snapshot JSONB,
            pricing_snapshot JSONB,
            investor_name TEXT,
            investor_email TEXT,
            investor_nationality TEXT,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',
            viewed_at TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS idx_prime_proposals_token
            ON prime_proposals(token);
        CREATE INDEX IF NOT EXISTS idx_prime_proposals_status
            ON prime_proposals(status) WHERE status IN ('draft', 'sent');
    """)
    logger.info("Migration 085: prime_proposals table created")


async def downgrade(conn) -> None:
    await conn.execute("DROP TABLE IF EXISTS prime_proposals;")
    logger.info("Migration 085: prime_proposals table dropped")
