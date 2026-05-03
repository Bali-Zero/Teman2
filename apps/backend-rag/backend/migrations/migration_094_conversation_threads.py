"""
Migration 094: Conversation threads for omnichannel unified inbox.

Creates conversation_threads table for grouping cross-channel messages
and adds thread_id FK to conversation_messages.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "094_conversation_threads"
DESCRIPTION = "Omnichannel: conversation_threads table + thread_id on conversation_messages"


async def check_if_applied(conn) -> bool:
    """Check if migration has been applied."""
    return await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'conversation_threads')"
    )


async def apply(conn) -> None:
    """Apply migration: create conversation_threads and add thread_id to conversation_messages."""
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_threads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'assigned', 'waiting', 'resolved', 'closed')),
            priority TEXT NOT NULL DEFAULT 'normal'
                CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
            assigned_to TEXT,
            subject TEXT,
            channels TEXT[] DEFAULT '{}',
            intent TEXT,
            unread_count INTEGER NOT NULL DEFAULT 0,
            last_message_preview TEXT,
            last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'::jsonb
        )
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_threads_status ON conversation_threads(status, last_activity_at DESC)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_threads_assigned ON conversation_threads(assigned_to, status) WHERE assigned_to IS NOT NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_threads_client ON conversation_threads(client_id, last_activity_at DESC) WHERE client_id IS NOT NULL"
    )

    # Add thread_id to existing conversation_messages
    col_exists = await conn.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'conversation_messages' AND column_name = 'thread_id'
        )
    """)
    if not col_exists:
        await conn.execute(
            "ALTER TABLE conversation_messages ADD COLUMN thread_id UUID REFERENCES conversation_threads(id) ON DELETE SET NULL"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_thread ON conversation_messages(thread_id, created_at) WHERE thread_id IS NOT NULL"
        )

    logger.info(f"Migration {MIGRATION_ID} applied successfully")
