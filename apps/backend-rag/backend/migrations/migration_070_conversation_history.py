"""
Migration 068: Unified Conversation History

Cross-channel message storage for all 7 communication channels.
Enables AI to see full client history across WhatsApp, Telegram, Web, etc.

Architecture:
- ChannelMessage dataclass (channels/base.py) already normalizes format
- This table persists what was previously ephemeral
- Indexed by client_id + timestamp for fast retrieval
"""

UPGRADE_SQL = """
-- Unified conversation messages (cross-channel)
CREATE TABLE IF NOT EXISTS conversation_messages (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER,
    channel TEXT NOT NULL,
    direction TEXT NOT NULL,
    sender_id TEXT,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookup by client + time (most common query)
CREATE INDEX IF NOT EXISTS idx_conv_client_time
    ON conversation_messages (client_id, created_at DESC);

-- Channel-specific queries
CREATE INDEX IF NOT EXISTS idx_conv_channel
    ON conversation_messages (channel, created_at DESC);

-- Full-text search on content
CREATE INDEX IF NOT EXISTS idx_conv_content_gin
    ON conversation_messages USING GIN (to_tsvector('english', content));

COMMENT ON TABLE conversation_messages IS 'Unified cross-channel conversation history. Feeds LangGraph context and AI memory.';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS conversation_messages CASCADE;
"""


async def upgrade(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UPGRADE_SQL)


async def downgrade(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWNGRADE_SQL)
