"""
Migration 060: Create x_monitored_tweets table for X social listening.

Stores tweets matched by keyword monitoring with intent classification
and optional CRM client linkage.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "060_x_monitored_tweets"

UP_SQL = """
CREATE TABLE IF NOT EXISTS x_monitored_tweets (
    id SERIAL PRIMARY KEY,
    tweet_id TEXT UNIQUE NOT NULL,
    author_id TEXT NOT NULL,
    author_handle TEXT,
    author_name TEXT,
    text TEXT NOT NULL,
    matched_keywords TEXT[] DEFAULT '{}',
    intent TEXT DEFAULT 'unknown',
    lead_score FLOAT DEFAULT 0.0,
    responded BOOLEAN DEFAULT FALSE,
    digested BOOLEAN DEFAULT FALSE,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tweet_created_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_x_monitored_tweets_intent ON x_monitored_tweets(intent);
CREATE INDEX IF NOT EXISTS idx_x_monitored_tweets_created ON x_monitored_tweets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_x_monitored_tweets_client ON x_monitored_tweets(client_id) WHERE client_id IS NOT NULL;
"""

DOWN_SQL = """
DROP TABLE IF EXISTS x_monitored_tweets;
"""


async def up(conn) -> None:
    """Apply migration."""
    await conn.execute(UP_SQL)
    logger.info(f"✅ Migration {MIGRATION_ID}: x_monitored_tweets table created")


async def down(conn) -> None:
    """Rollback migration."""
    await conn.execute(DOWN_SQL)
    logger.info(f"✅ Migration {MIGRATION_ID}: x_monitored_tweets table dropped")
