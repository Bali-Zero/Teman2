"""Internal CRM Guardian Drive evidence endpoints.

The endpoints read only the staging tables introduced by migration 202. They
do not call Google Drive directly and do not mutate Drive, DB links, or review
state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user

router = APIRouter(prefix="/api/crm-guardian/drive", tags=["crm-guardian", "drive"])
admin_security = HTTPBearer(auto_error=False)


class DriveCountRow(BaseModel):
    key: str
    count: int


class DriveValidationSummary(BaseModel):
    total: int
    ok: int
    errors: int
    owner_domains: list[DriveCountRow] = Field(default_factory=list)
    mime_types: list[DriveCountRow] = Field(default_factory=list)
    statuses: list[DriveCountRow] = Field(default_factory=list)


class DriveBacklogItem(BaseModel):
    id: int | None = None
    drive_id: str
    backlog_type: str | None = None
    priority: str | None = None
    owner_email: str | None = None
    owner_domain: str | None = None
    source_mix: str | None = None
    recommended_action: str | None = None
    status: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class DriveMetadataItem(BaseModel):
    drive_id: str
    name: str | None = None
    mime_type: str | None = None
    owner_email: str | None = None
    owner_domain: str | None = None
    validation_status: str
    error_status: str | None = None
    error_message: str | None = None
    source_mix: str | None = None
    web_view_link: str | None = None


class ShortcutEdgeItem(BaseModel):
    shortcut_id: str
    target_id: str
    target_mime_type: str | None = None
    source_path: str | None = None
    source_cluster: str | None = None
    owner_email: str | None = None
    owner_domain: str | None = None
    resolution_status: str
    resolved_at: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


def _require_admin(current_user: dict[str, Any]) -> None:
    email = (current_user.get("email") or "").lower()
    if current_user.get("role") == "admin" or email in settings.admin_emails_set:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def _get_admin_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_security),
) -> dict[str, Any]:
    """Accept normal admin JWT/cookie auth or the internal admin API key."""
    admin_api_key = getattr(settings, "admin_api_key", None)
    debug_key = request.headers.get("X-Debug-Key")
    bearer_token = credentials.credentials if credentials else None
    if admin_api_key and (debug_key == admin_api_key or bearer_token == admin_api_key):
        return {
            "email": "admin-api-key@internal",
            "user_id": "admin-api-key",
            "role": "admin",
            "permissions": ["admin"],
        }

    current_user = get_current_user(request, credentials)
    _require_admin(current_user)
    return current_user


async def _get_pool(request: Request) -> Any:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database pool not available",
        )
    return pool


async def _require_table(conn: Any, table_name: str) -> None:
    exists = await conn.fetchval("SELECT to_regclass($1)", f"public.{table_name}")
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{table_name} is not migrated yet",
        )


def _count_rows(rows: list[Any], key_name: str) -> list[DriveCountRow]:
    return [
        DriveCountRow(key=str(row[key_name] or "unknown"), count=int(row["count"]))
        for row in rows
    ]


@router.get("/validation-summary", response_model=DriveValidationSummary)
async def get_drive_validation_summary(
    request: Request,
    current_user: dict[str, Any] = Depends(_get_admin_user),
) -> DriveValidationSummary:
    """Return aggregate state of the read-only Drive metadata snapshot."""
    _require_admin(current_user)
    pool = await _get_pool(request)
    async with pool.acquire() as conn:
        await _require_table(conn, "crm_guardian_drive_metadata_snapshot")
        total_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE validation_status = 'ok')::int AS ok,
                COUNT(*) FILTER (WHERE validation_status <> 'ok')::int AS errors
            FROM crm_guardian_drive_metadata_snapshot
            """,
        )
        owner_rows = await conn.fetch(
            """
            SELECT COALESCE(owner_domain, 'unknown') AS owner_domain, COUNT(*)::int AS count
            FROM crm_guardian_drive_metadata_snapshot
            WHERE validation_status = 'ok'
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
            """,
        )
        mime_rows = await conn.fetch(
            """
            SELECT COALESCE(mime_type, 'unknown') AS mime_type, COUNT(*)::int AS count
            FROM crm_guardian_drive_metadata_snapshot
            WHERE validation_status = 'ok'
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 20
            """,
        )
        status_rows = await conn.fetch(
            """
            SELECT validation_status, COUNT(*)::int AS count
            FROM crm_guardian_drive_metadata_snapshot
            GROUP BY validation_status
            ORDER BY count DESC
            """,
        )

    totals = dict(total_row or {})
    return DriveValidationSummary(
        total=int(totals.get("total") or 0),
        ok=int(totals.get("ok") or 0),
        errors=int(totals.get("errors") or 0),
        owner_domains=_count_rows(owner_rows, "owner_domain"),
        mime_types=_count_rows(mime_rows, "mime_type"),
        statuses=_count_rows(status_rows, "validation_status"),
    )


@router.get("/external-owner-risks", response_model=list[DriveBacklogItem])
async def list_external_owner_risks(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: dict[str, Any] = Depends(_get_admin_user),
) -> list[DriveBacklogItem]:
    """List open external-owner Drive migration risks."""
    _require_admin(current_user)
    pool = await _get_pool(request)
    async with pool.acquire() as conn:
        await _require_table(conn, "crm_guardian_migration_backlog")
        rows = await conn.fetch(
            """
            SELECT id, drive_id, backlog_type, priority, owner_email, owner_domain,
                   source_mix, recommended_action, status, evidence
            FROM crm_guardian_migration_backlog
            WHERE backlog_type = 'external_owner'
              AND status = 'open'
            ORDER BY priority, owner_domain, id
            LIMIT $1
            """,
            limit,
        )
    return [DriveBacklogItem(**dict(row)) for row in rows]


@router.get("/stale-link-candidates", response_model=list[DriveMetadataItem])
async def list_stale_link_candidates(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: dict[str, Any] = Depends(_get_admin_user),
) -> list[DriveMetadataItem]:
    """List Drive IDs that failed direct metadata validation."""
    _require_admin(current_user)
    pool = await _get_pool(request)
    async with pool.acquire() as conn:
        await _require_table(conn, "crm_guardian_drive_metadata_snapshot")
        rows = await conn.fetch(
            """
            SELECT drive_id, name, mime_type, owner_email, owner_domain,
                   validation_status, error_status, error_message, source_mix, web_view_link
            FROM crm_guardian_drive_metadata_snapshot
            WHERE validation_status <> 'ok'
            ORDER BY validation_status, drive_id
            LIMIT $1
            """,
            limit,
        )
    return [DriveMetadataItem(**dict(row)) for row in rows]


@router.get("/unlinked-items", response_model=list[DriveBacklogItem])
async def list_unlinked_items(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: dict[str, Any] = Depends(_get_admin_user),
) -> list[DriveBacklogItem]:
    """List visible CRM-relevant Drive items that need entity matching."""
    _require_admin(current_user)
    pool = await _get_pool(request)
    async with pool.acquire() as conn:
        await _require_table(conn, "crm_guardian_migration_backlog")
        rows = await conn.fetch(
            """
            SELECT id, drive_id, backlog_type, priority, owner_email, owner_domain,
                   source_mix, recommended_action, status, evidence
            FROM crm_guardian_migration_backlog
            WHERE backlog_type = 'unlinked_visible_crm_item'
              AND status = 'open'
            ORDER BY priority, owner_domain, id
            LIMIT $1
            """,
            limit,
        )
    return [DriveBacklogItem(**dict(row)) for row in rows]


@router.get("/shortcut-edges", response_model=list[ShortcutEdgeItem])
async def list_shortcut_edges(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: dict[str, Any] = Depends(_get_admin_user),
) -> list[ShortcutEdgeItem]:
    """List shortcut target edges for Canonical migration planning."""
    _require_admin(current_user)
    pool = await _get_pool(request)
    query = """
        SELECT shortcut_id, target_id, target_mime_type, source_path,
               source_cluster, owner_email, owner_domain, resolution_status,
               resolved_at::text, evidence
        FROM crm_guardian_shortcut_edges
    """
    params: list[Any] = []
    if status_filter:
        query += " WHERE resolution_status = $1"
        params.append(status_filter)
    query += f" ORDER BY resolution_status, shortcut_id LIMIT ${len(params) + 1}"
    params.append(limit)
    async with pool.acquire() as conn:
        await _require_table(conn, "crm_guardian_shortcut_edges")
        rows = await conn.fetch(query, *params)
    return [ShortcutEdgeItem(**dict(row)) for row in rows]
