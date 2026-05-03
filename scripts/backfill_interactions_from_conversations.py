#!/usr/bin/env python3
"""
Backfill interactions table from WhatsApp conversations in the conversations table.

Conversations with user_id like 'whatsapp_PHONE' or 'telegram_CHATID' are matched
to clients via phone_normalized or messaging_users table, then each conversation
session is recorded as a single interaction record.

Usage:
    cd /Users/nuzantara/Desktop/nuzantara
    source apps/backend-rag/.venv/bin/activate
    DATABASE_URL="postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag" \
        PYTHONPATH=apps/backend-rag python scripts/backfill_interactions_from_conversations.py [--dry-run]
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DRY_RUN = "--dry-run" in sys.argv


async def backfill(conn: asyncpg.Connection) -> dict:
    stats = {"skipped": 0, "inserted": 0, "no_client_match": 0, "errors": 0}

    # Fetch all WhatsApp conversations
    wa_convos = await conn.fetch(
        """
        SELECT id, user_id, messages, metadata, created_at, last_message_at
        FROM conversations
        WHERE user_id LIKE 'whatsapp_%'
        ORDER BY created_at
        """
    )

    logger.info(f"Found {len(wa_convos)} WhatsApp conversations to process")

    for row in wa_convos:
        convo_id = row["id"]
        user_id = row["user_id"]  # e.g. whatsapp_628113819002
        phone_raw = user_id.replace("whatsapp_", "")

        # Match to client via phone_normalized
        client_row = await conn.fetchrow(
            """
            SELECT id FROM clients
            WHERE phone_normalized = $1
               OR phone_normalized = '+' || $1
               OR REPLACE(REPLACE(COALESCE(phone, ''), ' ', ''), '+', '') = $1
            AND deleted_at IS NULL
            LIMIT 1
            """,
            phone_raw,
        )

        if not client_row:
            logger.debug(f"No client match for {user_id} (phone: {phone_raw})")
            stats["no_client_match"] += 1
            continue

        client_id = client_row["id"]

        # Check if interaction already exists for this conversation
        existing = await conn.fetchval(
            "SELECT id FROM interactions WHERE conversation_id = $1 AND channel = 'whatsapp'",
            convo_id,
        )
        if existing:
            logger.debug(f"Interaction already exists for conversation {convo_id}, skipping")
            stats["skipped"] += 1
            continue

        # Build summary from messages (asyncpg returns JSONB as Python objects)
        raw_messages = row["messages"]
        if isinstance(raw_messages, str):
            import json as _json
            try:
                messages = _json.loads(raw_messages)
            except Exception:
                messages = []
        else:
            messages = raw_messages or []
        user_msgs = [m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        first_msg = user_msgs[0] if user_msgs else ""
        summary = first_msg[:200] if first_msg else f"WhatsApp conversation ({len(messages)} messages)"
        full_content = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}"
            for m in messages
            if isinstance(m, dict) and m.get("content")
        )[:5000]

        interaction_date = row["last_message_at"] or row["created_at"]

        if DRY_RUN:
            logger.info(
                f"[DRY-RUN] Would insert interaction: client={client_id} "
                f"convo={convo_id} date={interaction_date} summary={summary[:60]}..."
            )
            stats["inserted"] += 1
            continue

        try:
            await conn.execute(
                """
                INSERT INTO interactions
                    (client_id, conversation_id, type, channel, interaction_type,
                     title, content, summary, full_content, direction,
                     interaction_date, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT DO NOTHING
                """,
                client_id,
                convo_id,
                "chat",
                "whatsapp",
                "whatsapp",
                f"WhatsApp conversation",
                summary,
                summary,
                full_content,
                "inbound",
                interaction_date,
                "backfill_script",
            )
            logger.info(f"Inserted interaction for client={client_id} convo={convo_id}")
            stats["inserted"] += 1
        except Exception as e:
            logger.error(f"Error inserting interaction for convo {convo_id}: {e}")
            stats["errors"] += 1

    return stats


async def backfill_telegram(conn: asyncpg.Connection) -> dict:
    """Backfill Telegram conversations from messaging_users + conversations."""
    stats = {"skipped": 0, "inserted": 0, "no_client_match": 0, "errors": 0}

    # Get Telegram users linked to clients
    tg_users = await conn.fetch(
        """
        SELECT mu.telegram_chat_id, mu.client_id, mu.display_name
        FROM messaging_users mu
        WHERE mu.channel = 'telegram' AND mu.client_id IS NOT NULL
        """
    )
    logger.info(f"Found {len(tg_users)} Telegram users linked to clients")

    for tg_user in tg_users:
        chat_id = str(tg_user["telegram_chat_id"])
        client_id = tg_user["client_id"]

        # Find conversations for this Telegram user
        tg_convos = await conn.fetch(
            """
            SELECT id, messages, metadata, created_at, last_message_at
            FROM conversations
            WHERE user_id = $1 OR user_id = $2
            ORDER BY created_at
            """,
            f"telegram_{chat_id}",
            chat_id,
        )

        for row in tg_convos:
            convo_id = row["id"]

            existing = await conn.fetchval(
                "SELECT id FROM interactions WHERE conversation_id = $1 AND channel = 'telegram'",
                convo_id,
            )
            if existing:
                stats["skipped"] += 1
                continue

            raw_messages = row["messages"]
            if isinstance(raw_messages, str):
                import json as _json
                try:
                    messages = _json.loads(raw_messages)
                except Exception:
                    messages = []
            else:
                messages = raw_messages or []
            user_msgs = [m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"]
            first_msg = user_msgs[0] if user_msgs else ""
            summary = first_msg[:200] if first_msg else f"Telegram conversation ({len(messages)} messages)"
            full_content = "\n".join(
                f"[{m.get('role', 'unknown')}]: {m.get('content', '')}"
                for m in messages
                if m.get("content")
            )[:5000]

            interaction_date = row["last_message_at"] or row["created_at"]

            if DRY_RUN:
                logger.info(
                    f"[DRY-RUN] Would insert TG interaction: client={client_id} "
                    f"convo={convo_id}"
                )
                stats["inserted"] += 1
                continue

            try:
                await conn.execute(
                    """
                    INSERT INTO interactions
                        (client_id, conversation_id, type, channel, interaction_type,
                         title, content, summary, full_content, direction,
                         interaction_date, created_by)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT DO NOTHING
                    """,
                    client_id,
                    convo_id,
                    "chat",
                    "telegram",
                    "telegram",
                    "Telegram conversation",
                    summary,
                    summary,
                    full_content,
                    "inbound",
                    interaction_date,
                    "backfill_script",
                )
                logger.info(f"Inserted TG interaction for client={client_id} convo={convo_id}")
                stats["inserted"] += 1
            except Exception as e:
                logger.error(f"Error inserting TG interaction for convo {convo_id}: {e}")
                stats["errors"] += 1

    return stats


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable required")
        sys.exit(1)

    if DRY_RUN:
        logger.info("=== DRY RUN MODE — no changes will be written ===")

    conn = await asyncpg.connect(db_url)
    try:
        logger.info("Starting WhatsApp interactions backfill...")
        wa_stats = await backfill(conn)

        logger.info("Starting Telegram interactions backfill...")
        tg_stats = await backfill_telegram(conn)

        logger.info("=" * 50)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"WhatsApp: inserted={wa_stats['inserted']} skipped={wa_stats['skipped']} "
                    f"no_match={wa_stats['no_client_match']} errors={wa_stats['errors']}")
        logger.info(f"Telegram: inserted={tg_stats['inserted']} skipped={tg_stats['skipped']} "
                    f"no_match={tg_stats['no_client_match']} errors={tg_stats['errors']}")

        # Verify
        total = await conn.fetchval("SELECT COUNT(*) FROM interactions")
        logger.info(f"Total interactions in DB: {total}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
