"""
Telegram Conversations API - Ultra-Safe Version
"""

import json
import logging
from typing import Any

from asyncpg import Pool
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.get("/conversations")
async def get_telegram_conversations(
    limit: int = 50, offset: int = 0, db: Pool = Depends(get_database),
) -> Any:
    try:
        async with db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, session_id, user_id, messages, metadata, created_at FROM conversations "
                "WHERE session_id LIKE 'tg_session_%' OR user_id LIKE 'telegram_%' "
                "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit,
                offset,
            )
            conversations = []
            for row in rows:
                session_id = row["session_id"] or ""
                chat_id = session_id.replace("tg_session_", "")

                messages_raw = row["messages"]
                last_msg_text = "Click to view Telegram messages"
                try:
                    msgs = (
                        json.loads(messages_raw) if isinstance(messages_raw, str) else messages_raw
                    )
                    if msgs and isinstance(msgs, list):
                        last_msg_text = msgs[-1].get("content", "")[:100]
                except Exception as e:
                    logger.error(f"Failed to parse Telegram messages: {e}")
                    pass

                metadata_raw = row["metadata"]
                client_name = f"TG: {chat_id}"
                try:
                    meta = (
                        json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
                    )
                    client_name = meta.get("sender_name") or meta.get("client_name") or client_name
                except Exception as e:
                    logger.error(f"Failed to parse Telegram metadata: {e}")
                    pass

                conversations.append(
                    {
                        "id": row["id"],
                        "chat_id": chat_id,
                        "client_name": client_name,
                        "last_message": last_msg_text,
                        "last_message_date": row["created_at"].isoformat(),
                        "session_id": session_id,
                    },
                )
            return conversations
    except Exception as e:
        logger.error(f"TG FAIL: {e}")
        return []


@router.get("/messages/{chat_id}")
async def get_telegram_messages(
    chat_id: str, limit: int = 100, db: Pool = Depends(get_database),
) -> Any:

    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, messages, created_at FROM conversations WHERE session_id = $1 ORDER BY created_at DESC LIMIT 1",
                f"tg_session_{chat_id}",
            )
            if not row:
                return []
            msgs = (
                json.loads(row["messages"]) if isinstance(row["messages"], str) else row["messages"]
            )
            result = []
            for i, m in enumerate(msgs[-limit:]):
                if not isinstance(m, dict):
                    continue
                result.append(
                    {
                        "id": f"{row['id']}_{i}",
                        "message_text": m.get("content", ""),
                        "direction": "inbound" if m.get("role") == "user" else "outbound",
                        "timestamp": row["created_at"].isoformat(),
                    },
                )
            return result
    except Exception as e:
        logger.error(f"Failed to get Telegram messages: {e}")
        return []
