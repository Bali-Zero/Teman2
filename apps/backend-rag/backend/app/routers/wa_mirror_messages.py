"""Read-only wa-mirror message timeline API.

This router exposes CRM-safe projections of rows captured by apps/wa-mirror.
It intentionally never returns raw Baileys payloads, quoted-message context,
group internals, local media paths, or signed WhatsApp media URLs.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.crm_access import can_view_all_clients, get_practices_user_filter
from backend.app.utils.crm_utils import is_crm_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wa", tags=["wa-mirror"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_BODY_CHARS = 4000


class WaMirrorMessageResponse(BaseModel):
    """CRM-safe allowlist for one wa-mirror message."""

    model_config = ConfigDict(extra="forbid")

    id: int
    client_id: int | None
    practice_id: int | None
    direction: str
    team_member_phone: str | None
    counterpart_phone: str | None
    body: str
    body_truncated: bool
    message_date: datetime
    media_type: str
    media_mime: str | None
    has_media: bool
    has_ocr: bool
    source: str = Field(default="wa_mirror")


class WaMirrorMessagesResponse(BaseModel):
    """Paginated wa-mirror timeline response."""

    model_config = ConfigDict(extra="forbid")

    items: list[WaMirrorMessageResponse]
    limit: int
    offset: int


def _add_param(params: list[Any], value: Any) -> str:
    """Append a query parameter and return its asyncpg placeholder."""
    params.append(value)
    return f"${len(params)}"


def _build_messages_query(
    *,
    client_id: int | None,
    practice_id: int | None,
    prospect_only: bool,
    limit: int,
    offset: int,
) -> tuple[str, list[Any]]:
    """Build a parameterized wa-mirror message query."""
    params: list[Any] = []
    where = [
        "source = 'wa_mirror'",
        "team_member_phone IS NOT NULL",
        "counterpart_phone IS NOT NULL",
    ]

    if prospect_only:
        where.append("client_id IS NULL")
        where.append("practice_id IS NULL")

    if client_id is not None:
        where.append(f"client_id = {_add_param(params, client_id)}")

    if practice_id is not None:
        where.append(f"practice_id = {_add_param(params, practice_id)}")

    limit_placeholder = _add_param(params, limit)
    offset_placeholder = _add_param(params, offset)

    return (
        f"""
        SELECT id, client_id, practice_id, direction, team_member_phone,
               counterpart_phone,
               COALESCE(NULLIF(body, ''), message_text, '') AS body,
               message_date,
               COALESCE(NULLIF(media_type, ''), 'text') AS media_type,
               media_mime,
               (ocr_result IS NOT NULL) AS has_ocr,
               source
          FROM whatsapp_message_context
         WHERE {" AND ".join(where)}
         ORDER BY message_date DESC, id DESC
         LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """,
        params,
    )


def _row_get(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read a value from dict-like asyncpg rows without exposing extras."""
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


def _message_response_from_row(row: Mapping[str, Any]) -> WaMirrorMessageResponse:
    """Create a response-model allowlist from a database row."""
    body = str(_row_get(row, "body", "") or "")
    body_truncated = len(body) > MAX_BODY_CHARS
    if body_truncated:
        body = body[:MAX_BODY_CHARS]

    media_type = str(_row_get(row, "media_type", "text") or "text")
    has_ocr = _row_get(row, "has_ocr")
    if has_ocr is None:
        has_ocr = _row_get(row, "ocr_result") is not None

    return WaMirrorMessageResponse(
        id=int(_row_get(row, "id")),
        client_id=_row_get(row, "client_id"),
        practice_id=_row_get(row, "practice_id"),
        direction=str(_row_get(row, "direction", "inbound") or "inbound"),
        team_member_phone=_row_get(row, "team_member_phone"),
        counterpart_phone=_row_get(row, "counterpart_phone"),
        body=body,
        body_truncated=body_truncated,
        message_date=_row_get(row, "message_date"),
        media_type=media_type,
        media_mime=_row_get(row, "media_mime"),
        has_media=media_type != "text",
        has_ocr=bool(has_ocr),
        source=str(_row_get(row, "source", "wa_mirror") or "wa_mirror"),
    )


async def _ensure_practice_visible(
    conn: asyncpg.Connection,
    practice_id: int,
    current_user: dict[str, Any],
) -> None:
    """Verify practice visibility using the same filter helper as CRM practices."""
    practices_filter = get_practices_user_filter(current_user)
    if practices_filter:
        is_visible = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM practices p
             LEFT JOIN clients c ON c.id = p.client_id
                 WHERE p.id = $1
                   AND (
                        p.assigned_to = $2
                     OR p.created_by = $2
                     OR c.assigned_to = $2
                   )
            )
            """,
            practice_id,
            practices_filter,
        )
    else:
        is_visible = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM practices WHERE id = $1)",
            practice_id,
        )

    if not is_visible:
        raise HTTPException(status_code=404, detail="Practice not found")


@router.get("/messages", response_model=WaMirrorMessagesResponse)
async def list_wa_mirror_messages(
    client_id: int | None = Query(None, gt=0, description="CRM client id"),
    practice_id: int | None = Query(None, gt=0, description="CRM practice id"),
    prospect_only: bool = Query(
        False,
        description="Return unmatched wa-mirror rows with client_id/practice_id NULL",
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> WaMirrorMessagesResponse:
    """List CRM-safe wa-mirror messages for client/practice timelines."""
    if not can_view_all_clients(current_user):
        raise HTTPException(status_code=403, detail="CRM access required")

    if prospect_only and (client_id is not None or practice_id is not None):
        raise HTTPException(
            status_code=400,
            detail="prospect_only cannot be combined with client_id or practice_id",
        )

    if not prospect_only and client_id is None and practice_id is None:
        raise HTTPException(
            status_code=400,
            detail="Provide client_id, practice_id, or prospect_only=true",
        )

    if prospect_only and not is_crm_admin(current_user):
        raise HTTPException(status_code=403, detail="CRM admin access required")

    try:
        async with db_pool.acquire() as conn:
            if practice_id is not None:
                await _ensure_practice_visible(conn, practice_id, current_user)

            query, params = _build_messages_query(
                client_id=client_id,
                practice_id=practice_id,
                prospect_only=prospect_only,
                limit=limit,
                offset=offset,
            )
            rows = await conn.fetch(query, *params)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("wa_mirror.messages.query_failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load wa-mirror messages") from exc

    return WaMirrorMessagesResponse(
        items=[_message_response_from_row(row) for row in rows],
        limit=limit,
        offset=offset,
    )
