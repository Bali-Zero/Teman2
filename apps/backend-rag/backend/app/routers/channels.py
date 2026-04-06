"""
Channel System API — Health, Stats, and Unified Conversation History.

Provides visibility into the multi-channel messaging system:
- Per-channel health status and metrics
- DLQ (Dead Letter Queue) stats
- Unified cross-channel conversation timeline
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from backend.app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.get("/health")
async def channel_health(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get health status for all registered channels.

    Returns per-channel: status (up/degraded/down), metrics, DLQ pending count.
    Admin-only endpoint.
    """
    channel_router = getattr(request.app.state, "channel_router", None)
    if not channel_router:
        return {"status": "unavailable", "channels": {}, "message": "ChannelRouter not initialized"}

    db_pool = getattr(request.app.state, "db_pool", None)

    # Collect per-channel metrics
    from backend.channels.optimizations import channel_metrics

    channels_health: dict[str, Any] = {}
    for name in channel_router.get_available_channels():
        stats = channel_metrics.get_stats(name) if channel_metrics else {}
        received = stats.get("messages_received", 0)
        errors = stats.get("errors", 0)
        error_rate = (errors / received * 100) if received > 0 else 0.0

        # Determine status
        if error_rate > 20:
            status = "degraded"
        elif error_rate > 50:
            status = "down"
        else:
            status = "up"

        channels_health[name] = {
            "status": status,
            "error_rate": f"{error_rate:.1f}%",
            **stats,
        }

    # DLQ summary
    dlq_summary = {"pending": 0, "retrying": 0, "exhausted": 0}
    if db_pool:
        try:
            rows = await db_pool.fetch(
                """
                SELECT status, COUNT(*) as cnt
                FROM failed_messages
                WHERE status IN ('pending', 'retrying', 'exhausted')
                GROUP BY status
                """,
            )
            for row in rows:
                dlq_summary[row["status"]] = row["cnt"]
        except Exception as e:
            logger.debug(f"DLQ query failed (table may not exist yet): {e}")

    # Overall status
    statuses = [ch["status"] for ch in channels_health.values()]
    if "down" in statuses:
        overall = "degraded"
    elif "degraded" in statuses:
        overall = "partial"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channels": channels_health,
        "dlq": dlq_summary,
        "registered_count": len(channels_health),
    }


@router.get("/stats")
async def channel_stats(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get detailed metrics for all channels."""
    from backend.channels.optimizations import channel_metrics

    if not channel_metrics:
        return {"stats": {}, "message": "Metrics not initialized"}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": channel_metrics.get_all_stats(),
    }


@router.get("/conversations")
async def unified_conversations(
    request: Request,
    _user: dict = Depends(get_current_user),
    channel: str | None = Query(None, description="Filter by channel (telegram, whatsapp, etc.)"),
    sender_id: str | None = Query(None, description="Filter by sender ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """
    Unified cross-channel conversation timeline.

    Returns messages from all channels sorted by timestamp, enabling
    a unified inbox view across WhatsApp, Telegram, Instagram, Web, and X.
    """
    db_pool = getattr(request.app.state, "db_pool", None)
    if not db_pool:
        return {"conversations": [], "message": "Database not available"}

    # Build query with filters
    conditions = []
    params: list[Any] = []
    param_idx = 1

    if channel:
        conditions.append(f"channel = ${param_idx}")
        params.append(channel)
        param_idx += 1

    if sender_id:
        conditions.append(f"sender_id = ${param_idx}")
        params.append(sender_id)
        param_idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params.extend([limit, offset])

    try:
        rows = await db_pool.fetch(
            f"""
            SELECT id, channel, direction, sender_id,
                   LEFT(content, 200) as content_preview,
                   metadata, created_at
            FROM conversation_messages
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
        )

        # Get total count
        count_row = await db_pool.fetchrow(
            f"SELECT COUNT(*) as total FROM conversation_messages {where_clause}",
            *params[:-2],  # Exclude limit/offset
        )
        total = count_row["total"] if count_row else 0

        conversations = []
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)

            conversations.append({
                "id": row["id"],
                "channel": row["channel"],
                "direction": row["direction"],
                "sender_id": row["sender_id"],
                "content_preview": row["content_preview"],
                "sender_name": (meta or {}).get("sender_name") or (meta or {}).get("first_name"),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        return {
            "conversations": conversations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Unified conversations query failed: {e}")
        return {"conversations": [], "total": 0, "error": str(e)}


@router.get("/dlq")
async def dlq_messages(
    request: Request,
    _user: dict = Depends(get_current_user),
    status: str = Query("pending", description="Filter by status: pending, retrying, exhausted, delivered"),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """View Dead Letter Queue messages for debugging failed deliveries."""
    db_pool = getattr(request.app.state, "db_pool", None)
    if not db_pool:
        return {"messages": [], "message": "Database not available"}

    try:
        rows = await db_pool.fetch(
            """
            SELECT id, channel, channel_id, LEFT(content, 200) as content_preview,
                   error_message, attempt_count, status, next_retry_at, created_at
            FROM failed_messages
            WHERE status = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            status, limit,
        )

        messages = [
            {
                "id": row["id"],
                "channel": row["channel"],
                "channel_id": row["channel_id"],
                "content_preview": row["content_preview"],
                "error": row["error_message"],
                "attempts": row["attempt_count"],
                "status": row["status"],
                "next_retry": row["next_retry_at"].isoformat() if row["next_retry_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

        return {"messages": messages, "count": len(messages)}

    except Exception as e:
        logger.debug(f"DLQ query failed: {e}")
        return {"messages": [], "error": str(e)}
