"""WA Meta Inbox API — read/write console for the Meta WhatsApp Business number.

Backs the local desktop console (apps/wa-meta-inbox, localhost:7791) which is a
thin proxy: it never touches the DB directly, only these authenticated Fly
endpoints. Spec: docs/superpowers/specs/2026-06-03-wa-meta-inbox-design.md
(sezione 4, panel-approved).

Auth model (least-privilege, route-level scoping — sezione 4):
  - The HybridAuthMiddleware authenticates any valid X-API-Key in
    ``settings.api_keys`` (the wa-inbox key contains "secret" so it gets POST
    capability there).
  - These routes add a dependency that requires the X-API-Key header to EQUAL
    ``settings.wa_inbox_api_key`` exactly. A generic admin key therefore cannot
    read or write the Meta inbox — only the dedicated key can.
  - /api/wa-inbox/* is NOT in PUBLIC_ENDPOINTS (stays authenticated).

Endpoints:
  GET  /api/wa-inbox/threads                     — keyset-paginated thread list
  GET  /api/wa-inbox/threads/{id}/messages       — ledger for one thread
  POST /api/wa-inbox/threads/{id}/send           — human reply (24h-gated)
  POST /api/wa-inbox/threads/{id}/takeover       — bot OFF for this thread
  POST /api/wa-inbox/threads/{id}/release         — bot ON for this thread
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.deps.database import get_database_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wa-inbox", tags=["wa-meta-inbox"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
CUSTOMER_WINDOW_HOURS = 24


# ──────────────────────────────────────────────────────────────────────────
# Auth: route-level scoped dependency (X-API-Key must equal wa_inbox_api_key)
# ──────────────────────────────────────────────────────────────────────────
def require_wa_inbox_key(request: Request) -> None:
    """Reject unless the X-API-Key header equals settings.wa_inbox_api_key.

    Defense-in-depth on top of the middleware: even an authenticated admin key
    is rejected here unless it is the dedicated wa-inbox key. Constant-time
    comparison. 401 if the key is missing, wrong, or not configured server-side.
    """
    configured = settings.wa_inbox_api_key
    provided = request.headers.get("X-API-Key")
    if not configured or not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(status_code=401, detail="wa-inbox key required")


# ──────────────────────────────────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────────────────────────────────
class ThreadSummary(BaseModel):
    thread_id: int
    counterpart_phone: str
    counterpart_name: str | None = None
    human_handling: bool
    last_customer_at: datetime | None = None
    last_message_at: datetime | None = None
    window_open: bool


class ThreadsPage(BaseModel):
    items: list[ThreadSummary]
    next_cursor: str | None = None


class LedgerMessage(BaseModel):
    id: int
    meta_message_id: str | None = None
    direction: str
    sender_role: str
    body: str | None = None
    media_type: str | None = None
    status: str
    error: str | None = None
    created_at: datetime
    sent_at: datetime | None = None


class ThreadMessages(BaseModel):
    thread_id: int
    human_handling: bool
    last_customer_at: datetime | None = None
    window_open: bool
    items: list[LedgerMessage]


class SendRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)
    idempotency_key: str = Field(..., min_length=1, max_length=128)


class SendResponse(BaseModel):
    message_id: int
    status: str


class HandlingResponse(BaseModel):
    thread_id: int
    human_handling: bool


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────
def _parse_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    """Parse a keyset cursor "<iso_ts>,<thread_id>" → (ts, thread_id)."""
    if not cursor:
        return None
    try:
        ts_part, id_part = cursor.rsplit(",", 1)
        return datetime.fromisoformat(ts_part), int(id_part)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc


def _thread_summary(row: asyncpg.Record) -> ThreadSummary:
    return ThreadSummary(
        thread_id=row["thread_id"],
        counterpart_phone=row["counterpart_phone"],
        counterpart_name=row["counterpart_name"],
        human_handling=row["human_handling"],
        last_customer_at=row["last_customer_at"],
        last_message_at=row["last_message_at"],
        window_open=bool(row["window_open"]),
    )


# ──────────────────────────────────────────────────────────────────────────
# GET /threads — keyset pagination (last_message_at DESC, thread_id DESC)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/threads", response_model=ThreadsPage, dependencies=[Depends(require_wa_inbox_key)])
async def list_threads(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: str | None = Query(None),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ThreadsPage:
    parsed = _parse_cursor(cursor)

    select = """
        SELECT thread_id, counterpart_phone, counterpart_name, human_handling,
               last_customer_at, last_message_at,
               (last_customer_at IS NOT NULL
                AND NOW() - last_customer_at < ($WINDOW * INTERVAL '1 hour')) AS window_open
        FROM meta_inbox_threads
    """.replace("$WINDOW", str(CUSTOMER_WINDOW_HOURS))

    async with pool.acquire() as conn:
        if parsed is None:
            rows = await conn.fetch(
                select
                + """
                ORDER BY last_message_at DESC NULLS LAST, thread_id DESC
                LIMIT $1
                """,
                limit + 1,
            )
        else:
            cur_ts, cur_id = parsed
            rows = await conn.fetch(
                select
                + """
                WHERE (last_message_at, thread_id) < ($2, $3)
                ORDER BY last_message_at DESC NULLS LAST, thread_id DESC
                LIMIT $1
                """,
                limit + 1,
                cur_ts,
                cur_id,
            )

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        if last["last_message_at"] is not None:
            next_cursor = f"{last['last_message_at'].isoformat()},{last['thread_id']}"

    return ThreadsPage(items=[_thread_summary(r) for r in rows], next_cursor=next_cursor)


# ──────────────────────────────────────────────────────────────────────────
# GET /threads/{id}/messages — ledger ASC + thread state
# ──────────────────────────────────────────────────────────────────────────
@router.get(
    "/threads/{thread_id}/messages",
    response_model=ThreadMessages,
    dependencies=[Depends(require_wa_inbox_key)],
)
async def get_thread_messages(
    thread_id: int,
    before: int | None = Query(None, description="Ledger id; return rows older than this"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ThreadMessages:
    async with pool.acquire() as conn:
        thread = await conn.fetchrow(
            """
            SELECT thread_id, human_handling, last_customer_at,
                   (last_customer_at IS NOT NULL
                    AND NOW() - last_customer_at < ($2 * INTERVAL '1 hour')) AS window_open
            FROM meta_inbox_threads
            WHERE thread_id = $1
            """,
            thread_id,
            CUSTOMER_WINDOW_HOURS,
        )
        if thread is None:
            raise HTTPException(status_code=404, detail="thread not found")

        if before is None:
            rows = await conn.fetch(
                """
                SELECT id, meta_message_id, direction, sender_role, body,
                       media_type, status, error, created_at, sent_at
                FROM meta_inbox_messages
                WHERE thread_id = $1
                ORDER BY id DESC
                LIMIT $2
                """,
                thread_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, meta_message_id, direction, sender_role, body,
                       media_type, status, error, created_at, sent_at
                FROM meta_inbox_messages
                WHERE thread_id = $1 AND id < $3
                ORDER BY id DESC
                LIMIT $2
                """,
                thread_id,
                limit,
                before,
            )

    # Return chronological ASC for the UI.
    items = [LedgerMessage(**dict(r)) for r in reversed(rows)]
    return ThreadMessages(
        thread_id=thread["thread_id"],
        human_handling=thread["human_handling"],
        last_customer_at=thread["last_customer_at"],
        window_open=bool(thread["window_open"]),
        items=items,
    )


# ──────────────────────────────────────────────────────────────────────────
# POST /threads/{id}/send — human reply (24h-gated, idempotent)
# ──────────────────────────────────────────────────────────────────────────
@router.post(
    "/threads/{thread_id}/send",
    response_model=SendResponse,
    dependencies=[Depends(require_wa_inbox_key)],
)
async def send_message(
    thread_id: int,
    body: SendRequest,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SendResponse:
    async with pool.acquire() as conn:
        thread = await conn.fetchrow(
            """
            SELECT thread_id,
                   (last_customer_at IS NOT NULL
                    AND NOW() - last_customer_at < ($2 * INTERVAL '1 hour')) AS window_open
            FROM meta_inbox_threads
            WHERE thread_id = $1
            """,
            thread_id,
            CUSTOMER_WINDOW_HOURS,
        )
        if thread is None:
            raise HTTPException(status_code=404, detail="thread not found")
        if not thread["window_open"]:
            raise HTTPException(status_code=409, detail="window_closed")

        async with conn.transaction():
            ledger = await conn.fetchrow(
                """
                INSERT INTO meta_inbox_messages (
                    thread_id, direction, sender_role, body, status, idempotency_key
                )
                VALUES ($1, 'outbound', 'human', $2, 'queued', $3)
                ON CONFLICT (thread_id, idempotency_key) DO NOTHING
                RETURNING id
                """,
                thread_id,
                body.text,
                body.idempotency_key,
            )

            if ledger is None:
                # Idempotency replay — return the previously created row id.
                existing = await conn.fetchrow(
                    """
                    SELECT id, status FROM meta_inbox_messages
                    WHERE thread_id = $1 AND idempotency_key = $2
                    """,
                    thread_id,
                    body.idempotency_key,
                )
                if existing is None:
                    # Extremely unlikely race; surface as conflict.
                    raise HTTPException(status_code=409, detail="idempotency_conflict")
                return SendResponse(message_id=existing["id"], status=existing["status"])

            message_id = ledger["id"]

            # Human send → operator owns the thread; bot OFF.
            await conn.execute(
                "UPDATE meta_inbox_threads SET human_handling = true WHERE thread_id = $1",
                thread_id,
            )
            await conn.execute(
                """
                INSERT INTO wa_outbox (thread_id, message_id, needs_generation, status)
                VALUES ($1, $2, false, 'pending')
                ON CONFLICT (message_id) DO NOTHING
                """,
                thread_id,
                message_id,
            )

    return SendResponse(message_id=message_id, status="queued")


# ──────────────────────────────────────────────────────────────────────────
# POST /threads/{id}/takeover — human wins always (no version check)
# ──────────────────────────────────────────────────────────────────────────
@router.post(
    "/threads/{thread_id}/takeover",
    response_model=HandlingResponse,
    dependencies=[Depends(require_wa_inbox_key)],
)
async def takeover(
    thread_id: int,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> HandlingResponse:
    async with pool.acquire() as conn:
        async with conn.transaction():
            updated = await conn.fetchrow(
                """
                UPDATE meta_inbox_threads
                SET human_handling = true, handling_version = handling_version + 1
                WHERE thread_id = $1
                RETURNING thread_id, human_handling
                """,
                thread_id,
            )
            if updated is None:
                raise HTTPException(status_code=404, detail="thread not found")

            # Cancel any pending/generating bot outbox for this thread so a
            # half-claimed bot reply cannot still go out after the takeover.
            await conn.execute(
                """
                UPDATE wa_outbox o
                SET status = 'failed', claim_token = NULL, claimed_at = NULL,
                    claim_expires_at = NULL
                FROM meta_inbox_messages m
                WHERE o.message_id = m.id
                  AND o.thread_id = $1
                  AND o.status IN ('pending', 'generating', 'claimed')
                  AND o.needs_generation = true
                """,
                thread_id,
            )
            await conn.execute(
                """
                UPDATE meta_inbox_messages
                SET status = 'failed', error = 'aborted_human_takeover'
                WHERE thread_id = $1
                  AND sender_role = 'bot'
                  AND status IN ('queued', 'generating')
                """,
                thread_id,
            )

    return HandlingResponse(thread_id=updated["thread_id"], human_handling=updated["human_handling"])


# ──────────────────────────────────────────────────────────────────────────
# POST /threads/{id}/release — bot ON again
# ──────────────────────────────────────────────────────────────────────────
@router.post(
    "/threads/{thread_id}/release",
    response_model=HandlingResponse,
    dependencies=[Depends(require_wa_inbox_key)],
)
async def release(
    thread_id: int,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> HandlingResponse:
    async with pool.acquire() as conn:
        updated = await conn.fetchrow(
            """
            UPDATE meta_inbox_threads
            SET human_handling = false, handling_version = handling_version + 1
            WHERE thread_id = $1
            RETURNING thread_id, human_handling
            """,
            thread_id,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="thread not found")

    return HandlingResponse(thread_id=updated["thread_id"], human_handling=updated["human_handling"])


__all__ = ["require_wa_inbox_key", "router"]
