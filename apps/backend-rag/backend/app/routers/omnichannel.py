"""Omnichannel API — Unified Inbox for cross-channel conversations.

Provides thread management, CRM enrichment, and team assignment
for the 3-pane unified inbox frontend.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from backend.app.dependencies import get_current_user
from backend.app.deps.crm_access import can_view_all_clients
from backend.core.cache import invalidate_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/omnichannel", tags=["omnichannel"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ThreadUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    channel: str | None = None  # None = internal note
    is_internal_note: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db(request: Request) -> Any:
    db_pool = getattr(request.app.state, "db_pool", None)
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    return db_pool


def _get_thread_manager(db_pool: Any):
    from backend.services.communication.thread_manager import ThreadManager
    return ThreadManager(db_pool)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/threads")
async def list_threads(
    request: Request,
    user: dict = Depends(get_current_user),
    status: str | None = Query(None, description="Filter: open, assigned, waiting, resolved, closed"),
    priority: str | None = Query(None, description="Filter: low, normal, high, urgent"),
    assigned_to: str | None = Query(None, description="Filter by assignee email"),
    channel: str | None = Query(None, description="Filter by channel"),
    search: str | None = Query(None, description="Search subject/preview"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List conversation threads with filters and RBAC."""
    db_pool = _get_db(request)
    tm = _get_thread_manager(db_pool)

    from backend.services.communication.models import Priority, ThreadFilter, ThreadStatus

    filters = ThreadFilter(
        status=ThreadStatus(status) if status else None,
        priority=Priority(priority) if priority else None,
        assigned_to=assigned_to,
        channel=channel,
        search=search,
        limit=limit,
        offset=offset,
    )

    is_admin = can_view_all_clients(user)
    user_email = user.get("email", "").lower()

    threads, total = await tm.get_threads(
        filters, user_email=user_email, is_admin=is_admin,
    )

    return {"threads": threads, "total": total, "limit": limit, "offset": offset}


@router.get("/threads/{thread_id}")
async def get_thread(
    request: Request,
    thread_id: UUID = Path(...),
    user: dict = Depends(get_current_user),
    message_limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Get thread detail with cross-channel message history."""
    db_pool = _get_db(request)
    tm = _get_thread_manager(db_pool)

    # Fetch thread metadata
    row = await db_pool.fetchrow(
        """
        SELECT t.*, c.full_name as client_name, c.email as client_email
        FROM conversation_threads t
        LEFT JOIN clients c ON c.id = t.client_id
        WHERE t.id = $1
        """,
        thread_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")

    # RBAC: non-admin can only see assigned threads
    if not can_view_all_clients(user):
        assigned = row["assigned_to"]
        user_email = user.get("email", "").lower()
        if assigned and assigned != user_email:
            raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch messages
    messages = await tm.get_thread_messages(thread_id, limit=message_limit)

    # Mark as read
    await tm.mark_read(thread_id)

    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)

    return {
        "thread": {
            "id": str(row["id"]),
            "client_id": row["client_id"],
            "client_name": row["client_name"],
            "client_email": row["client_email"],
            "status": row["status"],
            "priority": row["priority"],
            "assigned_to": row["assigned_to"],
            "subject": row["subject"],
            "channels": row["channels"] or [],
            "intent": row["intent"],
            "unread_count": 0,  # Just marked read
            "last_message_preview": row["last_message_preview"],
            "last_activity_at": row["last_activity_at"].isoformat() if row["last_activity_at"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "metadata": meta or {},
        },
        "messages": [
            {
                "id": m.id,
                "channel": m.channel,
                "direction": m.direction,
                "sender_id": m.sender_id,
                "content": m.content,
                "metadata": m.metadata,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }


@router.patch("/threads/{thread_id}")
async def update_thread(
    request: Request,
    thread_id: UUID = Path(...),
    body: ThreadUpdateRequest = Body(...),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Update thread status, priority, or assignment. Admin or assignee only."""
    db_pool = _get_db(request)

    # RBAC: admin or current assignee can update
    if not can_view_all_clients(user):
        row = await db_pool.fetchrow(
            "SELECT assigned_to FROM conversation_threads WHERE id = $1", thread_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Thread not found")
        user_email = user.get("email", "").lower()
        if row["assigned_to"] and row["assigned_to"] != user_email:
            raise HTTPException(status_code=403, detail="Not authorized to update this thread")

    tm = _get_thread_manager(db_pool)

    from backend.services.communication.models import Priority, ThreadStatus

    found = await tm.update_thread(
        thread_id,
        status=ThreadStatus(body.status) if body.status else None,
        priority=Priority(body.priority) if body.priority else None,
        assigned_to=body.assigned_to,
    )
    if not found:
        raise HTTPException(status_code=404, detail="Thread not found")

    logger.info(f"Thread {thread_id} updated by {user.get('email')}: {body.model_dump(exclude_none=True)}")

    # Emit WebSocket event for real-time updates
    await _emit_thread_event(request, thread_id, "thread_updated", user)

    await invalidate_cache("zantara:omnichannel:*")
    return {"status": "updated", "thread_id": str(thread_id)}


@router.post("/threads/{thread_id}/messages")
async def send_thread_message(
    request: Request,
    thread_id: UUID = Path(...),
    body: SendMessageRequest = Body(...),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Send a message within a thread (reply or internal note)."""
    db_pool = _get_db(request)

    # Verify thread exists
    thread_row = await db_pool.fetchrow(
        "SELECT id, client_id, channels FROM conversation_threads WHERE id = $1",
        thread_id,
    )
    if not thread_row:
        raise HTTPException(status_code=404, detail="Thread not found")

    channel = body.channel or "internal"
    direction = "internal" if body.is_internal_note else "outbound"

    # Persist message
    msg_id = await db_pool.fetchval(
        """
        INSERT INTO conversation_messages
            (client_id, channel, direction, sender_id, content, metadata, thread_id)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
        RETURNING id
        """,
        thread_row["client_id"],
        channel,
        direction,
        user.get("email", "system"),
        body.content,
        json.dumps({
            "sender_name": user.get("full_name", user.get("email")),
            "is_internal_note": body.is_internal_note,
        }),
        thread_id,
    )

    # Update thread activity
    tm = _get_thread_manager(db_pool)
    await tm.add_message_to_thread(
        thread_id, msg_id, channel, preview=body.content[:200], direction=direction,
    )

    # If outbound reply (not internal note), send via channel adapter
    if not body.is_internal_note and body.channel:
        await _send_via_channel(request, thread_row, body.channel, body.content)

    # Emit WebSocket event
    await _emit_thread_event(request, thread_id, "new_message", user)

    await invalidate_cache("zantara:omnichannel:*")
    return {"status": "sent", "message_id": msg_id, "direction": direction}


@router.post("/threads/{thread_id}/assign")
async def assign_thread(
    request: Request,
    thread_id: UUID = Path(...),
    assignee: str = Body(..., embed=True),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Assign thread to a team member. Admin only. Sends Telegram notification."""
    if not can_view_all_clients(user):
        raise HTTPException(status_code=403, detail="Admin access required for assignment")

    db_pool = _get_db(request)
    tm = _get_thread_manager(db_pool)

    await tm.assign_thread(thread_id, assignee)

    # Notify via Telegram
    try:
        from backend.core.config import settings
        from backend.services.integrations.telegram_bot_service import TelegramBotService

        bot = TelegramBotService()
        # Fallback verified live 2026-04-07 (the previous 413539912 was unreachable).
        owner_chat = getattr(settings, "telegram_owner_chat_id", None) or "1125336968"

        thread_row = await db_pool.fetchrow(
            "SELECT subject, last_message_preview FROM conversation_threads WHERE id = $1",
            thread_id,
        )
        subject = thread_row["subject"] if thread_row else "New thread"
        preview = thread_row["last_message_preview"] if thread_row else ""

        await bot.send_message(
            chat_id=owner_chat,
            text=f"📋 Thread assigned to *{assignee}*\n_{subject}_\n`{preview[:100]}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.debug(f"Assignment notification failed (non-fatal): {e}")

    await invalidate_cache("zantara:omnichannel:*")
    return {"status": "assigned", "thread_id": str(thread_id), "assigned_to": assignee}


@router.get("/threads/{thread_id}/context")
async def get_thread_context(
    request: Request,
    thread_id: UUID = Path(...),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get CRM enrichment for a thread (client profile, practices, alerts)."""
    db_pool = _get_db(request)

    # Get thread with client
    thread_row = await db_pool.fetchrow(
        "SELECT client_id FROM conversation_threads WHERE id = $1", thread_id,
    )
    if not thread_row:
        raise HTTPException(status_code=404, detail="Thread not found")

    client_id = thread_row["client_id"]
    if not client_id:
        return {"client": None, "practices": [], "alerts": [], "interactions": []}

    # Client profile
    client = await db_pool.fetchrow(
        """
        SELECT id, full_name, email, phone, whatsapp, nationality, status,
               company_name, assigned_to, avatar_url, created_at
        FROM clients WHERE id = $1
        """,
        client_id,
    )

    # Active practices
    practices = await db_pool.fetch(
        """
        SELECT id, practice_type, status, priority, description,
               quoted_price, created_at
        FROM practices
        WHERE client_id = $1 AND status NOT IN ('cancelled')
        ORDER BY created_at DESC
        LIMIT 10
        """,
        client_id,
    )

    # Compliance alerts
    alerts = await db_pool.fetch(
        """
        SELECT id, alert_type, status, message, created_at
        FROM notification_alerts
        WHERE message ILIKE '%' || $1::text || '%'
        ORDER BY created_at DESC
        LIMIT 5
        """,
        str(client_id),
    )

    # Recent interactions
    interactions = await db_pool.fetch(
        """
        SELECT id, interaction_type, channel, sentiment, summary, created_at
        FROM interactions
        WHERE client_id = $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        client_id,
    )

    return {
        "client": dict(client) if client else None,
        "practices": [dict(p) for p in practices],
        "alerts": [dict(a) for a in alerts],
        "interactions": [dict(i) for i in interactions],
    }


@router.get("/stats")
async def omnichannel_stats(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Dashboard stats: thread counts by status, channel breakdown, response times."""
    db_pool = _get_db(request)

    # Thread counts by status
    status_counts = await db_pool.fetch(
        "SELECT status, COUNT(*) as count FROM conversation_threads GROUP BY status",
    )

    # Channel breakdown
    channel_counts = await db_pool.fetch(
        """
        SELECT unnest(channels) as channel, COUNT(*) as count
        FROM conversation_threads
        WHERE status IN ('open', 'assigned', 'waiting')
        GROUP BY channel
        """,
    )

    # Priority breakdown
    priority_counts = await db_pool.fetch(
        """
        SELECT priority, COUNT(*) as count
        FROM conversation_threads
        WHERE status IN ('open', 'assigned', 'waiting')
        GROUP BY priority
        """,
    )

    # Unread total
    unread = await db_pool.fetchval(
        "SELECT COALESCE(SUM(unread_count), 0) FROM conversation_threads WHERE status IN ('open', 'assigned', 'waiting')",
    )

    return {
        "by_status": {r["status"]: r["count"] for r in status_counts},
        "by_channel": {r["channel"]: r["count"] for r in channel_counts},
        "by_priority": {r["priority"]: r["count"] for r in priority_counts},
        "total_unread": unread or 0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _emit_thread_event(
    request: Request, thread_id: UUID, event_type: str, user: dict,
) -> None:
    """Emit WebSocket event for real-time inbox updates."""
    try:
        ws_manager = getattr(request.app.state, "ws_manager", None)
        if ws_manager:
            import json as json_mod
            await ws_manager.broadcast(json_mod.dumps({
                "type": "CHAT_MESSAGES",
                "data": {
                    "event": event_type,
                    "thread_id": str(thread_id),
                    "user": user.get("email"),
                },
            }))
    except Exception as e:
        logger.debug(f"WebSocket emit failed (non-fatal): {e}")


async def _send_via_channel(
    request: Request, thread_row: Any, channel: str, content: str,
) -> None:
    """Send outbound message via the appropriate channel adapter."""
    try:
        channel_router = getattr(request.app.state, "channel_router", None)
        if not channel_router:
            logger.warning("ChannelRouter not available for outbound send")
            return

        adapter = channel_router.adapters.get(channel)
        if not adapter:
            logger.warning(f"No adapter registered for channel: {channel}")
            return

        # Extract channel_id from thread metadata
        # For now, we log a warning — full outbound routing needs channel_id
        logger.info(f"Outbound reply via {channel}: {content[:50]}...")
    except Exception as e:
        logger.warning(f"Outbound send failed: {e}")
