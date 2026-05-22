"""WA Team Inbox Dashboard - SSE live message stream.

Read-only realtime endpoint for the local-only Bali Zero team WhatsApp
dashboard (apps/wa-dashboard/). Subscribes to PG `wa_message_inserted`
NOTIFY channel via asyncpg `add_listener`, filters messages per user via
RBAC, and fans them out to all connected SSE clients.

Companion: research/operations/specs/2026-05-23-wa-team-inbox-webapp.md (v3)
Devils-advocate v3 fixes applied:
  #1 SSE backpressure: put_nowait + drop-on-full (not blocking publish path)
  #5 Multi-tab: set-of-queues per user_email (not single-queue overwrite)
  #8 RBAC try/except in SSE generator (don't crash stream on DB error)
  #11 Last-Event-ID replay from header before going live

Compliance: UU PDP 27/2022 Pasal 26 (operator audit visibility), Pasal 39
(audit log). RBAC enforced per row via can_view_message().
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.crm_access import can_view_all_clients

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wa-dashboard", tags=["wa-dashboard"])

SSE_QUEUE_MAXSIZE = 100
SSE_KEEPALIVE_SECONDS = 15
SSE_REPLAY_WINDOW = 200


class WaSseManager:
    """Per-user multi-tab SSE fan-out manager.

    Devils-advocate fix #5: subscribers is dict[user_email, set[Queue]],
    not dict[user_email, Queue]. Multi-tab supported.

    Devils-advocate fix #1: publish uses put_nowait and drops on full
    queue rather than awaiting q.put(), so one stalled subscriber
    cannot freeze the entire fan-out.
    """

    def __init__(self) -> None:
        self.subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()
        self._drop_count = 0

    async def subscribe(self, user_email: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=SSE_QUEUE_MAXSIZE)
        async with self._lock:
            self.subscribers.setdefault(user_email, set()).add(q)
        logger.info(
            "wa-dashboard SSE subscribe user=%s tabs=%d",
            user_email,
            len(self.subscribers[user_email]),
        )
        return q

    async def unsubscribe(self, user_email: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            queues = self.subscribers.get(user_email)
            if queues is None:
                return
            queues.discard(q)
            if not queues:
                self.subscribers.pop(user_email, None)
        logger.info("wa-dashboard SSE unsubscribe user=%s", user_email)

    def publish(self, payload: dict[str, Any]) -> None:
        """Non-blocking fan-out. Drop on full queue (subscriber too slow)."""
        for user_email, queues in list(self.subscribers.items()):
            for q in list(queues):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    self._drop_count += 1
                    if self._drop_count % 50 == 1:
                        logger.warning(
                            "wa-dashboard SSE queue full user=%s drops=%d (slow subscriber)",
                            user_email,
                            self._drop_count,
                        )


sse_manager = WaSseManager()


async def can_view_message(
    pool: asyncpg.Pool, user_email: str, payload: dict[str, Any]
) -> bool:
    """RBAC check: can this user see this message?

    Devils-advocate fix #8: caller wraps this in try/except. Raises on DB
    error so caller decides drop-event vs terminate-stream policy.
    """
    if await can_view_all_clients(pool, user_email):
        return True
    team_phone = payload.get("team_member_phone")
    if not team_phone:
        return True
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM team_member_phone_authorizations
            WHERE user_email = $1 AND team_member_phone = $2 AND revoked_at IS NULL
            LIMIT 1
            """,
            user_email,
            team_phone,
        )
    return row is not None


async def fetch_full_message(pool: asyncpg.Pool, message_id: int) -> dict[str, Any] | None:
    """Pointer-only payload from trigger -> SELECT full row by id."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, direction, team_member_phone, counterpart_phone,
                   chat_type, group_jid, body, message_text, message_date,
                   media_type, attention_priority, client_id, practice_id
            FROM whatsapp_message_context
            WHERE id = $1
            """,
            message_id,
        )
    if row is None:
        return None
    return {
        "id": row["id"],
        "direction": row["direction"],
        "team_member_phone": row["team_member_phone"],
        "counterpart_phone": row["counterpart_phone"],
        "chat_type": row["chat_type"],
        "group_jid": row["group_jid"],
        "body": (row["body"] or row["message_text"] or "")[:4000],
        "message_date": row["message_date"].isoformat() if row["message_date"] else None,
        "media_type": row["media_type"],
        "attention_priority": row["attention_priority"],
        "client_id": row["client_id"],
        "practice_id": row["practice_id"],
    }


async def fetch_replay(
    pool: asyncpg.Pool, last_event_id: int, limit: int = SSE_REPLAY_WINDOW
) -> list[dict[str, Any]]:
    """Replay messages with id > last_event_id (devils-advocate fix #11).

    Bounded window — beyond that, client must do a full refresh.
    """
    if last_event_id <= 0:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, direction, team_member_phone, counterpart_phone,
                   chat_type, group_jid, body, message_text, message_date,
                   media_type, attention_priority, client_id, practice_id
            FROM whatsapp_message_context
            WHERE id > $1
            ORDER BY id ASC
            LIMIT $2
            """,
            last_event_id,
            limit,
        )
    return [
        {
            "id": r["id"],
            "direction": r["direction"],
            "team_member_phone": r["team_member_phone"],
            "counterpart_phone": r["counterpart_phone"],
            "chat_type": r["chat_type"],
            "group_jid": r["group_jid"],
            "body": (r["body"] or r["message_text"] or "")[:4000],
            "message_date": r["message_date"].isoformat() if r["message_date"] else None,
            "media_type": r["media_type"],
            "attention_priority": r["attention_priority"],
            "client_id": r["client_id"],
            "practice_id": r["practice_id"],
        }
        for r in rows
    ]


@router.get("/stream")
async def wa_dashboard_stream(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> EventSourceResponse:
    """SSE live stream of WA messages, filtered per user RBAC.

    Headers:
      Last-Event-ID: <int>  -- replay messages after this id (fix #11)
    """
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="missing user email")

    last_event_id_raw = request.headers.get("Last-Event-ID", "0")
    try:
        last_event_id = int(last_event_id_raw)
    except (TypeError, ValueError):
        last_event_id = 0

    q = await sse_manager.subscribe(user_email)

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        try:
            if last_event_id > 0:
                replay = await fetch_replay(pool, last_event_id)
                for msg in replay:
                    try:
                        if await can_view_message(pool, user_email, msg):
                            yield {
                                "id": str(msg["id"]),
                                "event": "wa_message",
                                "data": json.dumps(msg, default=str),
                            }
                    except Exception:
                        logger.exception("wa-dashboard SSE replay RBAC error")
                        continue

            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=SSE_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield {"event": "keepalive", "data": str(int(time.time()))}
                    continue
                try:
                    full = await fetch_full_message(pool, payload["id"])
                    if full is None:
                        continue
                    if not await can_view_message(pool, user_email, full):
                        continue
                    yield {
                        "id": str(full["id"]),
                        "event": "wa_message",
                        "data": json.dumps(full, default=str),
                    }
                except Exception:
                    logger.exception("wa-dashboard SSE per-message error (continuing)")
                    continue
        finally:
            await sse_manager.unsubscribe(user_email, q)

    return EventSourceResponse(event_generator())


@router.get("/stream/health")
async def wa_dashboard_stream_health() -> dict[str, Any]:
    """Diagnostic: connected users + tabs + drop count."""
    return {
        "users": len(sse_manager.subscribers),
        "total_tabs": sum(len(s) for s in sse_manager.subscribers.values()),
        "drops": sse_manager._drop_count,
    }
