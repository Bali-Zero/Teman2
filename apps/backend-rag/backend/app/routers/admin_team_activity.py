"""
Admin Team Activity Router
Complete team activity dashboard with messages, timesheet, and CRM actions
"""

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/team-activity", tags=["admin-team-activity"])


# =============================================================================
# Auth
# =============================================================================


async def verify_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Verify user is admin"""
    if not is_crm_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# =============================================================================
# Response Models
# =============================================================================


class MessageItem(BaseModel):
    """Single message from v_messages view"""

    conversation_id: int
    user_id: str | None
    role: str | None
    content: str | None
    message_timestamp: datetime | None
    content_length: int | None


class TeamMemberStats(BaseModel):
    """Team member activity statistics"""

    email: str
    name: str | None
    role: str | None
    department: str | None
    conversations: int
    messages: int
    days_worked: int
    crm_actions: int
    last_activity: datetime | None


class OverviewStats(BaseModel):
    """Overview statistics"""

    total_conversations: int
    total_messages: int
    total_team_members: int
    active_today: int
    messages_today: int


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/overview")
async def get_overview(
    start_date: str | None = Query(
        None, description="Start date (YYYY-MM-DD), defaults to 30 days ago"
    ),
    _admin: dict = Depends(verify_admin),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get overview statistics for team activity"""
    try:
        async with db_pool.acquire() as conn:
            # Total conversations and messages (using view for robust counting)
            total_convs = await conn.fetchval("SELECT COUNT(*) FROM conversations")
            total_msgs = await conn.fetchval("SELECT COUNT(*) FROM v_messages")

            # Knowledge Base Stats (Intelligence Center)
            kg_nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
            kg_edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")

            # Team members count
            total_team = await conn.fetchval(
                "SELECT COUNT(*) FROM team_members WHERE role NOT IN ('client')"
            )

            # Active today (clocked in)
            active_today = await conn.fetchval("""
                SELECT COUNT(DISTINCT email) FROM team_timesheet
                WHERE DATE(timestamp) = CURRENT_DATE AND action_type = 'clock_in'
            """)

            # Messages today
            msgs_today = await conn.fetchval("""
                SELECT COUNT(*) FROM v_messages
                WHERE DATE(conversation_started) = CURRENT_DATE
            """)

            # Top users by messages - use start_date if provided, else 30 days
            if start_date:
                # Parse string to date object for asyncpg
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                top_users = await conn.fetch(
                    """
                    SELECT user_id, COUNT(*) as msg_count
                    FROM v_messages
                    WHERE role = 'user'
                      AND DATE(conversation_started) >= $1
                    GROUP BY user_id
                    ORDER BY msg_count DESC
                    LIMIT 10
                """,
                    start_date_obj,
                )
            else:
                top_users = await conn.fetch("""
                    SELECT user_id, COUNT(*) as msg_count
                    FROM v_messages
                    WHERE role = 'user'
                      AND conversation_started > NOW() - INTERVAL '30 days'
                    GROUP BY user_id
                    ORDER BY msg_count DESC
                    LIMIT 10
                """)

        return {
            "success": True,
            "stats": {
                "total_conversations": total_convs,
                "total_messages": total_msgs,
                "total_team_members": total_team,
                "active_today": active_today or 0,
                "messages_today": msgs_today or 0,
                "total_kg_nodes": kg_nodes,
                "total_kg_edges": kg_edges,
            },
            "top_users": [dict(u) for u in top_users],
        }
    except Exception as e:
        logger.error(f"Failed to get overview: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages")
async def get_messages(
    user_id: str | None = Query(None, description="Filter by user email"),
    role: str | None = Query(None, description="Filter by role (user/assistant)"),
    search: str | None = Query(None, description="Search in message content"),
    date_from: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _admin: dict = Depends(verify_admin),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get messages from v_messages view with filters"""
    try:
        conditions = []
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        if role:
            param_count += 1
            conditions.append(f"role = ${param_count}")
            params.append(role)

        if search:
            param_count += 1
            conditions.append(f"content ILIKE ${param_count}")
            params.append(f"%{search}%")

        if date_from:
            param_count += 1
            conditions.append(f"DATE(conversation_started) >= ${param_count}::date")
            params.append(date_from)

        if date_to:
            param_count += 1
            conditions.append(f"DATE(conversation_started) <= ${param_count}::date")
            params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with db_pool.acquire() as conn:
            # Count total
            count_query = f"SELECT COUNT(*) FROM v_messages {where_clause}"
            total = await conn.fetchval(count_query, *params)

            # Get messages
            param_count += 1
            limit_param = param_count
            param_count += 1
            offset_param = param_count

            query = f"""
                SELECT conversation_id, user_id, role,
                       LEFT(content, 500) as content,
                       message_timestamp, content_length,
                       conversation_started
                FROM v_messages
                {where_clause}
                ORDER BY conversation_started DESC, message_index
                LIMIT ${limit_param} OFFSET ${offset_param}
            """
            rows = await conn.fetch(query, *params, limit, offset)

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "messages": [dict(r) for r in rows],
        }
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/team-stats")
async def get_team_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    start_date: str | None = Query(
        None, description="Start date (YYYY-MM-DD), overrides days if provided"
    ),
    _admin: dict = Depends(verify_admin),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get detailed stats for each team member"""
    try:
        async with db_pool.acquire() as conn:
            # Use start_date if provided, else use days parameter
            if start_date:
                # Parse string to date object for asyncpg
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                query = """
                    WITH msg_stats AS (
                        SELECT user_id,
                               COUNT(DISTINCT conversation_id) as conversations,
                               COUNT(*) FILTER (WHERE role = 'user') as messages,
                               MAX(conversation_started) as last_msg
                        FROM v_messages
                        WHERE DATE(conversation_started) >= $1
                        GROUP BY user_id
                    ),
                    timesheet_stats AS (
                        SELECT email,
                               COUNT(DISTINCT DATE(timestamp)) FILTER (WHERE action_type = 'clock_in') as days_worked
                        FROM team_timesheet
                        WHERE DATE(timestamp) >= $1
                        GROUP BY email
                    ),
                    crm_stats AS (
                        SELECT performed_by as email, COUNT(*) as crm_actions
                        FROM activity_log
                        WHERE DATE(performed_at) >= $1
                        GROUP BY performed_by
                    ),
                    email_stats AS (
                        SELECT user_email as email,
                               COUNT(*) FILTER (WHERE operation = 'send') as emails_sent,
                               COUNT(*) FILTER (WHERE operation = 'receive') as emails_received
                        FROM email_activity_log
                        WHERE DATE(created_at) >= $1
                        GROUP BY user_email
                    ),
                    kb_stats AS (
                        SELECT user_email as email,
                               COUNT(*) FILTER (WHERE action_type = 'view') as kb_views,
                               COUNT(*) FILTER (WHERE action_type = 'download') as kb_downloads
                        FROM knowledge_activity_log
                        WHERE DATE(created_at) >= $1
                        GROUP BY user_email
                    )
                    SELECT
                        tm.email,
                        tm.name,
                        tm.role,
                        tm.department,
                        COALESCE(ms.conversations, 0) as conversations,
                        COALESCE(ms.messages, 0) as messages,
                        COALESCE(ts.days_worked, 0) as days_worked,
                        COALESCE(cs.crm_actions, 0) as crm_actions,
                        COALESCE(es.emails_sent, 0) as emails_sent,
                        COALESCE(es.emails_received, 0) as emails_received,
                        COALESCE(kb.kb_views, 0) as kb_views,
                        COALESCE(kb.kb_downloads, 0) as kb_downloads,
                        ms.last_msg as last_activity
                    FROM team_members tm
                    LEFT JOIN msg_stats ms ON tm.email = ms.user_id
                    LEFT JOIN timesheet_stats ts ON tm.email = ts.email
                    LEFT JOIN crm_stats cs ON tm.email = cs.email
                    LEFT JOIN email_stats es ON tm.email = es.email
                    LEFT JOIN kb_stats kb ON tm.email = kb.email
                    WHERE tm.role NOT IN ('client')
                      AND tm.email NOT LIKE '%test%'
                      AND tm.email NOT LIKE '%demo%'
                      AND tm.email NOT LIKE '%example%'
                    ORDER BY COALESCE(ms.messages, 0) DESC
                """
                rows = await conn.fetch(query, start_date_obj)
                period_info = f"from {start_date}"
            else:
                query = """
                    WITH msg_stats AS (
                        SELECT user_id,
                               COUNT(DISTINCT conversation_id) as conversations,
                               COUNT(*) FILTER (WHERE role = 'user') as messages,
                               MAX(conversation_started) as last_msg
                        FROM v_messages
                        WHERE conversation_started > NOW() - $1 * INTERVAL '1 day'
                        GROUP BY user_id
                    ),
                    timesheet_stats AS (
                        SELECT email,
                               COUNT(DISTINCT DATE(timestamp)) FILTER (WHERE action_type = 'clock_in') as days_worked
                        FROM team_timesheet
                        WHERE timestamp > NOW() - $1 * INTERVAL '1 day'
                        GROUP BY email
                    ),
                    crm_stats AS (
                        SELECT performed_by as email, COUNT(*) as crm_actions
                        FROM activity_log
                        WHERE performed_at > NOW() - $1 * INTERVAL '1 day'
                        GROUP BY performed_by
                    ),
                    email_stats AS (
                        SELECT user_email as email,
                               COUNT(*) FILTER (WHERE operation = 'send') as emails_sent,
                               COUNT(*) FILTER (WHERE operation = 'receive') as emails_received
                        FROM email_activity_log
                        WHERE created_at > NOW() - $1 * INTERVAL '1 day'
                        GROUP BY user_email
                    ),
                    kb_stats AS (
                        SELECT user_email as email,
                               COUNT(*) FILTER (WHERE action_type = 'view') as kb_views,
                               COUNT(*) FILTER (WHERE action_type = 'download') as kb_downloads
                        FROM knowledge_activity_log
                        WHERE created_at > NOW() - $1 * INTERVAL '1 day'
                        GROUP BY user_email
                    )
                    SELECT
                        tm.email,
                        tm.name,
                        tm.role,
                        tm.department,
                        COALESCE(ms.conversations, 0) as conversations,
                        COALESCE(ms.messages, 0) as messages,
                        COALESCE(ts.days_worked, 0) as days_worked,
                        COALESCE(cs.crm_actions, 0) as crm_actions,
                        COALESCE(es.emails_sent, 0) as emails_sent,
                        COALESCE(es.emails_received, 0) as emails_received,
                        COALESCE(kb.kb_views, 0) as kb_views,
                        COALESCE(kb.kb_downloads, 0) as kb_downloads,
                        ms.last_msg as last_activity
                    FROM team_members tm
                    LEFT JOIN msg_stats ms ON tm.email = ms.user_id
                    LEFT JOIN timesheet_stats ts ON tm.email = ts.email
                    LEFT JOIN crm_stats cs ON tm.email = cs.email
                    LEFT JOIN email_stats es ON tm.email = es.email
                    LEFT JOIN kb_stats kb ON tm.email = kb.email
                    WHERE tm.role NOT IN ('client')
                      AND tm.email NOT LIKE '%test%'
                      AND tm.email NOT LIKE '%demo%'
                      AND tm.email NOT LIKE '%example%'
                    ORDER BY COALESCE(ms.messages, 0) DESC
                """
                rows = await conn.fetch(query, days)
                period_info = f"last {days} days"

        return {
            "success": True,
            "period": period_info,
            "start_date": start_date,
            "team_stats": [dict(r) for r in rows],
        }
    except Exception as e:
        logger.error(f"Failed to get team stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/timesheet")
async def get_timesheet(
    email: str | None = Query(None, description="Filter by email"),
    date_from: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(verify_admin),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get timesheet records"""
    try:
        conditions = []
        params = []
        param_count = 0

        if email:
            param_count += 1
            conditions.append(f"email = ${param_count}")
            params.append(email)

        if date_from:
            param_count += 1
            conditions.append(f"DATE(timestamp) >= ${param_count}::date")
            params.append(date_from)

        if date_to:
            param_count += 1
            conditions.append(f"DATE(timestamp) <= ${param_count}::date")
            params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with db_pool.acquire() as conn:
            count_query = f"SELECT COUNT(*) FROM team_timesheet {where_clause}"
            total = await conn.fetchval(count_query, *params)

            param_count += 1
            limit_param = param_count
            param_count += 1
            offset_param = param_count

            query = f"""
                SELECT id, email, action_type, timestamp, notes
                FROM team_timesheet
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${limit_param} OFFSET ${offset_param}
            """
            rows = await conn.fetch(query, *params, limit, offset)

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "records": [dict(r) for r in rows],
        }
    except Exception as e:
        logger.error(f"Failed to get timesheet: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/crm-actions")
async def get_crm_actions(
    email: str | None = Query(None, description="Filter by email"),
    action: str | None = Query(None, description="Filter by action type"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(verify_admin),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get CRM activity log"""
    try:
        conditions = []
        params = []
        param_count = 0

        if email:
            param_count += 1
            conditions.append(f"performed_by = ${param_count}")
            params.append(email)

        if action:
            param_count += 1
            conditions.append(f"action = ${param_count}")
            params.append(action)

        if entity_type:
            param_count += 1
            conditions.append(f"entity_type = ${param_count}")
            params.append(entity_type)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with db_pool.acquire() as conn:
            count_query = f"SELECT COUNT(*) FROM activity_log {where_clause}"
            total = await conn.fetchval(count_query, *params)

            param_count += 1
            limit_param = param_count
            param_count += 1
            offset_param = param_count

            query = f"""
                SELECT id, performed_by, action, entity_type, entity_id,
                       description, performed_at
                FROM activity_log
                {where_clause}
                ORDER BY performed_at DESC
                LIMIT ${limit_param} OFFSET ${offset_param}
            """
            rows = await conn.fetch(query, *params, limit, offset)

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "actions": [dict(r) for r in rows],
        }
    except Exception as e:
        logger.error(f"Failed to get CRM actions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/practice-stats")
async def get_practice_stats(
    _admin: dict = Depends(verify_admin),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Get completed/active practice counts per team member via client.assigned_to"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                WITH email_normalized AS (
                    -- Normalise legacy/alias emails to canonical team_members email
                    SELECT
                        p.id AS practice_id,
                        p.status,
                        p.actual_price,
                        COALESCE(tm.email, c.assigned_to) AS canonical_email
                    FROM practices p
                    JOIN clients c ON p.client_id = c.id
                    LEFT JOIN team_members tm
                        ON tm.email ILIKE c.assigned_to
                        OR (
                            -- handle bare-username aliases like "ari" → "ari.firda@balizero.com"
                            c.assigned_to NOT LIKE '%@%'
                            AND tm.name ILIKE c.assigned_to
                        )
                        OR (
                            -- handle old-format aliases like "ari@balizero.com" → "ari.firda@balizero.com"
                            c.assigned_to LIKE '%@%'
                            AND tm.name ILIKE SPLIT_PART(c.assigned_to, '@', 1)
                        )
                    WHERE c.assigned_to IS NOT NULL
                      AND c.assigned_to != ''
                      AND c.deleted_at IS NULL
                )
                SELECT
                    canonical_email                                              AS email,
                    COUNT(*) FILTER (WHERE status = 'completed')                AS completed,
                    COUNT(*) FILTER (WHERE status = 'in_progress')              AS in_progress,
                    COUNT(*) FILTER (WHERE status NOT IN ('completed','inquiry','quotation')) AS active,
                    COALESCE(SUM(actual_price) FILTER (WHERE status = 'completed'), 0)       AS revenue
                FROM email_normalized
                WHERE canonical_email IS NOT NULL
                GROUP BY canonical_email
                ORDER BY completed DESC
            """)
        return {
            "success": True,
            "practice_stats": [dict(r) for r in rows],
        }
    except Exception as e:
        logger.error(f"Failed to get practice stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/export/messages")
async def export_messages(
    user_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    _admin: dict = Depends(verify_admin),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> StreamingResponse:
    """Export messages as CSV"""
    try:
        conditions = []
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        if date_from:
            param_count += 1
            conditions.append(f"DATE(conversation_started) >= ${param_count}::date")
            params.append(date_from)

        if date_to:
            param_count += 1
            conditions.append(f"DATE(conversation_started) <= ${param_count}::date")
            params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with db_pool.acquire() as conn:
            query = f"""
                SELECT conversation_id, user_id, role, content,
                       message_timestamp, conversation_started
                FROM v_messages
                {where_clause}
                ORDER BY conversation_started DESC, message_index
            """
            rows = await conn.fetch(query, *params)

        # Generate CSV
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["conversation_id", "user_id", "role", "content", "timestamp", "conv_started"]
        )

        for row in rows:
            writer.writerow(
                [
                    row["conversation_id"],
                    row["user_id"],
                    row["role"],
                    (row["content"] or "").replace("\n", " ")[:1000],
                    row["message_timestamp"],
                    row["conversation_started"],
                ]
            )

        csv_content = output.getvalue()
        output.close()

        filename = f"messages_export_{datetime.now(tz=timezone.utc).replace(tzinfo=None).strftime('%Y%m%d_%H%M%S')}.csv"

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error(f"Failed to export messages: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
