"""
Admin Logs Router
Endpoints for querying team activity logs, interactions, and audit trail

Access: an admin (ADMIN_API_KEY or an admin-role JWT, via
``verify_debug_access``) or a developer named in ``DEVELOPER_EMAILS``.
See ``verify_log_read_access`` below for why the developer grant lives here
and not on ``verify_debug_access`` itself.
"""

from datetime import datetime, timezone
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.routers.debug import verify_debug_access
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/logs", tags=["admin-logs"])

_security = HTTPBearer(auto_error=False)


_UNPROVISIONED_DETAIL = (
    "This team-activity surface is not provisioned in this environment: the "
    "relation it reads does not exist. Migration 041b, which creates "
    "activity_logs, team_interactions and the two summary views, lives in "
    "backend/migrations/ — classified 'Legacy (manual), None (manual apply)' in "
    "MIGRATIONS.md — and has no counterpart in db/migrations_v2/, the directory "
    "the Fly release_command actually applies. Nothing has ever created these "
    "relations, and nothing writes to them. This is a known gap, not a "
    "transient fault: retrying will not help."
)


def _query_failure(operation: str, exc: BaseException) -> HTTPException:
    """Map a query failure to a response that does not quote the database.

    Every endpoint below used to end in ``raise HTTPException(500,
    detail=str(e))``, which handed the CALLER the raw Postgres message — on the
    one surface whose entire purpose is to be narrower than admin
    (``DEVELOPER_EMAILS``, see ``verify_log_read_access``). A developer reading
    logs has no need of the server's exception text, and four of these five
    endpoints read relations that do not exist, so that leak was not
    hypothetical: it was the normal response. The full exception, with
    traceback, still goes to the server log, which is where it belongs.

    Three outcomes, because they mean three different things to the caller:

    * an ``HTTPException`` raised inside the ``try`` is passed through
      unchanged. The bare ``except Exception`` used to swallow it and relabel
      it 500, so a deliberate 4xx became a server error;
    * a missing relation is **501**, not 500 and not 503. It is not a fault and
      not transient — the functionality is not provisioned — and 503 would
      invite a retry that cannot succeed;
    * anything else is a 500 naming the OPERATION, never the exception.
    """
    if isinstance(exc, HTTPException):
        return exc
    # `exc_info=exc` and not `exc_info=True`: this helper is CALLED from an
    # except block but is not one itself, so there is no ambient exception to
    # pick up (ruff LOG014 catches exactly that). Naming the exception gives
    # the same traceback and works wherever the helper is called from.
    logger.error("❌ %s failed: %s", operation, exc, exc_info=exc)
    if isinstance(exc, asyncpg.exceptions.UndefinedTableError):
        return HTTPException(status_code=501, detail=_UNPROVISIONED_DETAIL)
    return HTTPException(status_code=500, detail=f"{operation} failed")


def verify_log_read_access(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    request: Request = None,
) -> bool:
    """Admin, or a developer named in ``DEVELOPER_EMAILS``.

    WHY THIS IS A SEPARATE GATE, and not two lines added to
    ``verify_debug_access`` (adversarial review, codex-gpt-5.6-sol, 2026-09-10,
    verified on disk before being accepted):

    ``verify_debug_access`` does not guard "the logs". It guards every route in
    ``debug.py``, and that router holds ``POST /api/debug/postgres/query``,
    which executes a caller-supplied SQL statement against the production
    database — read-only, but read-only over the whole client book. It also
    holds ``DELETE /api/debug/traces`` and ``POST /api/debug/profile``, which
    are not reads at all. Widening that dependency to give a developer his
    logs would have handed him arbitrary SELECT on production: strictly MORE
    than making him a CRM admin, which is the outcome the separate allowlist
    was introduced to avoid.

    So the developer grant is attached HERE, to the read-only log endpoints
    that actually need it, and ``verify_debug_access`` keeps its original
    admin-only perimeter unchanged.

    The token check is deliberately STRICTER than the one in
    ``verify_debug_access``: ``type`` must be exactly ``"access"``, not
    "missing or access". A token family that omits the claim cannot be
    laundered into log access through the allowlist.
    """
    # Admins keep the exact behaviour they had: the whole check, including the
    # ADMIN_API_KEY paths, is delegated untouched.
    #
    # Only its 401 is swallowed, and only so the developer branch below gets a
    # turn. Its 403 is RE-RAISED: that status means something categorically
    # different — "debug endpoints are not available in production without
    # ADMIN_API_KEY", an environment-level refusal, not "you are not an
    # admin". Swallowing it would let a listed developer walk through a
    # precondition that is meant to close these routes for everyone
    # (adversarial review, kimi-code/k3, round 2). ADMIN_API_KEY is in fact
    # configured on production today, so this branch is not reachable there —
    # which is exactly why it had to be decided deliberately rather than left
    # to whichever exception happened to be caught.
    try:
        return verify_debug_access(credentials=credentials, request=request)
    except HTTPException as admin_exc:
        if admin_exc.status_code != 401:
            raise

    allowlist = settings.developer_emails_set
    if not allowlist or credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Log access requires an admin credential or a listed developer JWT",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from jose import jwt

        from backend.services.security.token_revocation import (
            RevocationStoreUnavailable,
            is_session_revoked_sync,
        )

        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True, "require_exp": True},
        )
        if payload.get("type") == "access":
            # Equality on the normalised address, never a substring or a domain
            # prefix — cicatrix-superscar #3. An absent `email` claim yields ""
            # which the parser can never have put in the set; the truthiness
            # test states that rather than relying on it.
            email = (payload.get("email") or "").lower().strip()
            if email and email in allowlist:
                # A signed, unexpired token is not the same as a live session.
                # Both review seats flagged this independently: without the
                # revocation check a developer who logged out, or whose access
                # was revoked, keeps reading production logs until the token
                # expires on its own. This is the SAME call `get_current_user`
                # makes, so revocation means one thing across the app.
                #
                # RevocationStoreUnavailable is deliberately NOT swallowed by
                # the `except Exception` below: when the store cannot answer,
                # this fails CLOSED with 503 exactly like get_current_user,
                # rather than silently falling through to the 401 — a store
                # outage must not be indistinguishable from a bad token.
                try:
                    revoked = is_session_revoked_sync(payload)
                except RevocationStoreUnavailable as store_exc:
                    logger.error(
                        "log access unavailable: session revocation cannot be checked"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail="Authentication service temporarily unavailable",
                    ) from store_exc
                if revoked:
                    logger.warning("Rejected revoked JWT session on log access")
                else:
                    return True
    except HTTPException:
        raise
    except Exception:
        logger.debug("log access: bearer token is not a valid developer JWT")

    raise HTTPException(
        status_code=401,
        detail="Log access requires an admin credential or a listed developer JWT",
        headers={"WWW-Authenticate": "Bearer"},
    )


# =============================================================================
# Response Models
# =============================================================================


class ActivityLogItem(BaseModel):
    """Single activity log entry"""

    id: int
    user_email: str
    action_type: str
    resource_type: str | None
    resource_id: str | None
    description: str | None
    details: dict
    ip_address: str | None
    created_at: datetime


class InteractionLogItem(BaseModel):
    """Single team interaction log entry"""

    id: int
    user_email: str
    interaction_type: str
    direction: str
    client_email: str | None
    client_name: str | None
    subject: str | None
    message_preview: str | None
    created_at: datetime
    response_time_seconds: int | None


class APIAuditItem(BaseModel):
    """Single API audit trail entry"""

    id: int
    user_email: str | None
    method: str
    endpoint: str
    response_status: int
    response_time_ms: int
    error_message: str | None
    created_at: datetime


class TeamActivitySummary(BaseModel):
    """Team activity summary"""

    user_email: str
    total_actions: int
    unique_action_types: int
    first_action: datetime
    last_action: datetime


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/activity")
async def get_activity_logs(
    user_email: str | None = Query(None, description="Filter by user email"),
    action_type: str | None = Query(None, description="Filter by action type"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    date_from: datetime | None = Query(None, description="Start date (UTC)"),
    date_to: datetime | None = Query(None, description="End date (UTC)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _: bool = Depends(verify_log_read_access),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get activity logs with filters

    Returns:
        Activity logs matching filters
    """
    try:
        # Build query
        conditions = []
        params = []
        param_count = 0

        if user_email:
            param_count += 1
            conditions.append(f"user_email = ${param_count}")
            params.append(user_email)

        if action_type:
            param_count += 1
            conditions.append(f"action_type = ${param_count}")
            params.append(action_type)

        if resource_type:
            param_count += 1
            conditions.append(f"resource_type = ${param_count}")
            params.append(resource_type)

        if date_from:
            param_count += 1
            conditions.append(f"created_at >= ${param_count}")
            params.append(date_from)

        if date_to:
            param_count += 1
            conditions.append(f"created_at <= ${param_count}")
            params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count total
        count_query = f"SELECT COUNT(*) FROM activity_logs {where_clause}"

        # Get logs
        param_count += 1
        limit_param = param_count
        param_count += 1
        offset_param = param_count

        logs_query = f"""
            SELECT id, user_email, action_type, resource_type, resource_id,
                   description, details, ip_address, created_at
            FROM activity_logs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
        """

        async with db_pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)
            rows = await conn.fetch(logs_query, *params, limit, offset)

        logs = [dict(row) for row in rows]

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "logs": logs,
        }

    except Exception as e:
        raise _query_failure("fetch activity logs", e) from e


@router.get("/interactions")
async def get_team_interactions(
    user_email: str | None = Query(None, description="Filter by team member"),
    client_email: str | None = Query(None, description="Filter by client"),
    interaction_type: str | None = Query(None, description="Filter by type"),
    direction: Literal["inbound", "outbound"] | None = Query(
        None,
        description="Filter by direction",
    ),
    date_from: datetime | None = Query(None, description="Start date (UTC)"),
    date_to: datetime | None = Query(None, description="End date (UTC)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _: bool = Depends(verify_log_read_access),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get team interactions (chat, WhatsApp, email, calls)

    Returns:
        Team interactions matching filters
    """
    try:
        conditions = []
        params = []
        param_count = 0

        if user_email:
            param_count += 1
            conditions.append(f"user_email = ${param_count}")
            params.append(user_email)

        if client_email:
            param_count += 1
            conditions.append(f"client_email = ${param_count}")
            params.append(client_email)

        if interaction_type:
            param_count += 1
            conditions.append(f"interaction_type = ${param_count}")
            params.append(interaction_type)

        if direction:
            param_count += 1
            conditions.append(f"direction = ${param_count}")
            params.append(direction)

        if date_from:
            param_count += 1
            conditions.append(f"created_at >= ${param_count}")
            params.append(date_from)

        if date_to:
            param_count += 1
            conditions.append(f"created_at <= ${param_count}")
            params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM team_interactions {where_clause}"

        param_count += 1
        limit_param = param_count
        param_count += 1
        offset_param = param_count

        logs_query = f"""
            SELECT id, user_email, interaction_type, direction, client_email,
                   client_name, subject, message_preview, created_at,
                   response_time_seconds, metadata
            FROM team_interactions
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
        """

        async with db_pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)
            rows = await conn.fetch(logs_query, *params, limit, offset)

        logs = [dict(row) for row in rows]

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "interactions": logs,
        }

    except Exception as e:
        raise _query_failure("fetch team interactions", e) from e


@router.get("/api-audit")
async def get_api_audit_trail(
    user_email: str | None = Query(None, description="Filter by user"),
    endpoint: str | None = Query(None, description="Filter by endpoint (contains)"),
    method: str | None = Query(None, description="Filter by HTTP method"),
    min_status: int = Query(0, ge=0, description="Min status code (e.g., 400 for errors)"),
    date_from: datetime | None = Query(None, description="Start date (UTC)"),
    date_to: datetime | None = Query(None, description="End date (UTC)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _: bool = Depends(verify_log_read_access),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get API audit trail

    Returns:
        API calls matching filters
    """
    try:
        conditions = []
        params = []
        param_count = 0

        if user_email:
            param_count += 1
            conditions.append(f"user_email = ${param_count}")
            params.append(user_email)

        if endpoint:
            param_count += 1
            conditions.append(f"endpoint LIKE ${param_count}")
            params.append(f"%{endpoint}%")

        if method:
            param_count += 1
            conditions.append(f"method = ${param_count}")
            params.append(method.upper())

        if min_status > 0:
            param_count += 1
            conditions.append(f"response_status >= ${param_count}")
            params.append(min_status)

        if date_from:
            param_count += 1
            conditions.append(f"created_at >= ${param_count}")
            params.append(date_from)

        if date_to:
            param_count += 1
            conditions.append(f"created_at <= ${param_count}")
            params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM api_audit_trail {where_clause}"

        param_count += 1
        limit_param = param_count
        param_count += 1
        offset_param = param_count

        logs_query = f"""
            SELECT id, user_email, method, endpoint, response_status,
                   response_time_ms, error_message, created_at, ip_address
            FROM api_audit_trail
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
        """

        async with db_pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)
            rows = await conn.fetch(logs_query, *params, limit, offset)

        logs = [dict(row) for row in rows]

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "api_calls": logs,
        }

    except Exception as e:
        raise _query_failure("fetch API audit trail", e) from e


@router.get("/summary/today")
async def get_today_summary(
    _: bool = Depends(verify_log_read_access),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get today's team activity summary

    Returns:
        Summary of today's activity by team member
    """
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM v_today_team_activity
                ORDER BY total_actions DESC
            """)

        summary = [dict(row) for row in rows]

        return {
            "success": True,
            "date": datetime.now(tz=timezone.utc).replace(tzinfo=None).date().isoformat(),
            "team_summary": summary,
        }

    except Exception as e:
        raise _query_failure("fetch today's activity summary", e) from e


@router.get("/summary/interactions")
async def get_interactions_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    _: bool = Depends(verify_log_read_access),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get team interactions summary

    Returns:
        Summary of team interactions over specified period
    """
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM v_team_interactions_summary
                WHERE date >= CURRENT_DATE - $1 * INTERVAL '1 day'
                ORDER BY date DESC, count DESC
            """,
                days,
            )

        summary = [dict(row) for row in rows]

        return {
            "success": True,
            "period_days": days,
            "interactions_summary": summary,
        }

    except Exception as e:
        raise _query_failure("fetch interactions summary", e) from e
