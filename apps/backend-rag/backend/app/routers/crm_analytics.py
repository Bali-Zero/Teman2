"""
CRM Client Analytics Router

Provides comprehensive analytics for client management:
- Client overview metrics
- Team performance analytics
- Revenue statistics
- Process/case analytics
- Temporal trends

Refactored: 2026-02-19
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.app.utils.error_handlers import handle_database_error
from backend.app.utils.logging_utils import get_logger, log_success

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/analytics", tags=["crm-analytics"])


# ================================================
# PYDANDIC MODELS
# ================================================


class ClientOverviewMetrics:
    """Client overview statistics."""

    total_clients: int
    new_this_month: int
    new_this_week: int
    by_status: dict[str, int]
    by_nationality: dict[str, int]


class TeamPerformanceMetrics:
    """Team member performance analytics."""

    member_email: str
    total_clients: int
    active_clients: int
    completed_clients: int
    conversion_rate: float
    avg_response_time_hours: float
    revenue_generated: float


class RevenueMetrics:
    """Revenue statistics."""

    total_quoted: float
    total_actual: float
    total_paid: float
    total_outstanding: float
    avg_per_client: float
    by_month: dict[str, dict[str, float]]


class ProcessTypeMetrics:
    """Process/case type analytics."""

    practice_type_code: str
    practice_type_name: str
    total_cases: int
    active_cases: int
    completed_cases: int
    avg_completion_days: float
    total_revenue: float


class ClientTrendPoint:
    """Single point in client acquisition trend."""

    period: str
    new_clients: int
    active_clients: int
    completed_cases: int
    revenue: float


# ================================================
# ENDPOINTS
# ================================================


@router.get("/clients/overview", response_model=dict[str, Any])
async def get_client_overview(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get client overview metrics.

    Returns:
        Total clients, new this month/week, breakdown by status and nationality.
    """
    try:
        async with db_pool.acquire() as conn:
            # Check permissions
            user_is_admin = is_crm_admin(current_user)
            user_email = current_user.get("email", "").lower()

            # Base query conditions
            where_clause = ""
            params = []
            if not user_is_admin:
                where_clause = "WHERE assigned_to = $1"
                params = [user_email]

            # Total clients
            total_query = f"SELECT COUNT(*) FROM clients {where_clause}"
            total_clients = await conn.fetchval(total_query, *params) or 0

            # New this month
            month_start = datetime.now(tz=timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_month_query = f"""
                SELECT COUNT(*) FROM clients
                {where_clause}
                {"AND" if where_clause else "WHERE"} created_at >= $2
            """
            month_params = params + [month_start] if params else [month_start]
            new_this_month = await conn.fetchval(new_month_query, *month_params) or 0

            # New this week
            week_start = datetime.now(tz=timezone.utc) - timedelta(days=datetime.now(tz=timezone.utc).weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            new_week_query = f"""
                SELECT COUNT(*) FROM clients
                {where_clause}
                {"AND" if where_clause else "WHERE"} created_at >= $2
            """
            week_params = params + [week_start] if params else [week_start]
            new_this_week = await conn.fetchval(new_week_query, *week_params) or 0

            # By status
            status_query = f"""
                SELECT status, COUNT(*) as count
                FROM clients
                {where_clause}
                GROUP BY status
            """
            status_rows = await conn.fetch(status_query, *params)
            by_status = {row["status"]: row["count"] for row in status_rows}

            # By nationality (top 10)
            nat_query = f"""
                SELECT nationality, COUNT(*) as count
                FROM clients
                {where_clause}
                GROUP BY nationality
                ORDER BY count DESC
                LIMIT 10
            """
            nat_rows = await conn.fetch(nat_query, *params)
            by_nationality = {row["nationality"] or "Unknown": row["count"] for row in nat_rows}

            log_success(logger, "Fetched client overview", user=user_email)

            return {
                "total_clients": total_clients,
                "new_this_month": new_this_month,
                "new_this_week": new_this_week,
                "by_status": by_status,
                "by_nationality": by_nationality,
            }

    except Exception as e:
        logger.error(f"Failed to fetch client overview: {e}", exc_info=True)
        raise handle_database_error(e)


@router.get("/team/performance", response_model=list[dict[str, Any]])
async def get_team_performance(
    period_days: int = 30,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """
    Get team member performance metrics.

    Args:
        period_days: Analysis period in days (default 30)

    Returns:
        List of team members with performance metrics.
    """
    try:
        async with db_pool.acquire() as conn:
            user_is_admin = is_crm_admin(current_user)
            user_email = current_user.get("email", "").lower()

            if not user_is_admin:
                # Non-admin can only see their own stats
                members = [user_email]
            else:
                # Get all team members who have clients
                member_rows = await conn.fetch(
                    "SELECT DISTINCT assigned_to FROM clients WHERE assigned_to IS NOT NULL",
                )
                members = [row["assigned_to"] for row in member_rows if row["assigned_to"]]

            datetime.now(tz=timezone.utc) - timedelta(days=period_days)
            results = []

            for member in members:
                # Total clients
                total = (
                    await conn.fetchval(
                        "SELECT COUNT(*) FROM clients WHERE assigned_to = $1", member,
                    )
                    or 0
                )

                # Active clients
                active = (
                    await conn.fetchval(
                        "SELECT COUNT(*) FROM clients WHERE assigned_to = $1 AND status = 'active'",
                        member,
                    )
                    or 0
                )

                # Completed (cases completed)
                completed = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM practices p
                    JOIN clients c ON p.client_id = c.id
                    WHERE c.assigned_to = $1 AND p.status = 'completed'
                    """,
                        member,
                    )
                    or 0
                )

                # Conversion rate (active / total)
                conversion_rate = (active / total * 100) if total > 0 else 0

                # Revenue generated
                revenue = (
                    await conn.fetchval(
                        """
                    SELECT COALESCE(SUM(actual_price), 0) FROM practices p
                    JOIN clients c ON p.client_id = c.id
                    WHERE c.assigned_to = $1 AND p.payment_status = 'paid'
                    """,
                        member,
                    )
                    or 0
                )

                results.append(
                    {
                        "member_email": member,
                        "total_clients": total,
                        "active_clients": active,
                        "completed_cases": completed,
                        "conversion_rate": round(conversion_rate, 1),
                        "revenue_generated": float(revenue),
                    },
                )

            # Sort by revenue
            results.sort(key=lambda x: x["revenue_generated"], reverse=True)

            return results

    except Exception as e:
        logger.error(f"Failed to fetch team performance: {e}", exc_info=True)
        raise handle_database_error(e)


@router.get("/revenue/summary", response_model=dict[str, Any])
async def get_revenue_summary(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get revenue summary metrics.

    Returns:
        Total quoted, actual, paid, outstanding, and monthly breakdown.
    """
    try:
        async with db_pool.acquire() as conn:
            user_is_admin = is_crm_admin(current_user)
            user_email = current_user.get("email", "").lower()

            where_clause = ""
            params = []
            if not user_is_admin:
                where_clause = "WHERE c.assigned_to = $1"
                params = [user_email]

            # Total metrics
            totals_query = f"""
                SELECT
                    COALESCE(SUM(p.quoted_price), 0) as total_quoted,
                    COALESCE(SUM(p.actual_price), 0) as total_actual,
                    COALESCE(SUM(CASE WHEN p.payment_status = 'paid' THEN p.actual_price ELSE 0 END), 0) as total_paid
                FROM practices p
                JOIN clients c ON p.client_id = c.id
                {where_clause}
            """
            row = await conn.fetchrow(totals_query, *params)

            total_quoted = float(row["total_quoted"] or 0)
            total_actual = float(row["total_actual"] or 0)
            total_paid = float(row["total_paid"] or 0)
            total_outstanding = total_actual - total_paid

            # Monthly breakdown (last 6 months)
            months = []
            for i in range(5, -1, -1):
                month_start = (datetime.now(tz=timezone.utc).replace(day=1) - timedelta(days=i * 30)).replace(
                    day=1,
                )
                month_end = (month_start + timedelta(days=32)).replace(day=1)
                month_label = month_start.strftime("%Y-%m")

                month_query = f"""
                    SELECT
                        COALESCE(SUM(p.actual_price), 0) as revenue,
                        COALESCE(SUM(CASE WHEN p.payment_status = 'paid' THEN p.actual_price ELSE 0 END), 0) as paid
                    FROM practices p
                    JOIN clients c ON p.client_id = c.id
                    {where_clause}
                    {"AND" if where_clause else "WHERE"} p.created_at >= $2 AND p.created_at < $3
                """
                month_params = (
                    params + [month_start, month_end] if params else [month_start, month_end]
                )
                month_row = await conn.fetchrow(month_query, *month_params)

                months.append(
                    {
                        "period": month_label,
                        "revenue": float(month_row["revenue"] or 0),
                        "paid": float(month_row["paid"] or 0),
                    },
                )

            # Average per client
            client_count = (
                await conn.fetchval(f"SELECT COUNT(*) FROM clients {where_clause}", *params) or 1
            )  # Avoid division by zero

            avg_per_client = total_actual / client_count

            return {
                "total_quoted": total_quoted,
                "total_actual": total_actual,
                "total_paid": total_paid,
                "total_outstanding": total_outstanding,
                "avg_per_client": round(avg_per_client, 2),
                "by_month": months,
            }

    except Exception as e:
        logger.error(f"Failed to fetch revenue summary: {e}", exc_info=True)
        raise handle_database_error(e)


@router.get("/processes/by-type", response_model=list[dict[str, Any]])
async def get_processes_by_type(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """
    Get process/case analytics grouped by type.

    Returns:
        List of practice types with metrics.
    """
    try:
        async with db_pool.acquire() as conn:
            user_is_admin = is_crm_admin(current_user)
            user_email = current_user.get("email", "").lower()

            where_clause = ""
            params = []
            if not user_is_admin:
                where_clause = "WHERE c.assigned_to = $1"
                params = [user_email]

            query = f"""
                SELECT
                    pt.code as practice_type_code,
                    pt.name as practice_type_name,
                    COUNT(*) as total_cases,
                    COUNT(CASE WHEN p.status NOT IN ('completed', 'cancelled') THEN 1 END) as active_cases,
                    COUNT(CASE WHEN p.status = 'completed' THEN 1 END) as completed_cases,
                    COALESCE(SUM(p.actual_price), 0) as total_revenue
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                JOIN clients c ON p.client_id = c.id
                {where_clause}
                GROUP BY pt.code, pt.name
                ORDER BY total_cases DESC
            """

            rows = await conn.fetch(query, *params)

            results = []
            for row in rows:
                results.append(
                    {
                        "practice_type_code": row["practice_type_code"],
                        "practice_type_name": row["practice_type_name"],
                        "total_cases": row["total_cases"],
                        "active_cases": row["active_cases"],
                        "completed_cases": row["completed_cases"],
                        "total_revenue": float(row["total_revenue"] or 0),
                    },
                )

            return results

    except Exception as e:
        logger.error(f"Failed to fetch processes by type: {e}", exc_info=True)
        raise handle_database_error(e)


@router.get("/clients/trend", response_model=list[dict[str, Any]])
async def get_client_trend(
    months: int = 6,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """
    Get client acquisition trend over time.

    Args:
        months: Number of months to analyze (default 6)

    Returns:
        List of monthly data points.
    """
    try:
        async with db_pool.acquire() as conn:
            user_is_admin = is_crm_admin(current_user)
            user_email = current_user.get("email", "").lower()

            where_clause = ""
            client_params = []
            practice_params = []

            if not user_is_admin:
                where_clause = "WHERE assigned_to = $1"
                client_params = [user_email]
                practice_params = [user_email]

            results = []
            for i in range(months - 1, -1, -1):
                month_start = (datetime.now(tz=timezone.utc).replace(day=1) - timedelta(days=i * 30)).replace(
                    day=1,
                )
                month_end = (month_start + timedelta(days=32)).replace(day=1)
                month_label = month_start.strftime("%b %Y")

                # New clients
                new_clients_query = f"""
                    SELECT COUNT(*) FROM clients
                    {where_clause}
                    {"AND" if where_clause else "WHERE"} created_at >= $2 AND created_at < $3
                """
                new_params = (
                    client_params + [month_start, month_end]
                    if client_params
                    else [month_start, month_end]
                )
                new_clients = await conn.fetchval(new_clients_query, *new_params) or 0

                # Revenue
                revenue_query = f"""
                    SELECT COALESCE(SUM(p.actual_price), 0)
                    FROM practices p
                    JOIN clients c ON p.client_id = c.id
                    {where_clause.replace("WHERE", "WHERE c.") if where_clause else ""}
                    {"AND" if where_clause else "WHERE"} p.created_at >= $2 AND p.created_at < $3
                """
                rev_params = (
                    practice_params + [month_start, month_end]
                    if practice_params
                    else [month_start, month_end]
                )
                revenue = await conn.fetchval(revenue_query, *rev_params) or 0

                results.append(
                    {
                        "period": month_label,
                        "new_clients": new_clients,
                        "revenue": float(revenue),
                    },
                )

            return results

    except Exception as e:
        logger.error(f"Failed to fetch client trend: {e}", exc_info=True)
        raise handle_database_error(e)
