"""
WhatsApp Conversations API
Fast endpoints for omnichannel dashboard to view Zan's live conversations.

Reads from 'conversations' table (Zan's chat history), not crm_interactions.
"""

import json
import logging
import time

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.dependencies import get_current_user, get_database, require_team_member

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/conversations")
async def get_whatsapp_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Get WhatsApp conversations from Zan's sessions.

    Returns list of conversations sorted by last update (most recent first).
    Format compatible with frontend WhatsAppConversation type.
    """
    try:
        logger.info("DEBUG: Entering get_whatsapp_conversations (Safe Mode v3)")
        async with db.acquire() as conn:
            # Query conversations table where session_id starts with 'wa_session_'
            # Extract phone from user_id (format: whatsapp_628213107363)
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
                    REGEXP_REPLACE(c.user_id, '^whatsapp_', '') as phone,
                    NULL as client_id,
                    NULL as client_name
                FROM conversations c
                WHERE c.session_id LIKE 'wa_session_%' OR c.user_id LIKE 'whatsapp_%'
                ORDER BY c.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

            conversations = []
            for row in rows:
                # Fast parsing for preview only
                messages_raw = row["messages"]
                last_message = ""
                interaction_count = 0
                
                if isinstance(messages_raw, list):
                    interaction_count = len(messages_raw)
                    if messages_raw:
                        last_msg = messages_raw[-1]
                        last_message = last_msg.get("content", "")[:200] if isinstance(last_msg, dict) else str(last_msg)[:200]
                elif isinstance(messages_raw, str):
                    # If it's a string, we just say "Long conversation" to avoid heavy json.loads
                    last_message = "New messages received"
                    interaction_count = 1

                unread_count = 0 # Default for performance

                # Get client name from metadata or crm.clients
                metadata = row["metadata"]
                if isinstance(metadata, str):
                    try:
                        import json
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                metadata = metadata or {}

                client_name = (
                    row["client_name"] or metadata.get("client_name") or metadata.get("sender_name")
                )

                conversations.append(
                    {
                        "id": row["id"],
                        "phone": row["phone"],
                        "client_id": row["client_id"],
                        "client_name": client_name,
                        "last_message": last_message,
                        "last_message_date": row["updated_at"].isoformat()
                        if row["updated_at"]
                        else row["created_at"].isoformat(),
                        "unread_count": unread_count,
                        "interaction_count": len(messages),
                        "session_id": row["session_id"],
                    }
                )

            logger.info(f"✅ Returned {len(conversations)} WhatsApp conversations")
            return conversations

    except Exception as e:
        logger.error(f"Failed to fetch WhatsApp conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")


@router.get("/messages/{phone}")
async def get_whatsapp_messages(
    phone: str,
    limit: int = 100,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(require_team_member),
):
    """
    Get messages for a specific WhatsApp phone number.

    Returns messages in chronological order (oldest first).
    Format compatible with frontend WhatsAppMessage type.
    """
    try:
        # Find conversation by phone
        user_id = f"whatsapp_{phone}"
        session_id = f"wa_session_{phone}"

        async with db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, messages, metadata, created_at, created_at as updated_at
                FROM conversations
                WHERE user_id = $1 OR session_id = $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id,
                session_id,
            )

            if not row:
                logger.warning(f"No conversation found for phone {phone}")
                return []

            # Ultra-robust parsing for messages history
            messages_raw = row["messages"]
            messages = []
            
            if isinstance(messages_raw, list):
                messages = messages_raw
            elif isinstance(messages_raw, str):
                try:
                    messages = json.loads(messages_raw)
                except:
                    messages = []
            
            # Handling list of string case
            if isinstance(messages, list) and len(messages) == 1 and isinstance(messages[0], str):
                try:
                    messages = json.loads(messages[0])
                except:
                    pass

            # Final string check
            if isinstance(messages, str):
                try:
                    messages = json.loads(messages)
                except:
                    messages = []

            # Convert to WhatsAppMessage format
            result = []
            for i, msg in enumerate(messages[-limit:]):
                if not isinstance(msg, dict):
                    # Fallback for weird data formats
                    logger.warning(f"Message at index {i} is not a dict: {msg}")
                    continue
                    
                role = msg.get("role", "user")
                content = msg.get("content", "")

                result.append(
                    {
                        "id": f"{row['id']}_{i}",
                        "interaction_id": row["id"],
                        "phone": phone,
                        "message_text": content,
                        "direction": "inbound" if role == "user" else "outbound",
                        "timestamp": row["updated_at"].isoformat()
                        if row["updated_at"]
                        else row["created_at"].isoformat(),
                        "status": "read",
                    }
                )

            logger.info(f"✅ Returned {len(result)} messages for phone {phone}")
            return result

    except Exception as e:
        logger.error(f"Failed to fetch messages for {phone}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@router.post("/send")
async def send_whatsapp_message(
    request: Request,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(require_team_member),
):
    """
    Send WhatsApp message from omnichannel dashboard.

    Body: { "phone": "628213107363", "text": "message", "reply_to": "optional_msg_id" }
    """
    try:
        body = await request.json()
        phone = body.get("phone")
        text = body.get("text")
        reply_to = body.get("reply_to")

        if not phone or not text:
            raise HTTPException(status_code=400, detail="Missing phone or text")

        # Send via WhatsApp service
        from backend.services.integrations.whatsapp_service import whatsapp_service

        await whatsapp_service.send_message(
            phone=phone,
            text=text,
            reply_to_message_id=reply_to,
        )

        # Save to conversation history
        user_id = f"whatsapp_{phone}"
        session_id = f"wa_session_{phone}"

        async with db.acquire() as conn:
            # Check if conversation exists
            existing = await conn.fetchrow(
                "SELECT id, messages FROM conversations WHERE session_id = $1",
                session_id,
            )

            new_msg = {"role": "assistant", "content": text}

            if existing:
                # Append to existing
                messages = existing["messages"] or []
                messages.append(new_msg)

                await conn.execute(
                    "UPDATE conversations SET messages = $1::jsonb WHERE id = $2",
                    json.dumps(messages),
                    existing["id"],
                )
            else:
                # Create new conversation
                await conn.execute(
                    """
                    INSERT INTO conversations (user_id, session_id, messages, created_at)
                    VALUES ($1, $2, $3::jsonb, NOW())
                    """,
                    user_id,
                    session_id,
                    json.dumps([new_msg]),
                )

        logger.info(f"✅ Message sent to {phone} from omnichannel dashboard")
        return {"success": True, "message_id": f"{phone}_{int(time.time())}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send message")
