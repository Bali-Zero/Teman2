"""
Migration 095: Backfill conversation_threads from existing messages.

Groups existing conversation_messages by client_id (or sender_id for
unidentified users) into threads. Idempotent: skips messages already threaded.
"""

import json
import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "095_backfill_threads"
DESCRIPTION = "Omnichannel: backfill conversation_threads from existing messages"


async def check_if_applied(conn) -> bool:
    """Check if backfill has been applied.

    Returns True only when there are no unthreaded messages with a client_id.
    This avoids false positives if live threads are created before backfill runs.
    """
    unthreaded = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM conversation_messages WHERE thread_id IS NULL AND client_id IS NOT NULL LIMIT 1)"
    )
    return not unthreaded


async def apply(conn) -> None:
    """Backfill threads by grouping messages per client_id or sender_id."""
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    # Group by client_id (identified users)
    client_groups = await conn.fetch("""
        SELECT client_id, array_agg(DISTINCT channel) as channels,
               MIN(created_at) as first_msg, MAX(created_at) as last_msg,
               COUNT(*) as msg_count
        FROM conversation_messages
        WHERE client_id IS NOT NULL AND thread_id IS NULL
        GROUP BY client_id
    """)

    threaded = 0
    for group in client_groups:
        channels = group["channels"] or []
        thread_id = await conn.fetchval("""
            INSERT INTO conversation_threads (client_id, channels, last_activity_at, created_at, subject)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """,
            group["client_id"],
            channels,
            group["last_msg"],
            group["first_msg"],
            f"Backfilled thread ({group['msg_count']} messages)",
        )

        await conn.execute("""
            UPDATE conversation_messages SET thread_id = $1
            WHERE client_id = $2 AND thread_id IS NULL
        """, thread_id, group["client_id"])
        threaded += 1

    # Group by sender_id (unidentified users)
    sender_groups = await conn.fetch("""
        SELECT sender_id, array_agg(DISTINCT channel) as channels,
               MIN(created_at) as first_msg, MAX(created_at) as last_msg,
               COUNT(*) as msg_count
        FROM conversation_messages
        WHERE client_id IS NULL AND thread_id IS NULL AND sender_id IS NOT NULL
        GROUP BY sender_id
    """)

    for group in sender_groups:
        channels = group["channels"] or []
        thread_id = await conn.fetchval("""
            INSERT INTO conversation_threads (channels, last_activity_at, created_at, subject,
                                              metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
        """,
            channels,
            group["last_msg"],
            group["first_msg"],
            f"Unidentified sender ({group['msg_count']} messages)",
            json.dumps({"sender_id": group["sender_id"]}),
        )

        await conn.execute("""
            UPDATE conversation_messages SET thread_id = $1
            WHERE sender_id = $2 AND client_id IS NULL AND thread_id IS NULL
        """, thread_id, group["sender_id"])
        threaded += 1

    logger.info(f"Migration {MIGRATION_ID}: backfilled {threaded} threads")
