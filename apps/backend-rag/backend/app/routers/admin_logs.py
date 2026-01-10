"""
Admin Logs Router
Endpoints for querying team activity logs, interactions, and audit trail

Requires ADMIN_API_KEY for access
"""

from datetime import datetime
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.dependencies import get_database_pool
from backend.app.routers.debug import verify_debug_access
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/logs", tags=["admin-logs"])


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
    _: bool = Depends(verify_debug_access),
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
        logger.error(f"❌ Failed to fetch activity logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interactions")
async def get_team_interactions(
    user_email: str | None = Query(None, description="Filter by team member"),
    client_email: str | None = Query(None, description="Filter by client"),
    interaction_type: str | None = Query(None, description="Filter by type"),
    direction: Literal["inbound", "outbound"] | None = Query(
        None, description="Filter by direction"
    ),
    date_from: datetime | None = Query(None, description="Start date (UTC)"),
    date_to: datetime | None = Query(None, description="End date (UTC)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _: bool = Depends(verify_debug_access),
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
        logger.error(f"❌ Failed to fetch team interactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
    _: bool = Depends(verify_debug_access),
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
        logger.error(f"❌ Failed to fetch API audit trail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/today")
async def get_today_summary(
    _: bool = Depends(verify_debug_access),
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
            "date": datetime.now().date().isoformat(),
            "team_summary": summary,
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch today's summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/interactions")
async def get_interactions_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    _: bool = Depends(verify_debug_access),
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
        logger.error(f"❌ Failed to fetch interactions summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
