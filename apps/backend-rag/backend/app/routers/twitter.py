"""
Twitter/X Conversations API
Fast endpoints for omnichannel dashboard to view live Twitter DMs.
"""

import json
import logging

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.dependencies import get_current_user, get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twitter", tags=["twitter"])


@router.get("/conversations")
async def get_twitter_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Get Twitter/X conversations from Zan's sessions.
    Format compatible with frontend TwitterConversation type.
    """
    try:
        async with db.acquire() as conn:
            # Query conversations table where session_id starts with 'twitter_session_' or user_id starts with 'twitter_'
            rows = await conn.fetch(
                """
                SELECT 
                    c.id,
                    c.session_id,
                    c.user_id,
                    c.messages,
                    c.metadata,
                    c.created_at,
                    c.created_at as updated_at,
                    REGEXP_REPLACE(c.user_id, '^(twitter|x)_', '') as twitter_user_id,
                    NULL as client_id,
                    NULL as client_name
                FROM conversations c
                WHERE c.session_id LIKE 'twitter_session_%' 
                   OR c.session_id LIKE 'x_session_%'
                   OR c.user_id LIKE 'twitter_%'
                   OR c.user_id LIKE 'x_%'
                ORDER BY c.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

            conversations = []
            for row in rows:
                messages_raw = row["messages"]
                messages = []
                if isinstance(messages_raw, str):
                    try:
                        import json
                        messages = json.loads(messages_raw)
                    except:
                        messages = []
                else:
                    messages = messages_raw or []

                last_message = ""
                unread_count = 0

                if messages:
                    last_msg = messages[-1] if messages else {}
                    last_message = last_msg.get("content", "")[:200]

                    # Simple unread logic
                    last_assistant_idx = -1
                    for i in range(len(messages) - 1, -1, -1):
                        if messages[i].get("role") == "assistant":
                            last_assistant_idx = i
                            break

                    if last_assistant_idx >= 0:
                        unread_count = sum(
                            1
                            for msg in messages[last_assistant_idx + 1 :]
                            if msg.get("role") == "user"
                        )
                    else:
                        unread_count = len(messages)

                metadata = row["metadata"] or {}
                client_name = (
                    row["client_name"]
                    or metadata.get("client_name")
                    or metadata.get("sender_name")
                    or f"Twitter User {row['twitter_user_id']}"
                )

                conversations.append(
                    {
                        "id": row["id"],
                        "twitter_user_id": row["twitter_user_id"],
                        "username": metadata.get("username") or metadata.get("twitter_username"),
                        "client_id": row["client_id"],
                        "client_name": client_name,
                        "last_message": last_message,
                        "last_message_date": row["updated_at"].isoformat()
                        if row["updated_at"]
                        else row["created_at"].isoformat(),
                        "unread_count": unread_count,
                        "interaction_count": len(messages),
                    }
                )

            return conversations
    except Exception as e:
        logger.error(f"Failed to fetch Twitter conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")


@router.get("/messages/{twitter_user_id}")
async def get_twitter_messages(
    twitter_user_id: str,
    limit: int = 100,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Get messages for a specific Twitter user.
    """
    try:
        user_id = f"twitter_{twitter_user_id}"
        session_id = f"twitter_session_{twitter_user_id}"

        # Also try 'x_' prefix
        user_id_x = f"x_{twitter_user_id}"
        session_id_x = f"x_session_{twitter_user_id}"

        async with db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, messages, metadata, created_at, created_at as updated_at
                FROM conversations
                WHERE user_id IN ($1, $3) OR session_id IN ($2, $4)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id,
                session_id,
                user_id_x,
                session_id_x,
            )

            if not row:
                return []

            messages = row["messages"] or []
            result = []
            for i, msg in enumerate(messages[-limit:]):
                role = msg.get("role", "user")

                result.append(
                    {
                        "id": i,
                        "interaction_id": row["id"],
                        "twitter_user_id": twitter_user_id,
                        "message_text": msg.get("content", ""),
                        "direction": "inbound" if role == "user" else "outbound",
                        "timestamp": row["updated_at"].isoformat()
                        if row["updated_at"]
                        else row["created_at"].isoformat(),
                        "status": "read",
                    }
                )
            return result
    except Exception as e:
        logger.error(f"Failed to fetch Twitter messages for {twitter_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@router.post("/send")
async def send_twitter_message(
    request: Request,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Send Twitter message (Mock/Interaction record for now).
    """
    try:
        body = await request.json()
        twitter_user_id = body.get("twitter_user_id")
        text = body.get("text")

        if not twitter_user_id or not text:
            raise HTTPException(status_code=400, detail="Missing twitter_user_id or text")

        # NOTE: Actual Twitter API integration would go here
        logger.info(f"WOULD SEND Twitter message to {twitter_user_id}: {text}")

        # Save to conversation history anyway
        user_id = f"twitter_{twitter_user_id}"
        session_id = f"twitter_session_{twitter_user_id}"

        async with db.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, messages FROM conversations WHERE session_id = $1 OR user_id = $2",
                session_id,
                user_id,
            )

            new_msg = {"role": "assistant", "content": text}

            if existing:
                messages = existing["messages"] or []
                messages.append(new_msg)
                await conn.execute(
                    "UPDATE conversations SET messages = $1::jsonb WHERE id = $2",
                    json.dumps(messages),
                    existing["id"],
                )
            else:
                await conn.execute(
                    "INSERT INTO conversations (user_id, session_id, messages, created_at) VALUES ($1, $2, $3::jsonb, NOW())",
                    user_id,
                    session_id,
                    json.dumps([new_msg]),
                )

        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to record Twitter message: {e}")
        raise HTTPException(status_code=500, detail="Failed to record message")
