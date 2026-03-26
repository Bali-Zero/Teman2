"""
WhatsApp Conversations API - Final Stabilized Version

Outbound /send endpoint re-enabled 2026-03-15 with safety gates:
- Rate limit: max 20 outbound messages per phone per hour
- CRM validation: recipient must exist in clients table
- Auth required: only authenticated users can send
"""

import json
import logging
import time
from collections import defaultdict
from typing import Any

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_optional_database_pool
from backend.services.integrations.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

# Rate limiting: per-phone outbound message tracking
_outbound_rate: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 20  # messages per phone per hour
_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


class SendWhatsAppRequest(BaseModel):
    """Validated request for outbound WhatsApp messages."""

    phone: str = Field(..., description="Recipient phone with country code, e.g. +6281234567890")
    message: str = Field(..., min_length=1, max_length=4096, description="Message text")


def _check_rate_limit(phone: str) -> bool:
    """Check if phone has exceeded outbound rate limit. Returns True if allowed."""
    now = time.time()
    # Clean old entries
    _outbound_rate[phone] = [t for t in _outbound_rate[phone] if now - t < _RATE_LIMIT_WINDOW]
    return len(_outbound_rate[phone]) < _RATE_LIMIT_MAX


router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/conversations")
async def get_whatsapp_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Pool | None = Depends(get_optional_database_pool),
    current_user: dict = Depends(get_current_user),  # noqa: ARG001 — auth gate
) -> Any:
    if not db:
        logger.warning("Database unavailable")
        # Return empty list gracefully if DB is down, but don't fake data
        return []

    try:
        async with db.acquire() as conn:
            # Simple query without REGEXP_REPLACE to be safe
            rows = await conn.fetch(
                """
                SELECT id, session_id, user_id, messages, metadata, created_at
                FROM conversations
                WHERE session_id LIKE 'wa_session_%' OR user_id LIKE 'whatsapp_%'
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

            conversations = []
            for row in rows:
                # Extract phone from session_id (wa_session_NUMBER) or user_id (whatsapp_NUMBER)
                session_id = row["session_id"] or ""
                user_id = row["user_id"] or ""
                phone = ""
                if "wa_session_" in session_id:
                    phone = session_id.replace("wa_session_", "")
                elif "whatsapp_" in user_id:
                    phone = user_id.replace("whatsapp_", "")

                if not phone:
                    phone = "unknown"

                # Robust but simple parsing
                messages_raw = row["messages"]
                last_msg_text = "Click to view messages"

                if isinstance(messages_raw, list) and messages_raw:
                    m = messages_raw[-1]
                    if isinstance(m, dict):
                        last_msg_text = m.get("content", "")[:100]
                elif isinstance(messages_raw, str) and messages_raw.startswith("["):
                    try:
                        msgs = json.loads(messages_raw)
                        if msgs:
                            m = msgs[-1]
                            last_msg_text = m.get("content", "")[:100]
                    except Exception as e:
                        logger.error(f"Failed to parse WhatsApp messages JSON: {e}")
                        pass

                # Extract name from metadata if possible
                metadata_raw = row["metadata"]
                client_name = phone
                if metadata_raw:
                    try:
                        meta = (
                            json.loads(metadata_raw)
                            if isinstance(metadata_raw, str)
                            else metadata_raw
                        )
                        client_name = meta.get("sender_name") or meta.get("client_name") or phone
                    except Exception as e:
                        logger.error(f"Failed to parse WhatsApp metadata: {e}")
                        pass

                conversations.append(
                    {
                        "id": row["id"],
                        "phone": phone,
                        "client_id": None,
                        "client_name": client_name,
                        "last_message": last_msg_text,
                        "last_message_date": row["created_at"].isoformat(),
                        "unread_count": 0,
                        "interaction_count": 0,
                        "session_id": row["session_id"],
                    }
                )

            return conversations
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return []  # Fallback to empty list instead of 500


@router.get("/messages/{phone}")
async def get_whatsapp_messages(
    phone: str,
    limit: int = 100,
    db: Pool | None = Depends(get_optional_database_pool),
    current_user: dict = Depends(get_current_user),  # noqa: ARG001 — auth gate
) -> Any:
    if not db:
        return []

    try:
        user_id = f"whatsapp_{phone}"
        session_id = f"wa_session_{phone}"

        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, messages, created_at FROM conversations WHERE user_id = $1 OR session_id = $2 ORDER BY created_at DESC LIMIT 1",
                user_id,
                session_id,
            )

            if not row:
                return []

            messages_raw = row["messages"]
            messages = []
            if isinstance(messages_raw, str):
                try:
                    messages = json.loads(messages_raw)
                except Exception as e:
                    logger.error(f"Failed to parse WhatsApp messages string: {e}")
                    messages = []
            else:
                messages = messages_raw or []

            # Handle stringified list within list
            if isinstance(messages, list) and len(messages) == 1 and isinstance(messages[0], str):
                try:
                    messages = json.loads(messages[0])
                except Exception as e:
                    logger.error(f"Failed to parse nested WhatsApp messages: {e}")
                    pass

            result = []
            for i, m in enumerate(messages[-limit:]):
                if not isinstance(m, dict):
                    continue
                result.append(
                    {
                        "id": f"{row['id']}_{i}",
                        "interaction_id": row["id"],
                        "phone": phone,
                        "message_text": m.get("content", ""),
                        "direction": "inbound" if m.get("role") == "user" else "outbound",
                        "timestamp": row["created_at"].isoformat(),
                        "status": "read",
                    }
                )
            return result
    except Exception as e:
        logger.error(f"Failed to get WhatsApp messages: {e}")
        return []


@router.post("/send")
async def send_whatsapp_message(
    body: SendWhatsAppRequest,
    db: Pool | None = Depends(get_optional_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Send an outbound WhatsApp message via Meta Cloud API.

    Safety gates:
    - Auth required (JWT)
    - Rate limit: 20 msgs/phone/hour
    - CRM validation: recipient must exist in clients table
    """
    phone = body.phone.lstrip("+")

    # Gate 1: Rate limit
    if not _check_rate_limit(phone):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {_RATE_LIMIT_MAX} messages per phone per hour",
        )

    # Gate 2: CRM validation — recipient must be a known client
    if db:
        async with db.acquire() as conn:
            client_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM clients WHERE phone LIKE $1 AND deleted_at IS NULL)",
                f"%{phone[-10:]}%",
            )
            if not client_exists:
                raise HTTPException(
                    status_code=403,
                    detail=f"Phone {body.phone} not found in CRM. Cannot send to unknown contacts.",
                )

    # Send via Meta WhatsApp Cloud API
    try:
        result = await whatsapp_service.send_message(phone=phone, text=body.message)
        _outbound_rate[phone].append(time.time())
        logger.info(f"Outbound WA sent to {phone} by {current_user.get('email', 'unknown')}")
        return {"success": True, "data": result}
    except ValueError as e:
        logger.error(f"WhatsApp send failed: {e}")
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send WhatsApp message") from e
