"""WA Copilot action_queue API (S1.10 UI MVP).

This router exposes the `action_queue` table populated by S1.9
(`backend.services.wa_copilot.action_queue_rules`) to the wa-dashboard
`/actions` page.

Endpoints:
  GET  /api/wa/actions                  list with filters (owner/status/priority/search)
  GET  /api/wa/actions/owners           distinct owners (for filter dropdown)
  PATCH /api/wa/actions/{action_id}     transitions: Done/Snooze/Assign/Dismiss

CRM access: admin-only (Bali Zero ops team). Per-row team-member assignment
is enforced via `owner` column free-text + future RBAC layer.

PgBouncer-safe asyncpg via `get_database_pool()` (statement_cache_size=0
already configured on the pool in `backend.app.core.database`).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.crm_access import can_view_all_clients

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wa", tags=["wa-actions"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_SEARCH_CHARS = 200
MAX_NOTES_CHARS = 2000

ALLOWED_STATUSES = {"open", "snoozed", "done", "dismissed"}
ALLOWED_SNOOZE_DAYS = {1, 3, 7, 14, 30}


class ActionQueueRow(BaseModel):
    """CRM-safe projection of one action_queue row."""

    model_config = ConfigDict(extra="forbid")

    action_id: int
    client_id: int | None
    practice_id: int | None
    conversation_id: int | None
    action_type: str
    reason: str
    recommended_action: str
    suggested_message_draft: str | None = None
    due_at: datetime | None = None
    evidence: dict[str, Any] | list[Any] | None = None
    owner: str | None = None
    priority: int
    status: str
    snoozed_until: datetime | None = None
    dismiss_reason: str | None = None
    resolution_notes: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    # Convenience joins (optional, NULL-safe)
    client_full_name: str | None = None
    practice_kind: str | None = None


class ActionQueueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ActionQueueRow]
    limit: int
    offset: int
    total: int


class ActionQueueOwnersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owners: list[str]


class ActionPatchRequest(BaseModel):
    """Partial update — any subset of fields can be present.

    Status transitions allowed:
      open      -> snoozed | done | dismissed
      snoozed   -> open | done | dismissed
      done      -> (terminal, but allow re-open back to open if needed)
      dismissed -> (terminal, allow re-open)
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "snoozed", "done", "dismissed"] | None = None
    snooze_days: int | None = Field(
        default=None,
        ge=1,
        le=30,
        description="If set + status=snoozed, snoozed_until = NOW() + N days",
    )
    snoozed_until: datetime | None = None
    owner: str | None = Field(default=None, max_length=120)
    dismiss_reason: str | None = Field(default=None, max_length=500)
    resolution_notes: str | None = Field(default=None, max_length=MAX_NOTES_CHARS)


def _row_get(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


def _decode_evidence(raw: Any) -> dict[str, Any] | list[Any] | None:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        # asyncpg can return JSONB as str if no codec — best-effort parse
        import json as _json

        try:
            return _json.loads(raw)
        except Exception:
            return None
    return None


def _row_to_response(row: Mapping[str, Any]) -> ActionQueueRow:
    return ActionQueueRow(
        action_id=int(_row_get(row, "action_id")),
        client_id=_row_get(row, "client_id"),
        practice_id=_row_get(row, "practice_id"),
        conversation_id=_row_get(row, "conversation_id"),
        action_type=str(_row_get(row, "action_type", "") or ""),
        reason=str(_row_get(row, "reason", "") or ""),
        recommended_action=str(_row_get(row, "recommended_action", "") or ""),
        suggested_message_draft=_row_get(row, "suggested_message_draft"),
        due_at=_row_get(row, "due_at"),
        evidence=_decode_evidence(_row_get(row, "evidence")),
        owner=_row_get(row, "owner"),
        priority=int(_row_get(row, "priority", 5) or 5),
        status=str(_row_get(row, "status", "open") or "open"),
        snoozed_until=_row_get(row, "snoozed_until"),
        dismiss_reason=_row_get(row, "dismiss_reason"),
        resolution_notes=_row_get(row, "resolution_notes"),
        created_at=_row_get(row, "created_at"),
        resolved_at=_row_get(row, "resolved_at"),
        client_full_name=_row_get(row, "client_full_name"),
        practice_kind=_row_get(row, "practice_kind"),
    )


def _add_param(params: list[Any], value: Any) -> str:
    params.append(value)
    return f"${len(params)}"


@router.get("/actions", response_model=ActionQueueListResponse)
async def list_actions(
    owner: str | None = Query(None, max_length=120, description="Exact owner match (use 'unassigned' for null/unassigned)"),
    status: str | None = Query(None, description="open | snoozed | done | dismissed"),
    min_priority: int | None = Query(None, ge=1, le=10),
    action_type: str | None = Query(None, max_length=120),
    search: str | None = Query(None, max_length=MAX_SEARCH_CHARS, description="ILIKE match on reason/recommended_action"),
    sort: Literal["priority", "due_at", "created_at"] = Query("priority"),
    order: Literal["asc", "desc"] = Query("desc"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ActionQueueListResponse:
    """List action_queue rows with filters + pagination."""
    if not can_view_all_clients(current_user):
        raise HTTPException(status_code=403, detail="CRM access required")

    if status is not None and status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")

    params: list[Any] = []
    where: list[str] = []

    if status is not None:
        where.append(f"aq.status = {_add_param(params, status)}")
    if min_priority is not None:
        where.append(f"aq.priority >= {_add_param(params, min_priority)}")
    if action_type is not None:
        where.append(f"aq.action_type = {_add_param(params, action_type)}")
    if owner is not None:
        if owner == "unassigned":
            where.append("(aq.owner IS NULL OR aq.owner = 'unassigned')")
        else:
            where.append(f"aq.owner = {_add_param(params, owner)}")
    if search:
        like = f"%{search.strip()}%"
        placeholder = _add_param(params, like)
        where.append(f"(aq.reason ILIKE {placeholder} OR aq.recommended_action ILIKE {placeholder})")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # Sort whitelist already enforced by Literal
    order_sql = "DESC" if order == "desc" else "ASC"
    sort_col = {
        "priority": "aq.priority",
        "due_at": "aq.due_at",
        "created_at": "aq.created_at",
    }[sort]

    limit_p = _add_param(params, limit)
    offset_p = _add_param(params, offset)

    list_query = f"""
        SELECT aq.action_id, aq.client_id, aq.practice_id, aq.conversation_id,
               aq.action_type, aq.reason, aq.recommended_action,
               aq.suggested_message_draft, aq.due_at, aq.evidence, aq.owner,
               aq.priority, aq.status, aq.snoozed_until, aq.dismiss_reason,
               aq.resolution_notes, aq.created_at, aq.resolved_at,
               c.full_name AS client_full_name,
               p.kind       AS practice_kind
          FROM action_queue aq
     LEFT JOIN clients   c ON c.id = aq.client_id
     LEFT JOIN practices p ON p.id = aq.practice_id
          {where_sql}
      ORDER BY {sort_col} {order_sql} NULLS LAST, aq.action_id DESC
         LIMIT {limit_p} OFFSET {offset_p}
    """

    # Count query uses same WHERE but no joins (faster + accurate enough)
    count_query = f"SELECT COUNT(*) FROM action_queue aq {where_sql}"
    # Strip the LIMIT/OFFSET params from count (last 2)
    count_params = params[:-2]

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(list_query, *params)
            total = await conn.fetchval(count_query, *count_params) or 0
    except Exception as exc:
        logger.error("wa_actions.list.query_failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load action queue") from exc

    return ActionQueueListResponse(
        items=[_row_to_response(r) for r in rows],
        limit=limit,
        offset=offset,
        total=int(total),
    )


@router.get("/actions/owners", response_model=ActionQueueOwnersResponse)
async def list_owners(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ActionQueueOwnersResponse:
    """List distinct owners present in action_queue (for filter UI)."""
    if not can_view_all_clients(current_user):
        raise HTTPException(status_code=403, detail="CRM access required")

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT COALESCE(owner, 'unassigned') AS owner
                  FROM action_queue
                 ORDER BY 1
                """
            )
    except Exception as exc:
        logger.error("wa_actions.owners.query_failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load owners") from exc

    return ActionQueueOwnersResponse(owners=[str(r["owner"]) for r in rows])


@router.patch("/actions/{action_id}", response_model=ActionQueueRow)
async def patch_action(
    action_id: int = Path(..., gt=0),
    payload: ActionPatchRequest = ...,  # type: ignore[assignment]
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ActionQueueRow:
    """Apply a partial update (Done / Snooze / Assign / Dismiss)."""
    if not can_view_all_clients(current_user):
        raise HTTPException(status_code=403, detail="CRM access required")

    sets: list[str] = []
    params: list[Any] = []
    now = datetime.now(timezone.utc)

    new_status = payload.status
    if new_status is not None:
        if new_status not in ALLOWED_STATUSES:
            raise HTTPException(
                status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}"
            )
        sets.append(f"status = {_add_param(params, new_status)}")
        if new_status in ("done", "dismissed"):
            sets.append(f"resolved_at = {_add_param(params, now)}")
        elif new_status == "open":
            sets.append("resolved_at = NULL")
            sets.append("snoozed_until = NULL")

    if payload.snooze_days is not None:
        if payload.snooze_days not in ALLOWED_SNOOZE_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"snooze_days must be one of {sorted(ALLOWED_SNOOZE_DAYS)}",
            )
        target = now + timedelta(days=payload.snooze_days)
        sets.append(f"snoozed_until = {_add_param(params, target)}")
        # If snoozing, force status=snoozed if not explicitly set
        if new_status is None:
            sets.append(f"status = {_add_param(params, 'snoozed')}")

    if payload.snoozed_until is not None and payload.snooze_days is None:
        sets.append(f"snoozed_until = {_add_param(params, payload.snoozed_until)}")

    if payload.owner is not None:
        normalized_owner = payload.owner.strip() or None
        sets.append(f"owner = {_add_param(params, normalized_owner)}")

    if payload.dismiss_reason is not None:
        sets.append(f"dismiss_reason = {_add_param(params, payload.dismiss_reason.strip() or None)}")

    if payload.resolution_notes is not None:
        sets.append(
            f"resolution_notes = {_add_param(params, payload.resolution_notes.strip() or None)}"
        )

    if not sets:
        raise HTTPException(status_code=400, detail="No mutable fields provided")

    # Dismiss requires a reason (UX guard)
    if new_status == "dismissed" and payload.dismiss_reason is None:
        raise HTTPException(
            status_code=400, detail="dismiss_reason is required when status=dismissed"
        )

    action_id_p = _add_param(params, action_id)
    update_sql = f"""
        UPDATE action_queue
           SET {", ".join(sets)}
         WHERE action_id = {action_id_p}
     RETURNING action_id, client_id, practice_id, conversation_id, action_type,
               reason, recommended_action, suggested_message_draft, due_at,
               evidence, owner, priority, status, snoozed_until, dismiss_reason,
               resolution_notes, created_at, resolved_at
    """

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(update_sql, *params)
            if row is None:
                raise HTTPException(status_code=404, detail="action_id not found")
            # Augment with joins for response parity
            extra = await conn.fetchrow(
                """
                SELECT c.full_name AS client_full_name,
                       p.kind       AS practice_kind
                  FROM action_queue aq
             LEFT JOIN clients   c ON c.id = aq.client_id
             LEFT JOIN practices p ON p.id = aq.practice_id
                 WHERE aq.action_id = $1
                """,
                action_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("wa_actions.patch.query_failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update action") from exc

    merged: dict[str, Any] = dict(row)
    if extra is not None:
        merged["client_full_name"] = extra["client_full_name"]
        merged["practice_kind"] = extra["practice_kind"]

    logger.info(
        "wa_actions.patch.success action_id=%s status=%s owner=%s user=%s",
        action_id,
        merged.get("status"),
        merged.get("owner"),
        current_user.get("email"),
    )

    return _row_to_response(merged)
