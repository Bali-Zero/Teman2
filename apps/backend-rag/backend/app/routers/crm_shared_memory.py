"""
ZANTARA CRM - Shared Memory Router
Team-wide memory access for AI and team members
Enables queries like "clients with upcoming renewals", "active practices for John Smith", etc.

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

import asyncpg
from core.cache import cached
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.dependencies import get_database_pool
from app.utils.error_handlers import handle_database_error
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/shared-memory", tags=["crm-shared-memory"])

# Constants
MAX_LIMIT = 100
DEFAULT_LIMIT = 20
CACHE_TTL_STATS_SECONDS = 300  # 5 minutes
CACHE_TTL_RENEWALS_SECONDS = 600  # 10 minutes
DEFAULT_RENEWAL_LOOKAHEAD_DAYS = 90
MAX_RENEWAL_LOOKAHEAD_DAYS = 365
DEFAULT_EXPIRY_WARNING_DAYS = 90  # Days before expiry to show in renewal queries
DEFAULT_RECENT_DAYS = 7  # Default days for "recent" queries
MAX_RECENT_DAYS = 30  # Maximum days for "recent" queries
RENEWALS_DASHBOARD_DAYS = 30  # Days for dashboard renewals overview


async def _get_practice_codes(conn: asyncpg.Connection) -> list[str]:
    """
    Get practice type codes from database

    Args:
        conn: Database connection

    Returns:
        List of practice type codes (e.g., ['KITAS', 'KITAP', 'PT_PMA'])
    """
    try:
        rows = await conn.fetch("SELECT code FROM practice_types WHERE active = true")
        return [row["code"] for row in rows]
    except Exception:
        # If table doesn't exist or query fails, return empty list
        return []


# ================================================
# ENDPOINTS
# ================================================


@router.get("/search")
async def search_shared_memory(
    q: str = Query(..., description="Natural language query"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Natural language search across CRM data

    Examples:
    - "clients with KITAS expiring soon"
    - "active practices for John Smith"
    - "recent interactions with antonello@balizero.com"
    - "urgent practices"
    - "PT PMA practices in progress"

    Returns relevant results from clients, practices, and interactions
    """
    try:
        async with db_pool.acquire() as conn:
            query_lower = q.lower()
            results = {
                "query": q,
                "clients": [],
                "practices": [],
                "interactions": [],
                "interpretation": [],
            }

            # Detect intent and search accordingly

            # 1. Renewal/Expiry queries
            if any(word in query_lower for word in ["expir", "renewal", "renew", "scaden"]):
                results["interpretation"].append("Detected: Renewal/Expiry query")

                rows = await conn.fetch(
                    """
                    SELECT
                        c.full_name as client_name,
                        c.email,
                        c.phone,
                        pt.name as practice_type,
                        pt.code as practice_code,
                        p.expiry_date,
                        p.expiry_date - CURRENT_DATE as days_until_expiry,
                        p.assigned_to,
                        p.id as practice_id
                    FROM practices p
                    JOIN clients c ON p.client_id = c.id
                    JOIN practice_types pt ON p.practice_type_id = pt.id
                    WHERE p.expiry_date IS NOT NULL
                    AND p.expiry_date > CURRENT_DATE
                    AND p.expiry_date <= CURRENT_DATE + INTERVAL '1 day' * $2
                    AND p.status = 'completed'
                    ORDER BY p.expiry_date ASC
                    LIMIT $1
                    """,
                    limit,
                    DEFAULT_EXPIRY_WARNING_DAYS,
                )

                results["practices"] = [dict(row) for row in rows]

            # 2. Client name search
            if not results["practices"]:  # If not a renewal query, try client search
                # Extract potential names (words that are capitalized)
                words = q.split()
                name_parts = [w for w in words if w[0].isupper() and len(w) > 2]

                if name_parts:
                    results["interpretation"].append(
                        f"Detected: Client search for '{' '.join(name_parts)}'"
                    )

                    search_pattern = f"%{' '.join(name_parts)}%"

                    # Search clients
                    client_rows = await conn.fetch(
                        """
                        SELECT
                            c.*,
                            COUNT(DISTINCT p.id) as total_practices,
                            COUNT(DISTINCT CASE WHEN p.status IN ('inquiry', 'in_progress', 'waiting_documents', 'submitted_to_gov') THEN p.id END) as active_practices
                        FROM clients c
                        LEFT JOIN practices p ON c.id = p.client_id
                        WHERE c.full_name ILIKE $1 OR c.email ILIKE $2
                        GROUP BY c.id
                        LIMIT $3
                        """,
                        search_pattern,
                        search_pattern,
                        limit,
                    )

                    results["clients"] = [dict(row) for row in client_rows]

                    # Get practices for found clients
                    if results["clients"]:
                        client_ids = [c["id"] for c in results["clients"]]

                        practice_rows = await conn.fetch(
                            """
                            SELECT
                                p.*,
                                pt.name as practice_type_name,
                                pt.code as practice_type_code,
                                c.full_name as client_name
                            FROM practices p
                            JOIN practice_types pt ON p.practice_type_id = pt.id
                            JOIN clients c ON p.client_id = c.id
                            WHERE p.client_id = ANY($1)
                            ORDER BY p.created_at DESC
                            """,
                            client_ids,
                        )

                        results["practices"] = [dict(row) for row in practice_rows]

            # 3. Practice type search - retrieved from database
            # TABULA RASA: No hardcoded practice codes - all practice types come from database
            practice_codes = await _get_practice_codes(conn)  # Retrieved from database at runtime
            detected_practice_type = None

            for code in practice_codes:
                if code.replace("_", " ").lower() in query_lower or code.lower() in query_lower:
                    detected_practice_type = code
                    break

            if detected_practice_type and not results["practices"]:
                results["interpretation"].append(
                    f"Detected: Practice type search for '{detected_practice_type}'"
                )

                # Determine status filter
                status_filter = []
                if "active" in query_lower or "in progress" in query_lower:
                    status_filter = [
                        "inquiry",
                        "quotation_sent",
                        "payment_pending",
                        "in_progress",
                        "waiting_documents",
                        "submitted_to_gov",
                    ]
                elif "completed" in query_lower:
                    status_filter = ["completed"]
                else:
                    status_filter = [
                        "inquiry",
                        "in_progress",
                        "waiting_documents",
                        "submitted_to_gov",
                    ]  # default to active

                practice_rows = await conn.fetch(
                    """
                    SELECT
                        p.*,
                        pt.name as practice_type_name,
                        pt.code as practice_type_code,
                        c.full_name as client_name,
                        c.email as client_email,
                        c.phone as client_phone
                    FROM practices p
                    JOIN practice_types pt ON p.practice_type_id = pt.id
                    JOIN clients c ON p.client_id = c.id
                    WHERE pt.code = $1
                    AND p.status = ANY($2)
                    ORDER BY p.created_at DESC
                    LIMIT $3
                    """,
                    detected_practice_type,
                    status_filter,
                    limit,
                )

                results["practices"] = [dict(row) for row in practice_rows]

            # 4. Urgency/Priority search
            if any(word in query_lower for word in ["urgent", "priority", "asap", "quickly"]):
                results["interpretation"].append("Detected: Urgency/Priority filter")

                practice_rows = await conn.fetch(
                    """
                    SELECT
                        p.*,
                        pt.name as practice_type_name,
                        c.full_name as client_name,
                        c.email as client_email
                    FROM practices p
                    JOIN practice_types pt ON p.practice_type_id = pt.id
                    JOIN clients c ON p.client_id = c.id
                    WHERE p.priority IN ('high', 'urgent')
                    AND p.status IN ('inquiry', 'in_progress', 'waiting_documents', 'submitted_to_gov')
                    ORDER BY
                        CASE p.priority
                            WHEN 'urgent' THEN 1
                            WHEN 'high' THEN 2
                            ELSE 3
                        END,
                        p.created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )

                results["practices"] = [dict(row) for row in practice_rows]

            # 5. Recent interactions
            if any(
                word in query_lower
                for word in ["recent", "last", "latest", "interaction", "communication"]
            ):
                results["interpretation"].append("Detected: Recent interactions query")

                # Extract days if mentioned ("last 7 days", "last week", etc.)
                days: int = DEFAULT_RECENT_DAYS  # default
                if "30" in q or "month" in query_lower:
                    days = MAX_RECENT_DAYS
                elif "week" in query_lower:
                    days = DEFAULT_RECENT_DAYS
                elif "today" in query_lower:
                    days = 1

                interaction_rows = await conn.fetch(
                    """
                    SELECT
                        i.*,
                        c.full_name as client_name,
                        c.email as client_email
                    FROM interactions i
                    JOIN clients c ON i.client_id = c.id
                    WHERE i.interaction_date >= NOW() - INTERVAL '1 day' * $1
                    ORDER BY i.interaction_date DESC
                    LIMIT $2
                    """,
                    days,
                    limit,
                )

                results["interactions"] = [dict(row) for row in interaction_rows]

            # Summary
            results["summary"] = {
                "clients_found": len(results["clients"]),
                "practices_found": len(results["practices"]),
                "interactions_found": len(results["interactions"]),
            }

            return results

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/upcoming-renewals")
@cached(ttl=CACHE_TTL_RENEWALS_SECONDS, prefix="crm_upcoming_renewals")
async def get_upcoming_renewals(
    days: int = Query(
        DEFAULT_RENEWAL_LOOKAHEAD_DAYS,
        ge=1,
        le=MAX_RENEWAL_LOOKAHEAD_DAYS,
        description="Look ahead days",
    ),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get all practices with upcoming renewal dates

    Default: next 90 days

    Performance: Cached for 10 minutes to reduce database load.
    """
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    c.full_name as client_name,
                    c.email,
                    c.phone,
                    c.whatsapp,
                    pt.name as practice_type,
                    pt.code as practice_code,
                    p.expiry_date,
                    p.expiry_date - CURRENT_DATE as days_until_expiry,
                    p.assigned_to,
                    p.id as practice_id,
                    p.status
                FROM practices p
                JOIN clients c ON p.client_id = c.id
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.expiry_date IS NOT NULL
                AND p.expiry_date > CURRENT_DATE
                AND p.expiry_date <= CURRENT_DATE + INTERVAL '1 day' * $1
                ORDER BY p.expiry_date ASC
                """,
                days,
            )

            renewals = [dict(row) for row in rows]

            return {"total_renewals": len(renewals), "days_ahead": days, "renewals": renewals}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/client/{client_id}/full-context")
async def get_client_full_context(
    client_id: int = Path(..., gt=0, description="Client ID"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get complete context for a client
    Everything the AI needs to know about this client

    Returns:
    - Client info
    - All practices (active + completed)
    - Recent interactions (last 20)
    - Upcoming renewals
    - Action items
    """
    try:
        async with db_pool.acquire() as conn:
            # Client info
            client_row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE id = $1""",
                client_id,
            )

            if not client_row:
                raise HTTPException(status_code=404, detail="Client not found")

            client = dict(client_row)

            # Practices
            practice_rows = await conn.fetch(
                """
                SELECT
                    p.*,
                    pt.name as practice_type_name,
                    pt.code as practice_type_code
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.client_id = $1
                ORDER BY p.created_at DESC
                """,
                client_id,
            )
            practices = [dict(row) for row in practice_rows]

            # Recent interactions
            interaction_rows = await conn.fetch(
                """
                SELECT id, client_id, practice_id, conversation_id, interaction_type, channel,
                       subject, summary, full_content, sentiment, team_member, direction,
                       duration_minutes, extracted_entities, action_items, interaction_date, created_at
                FROM interactions
                WHERE client_id = $1
                ORDER BY interaction_date DESC
                LIMIT 20
                """,
                client_id,
            )
            interactions = [dict(row) for row in interaction_rows]

            # Upcoming renewals
            renewal_rows = await conn.fetch(
                """
                SELECT
                    p.*,
                    pt.name as practice_type_name,
                    p.expiry_date - CURRENT_DATE as days_until_expiry
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.client_id = $1
                AND p.expiry_date > CURRENT_DATE
                ORDER BY p.expiry_date ASC
                """,
                client_id,
            )
            renewals = [dict(row) for row in renewal_rows]

            # Aggregate action items from interactions
            action_items = []
            for interaction in interactions:
                if interaction.get("action_items"):
                    action_items.extend(interaction["action_items"])

            return {
                "client": client,
                "practices": {
                    "total": len(practices),
                    "active": len(
                        [
                            p
                            for p in practices
                            if p["status"]
                            in ["inquiry", "in_progress", "waiting_documents", "submitted_to_gov"]
                        ]
                    ),
                    "completed": len([p for p in practices if p["status"] == "completed"]),
                    "list": practices,
                },
                "interactions": {"total": len(interactions), "recent": interactions},
                "renewals": renewals,
                "action_items": action_items[:10],  # top 10
                "summary": {
                    "first_contact": client.get("first_contact_date"),
                    "last_interaction": client.get("last_interaction_date"),
                    "total_practices": len(practices),
                    "total_interactions": len(interactions),
                    "upcoming_renewals": len(renewals),
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/team-overview")
@cached(ttl=CACHE_TTL_STATS_SECONDS, prefix="crm_team_overview")
async def get_team_overview(
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get team-wide CRM overview

    Perfect for dashboard or team queries like:
    - "How many active practices do we have?"
    - "What's our workload distribution?"
    - "Recent activity summary"

    Performance: Cached for 5 minutes to reduce database load.
    """
    try:
        async with db_pool.acquire() as conn:
            overview = {}

            # Total clients
            total_clients_row = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM clients WHERE status = 'active'"
            )
            overview["total_active_clients"] = (
                total_clients_row["count"] if total_clients_row else 0
            )

            # Total practices by status
            status_rows = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM practices
                GROUP BY status
                """
            )
            overview["practices_by_status"] = {row["status"]: row["count"] for row in status_rows}

            # Practices by team member
            team_member_rows = await conn.fetch(
                """
                SELECT assigned_to, COUNT(*) as count
                FROM practices
                WHERE assigned_to IS NOT NULL
                AND status IN ('inquiry', 'in_progress', 'waiting_documents', 'submitted_to_gov')
                GROUP BY assigned_to
                ORDER BY count DESC
                """
            )
            overview["active_practices_by_team_member"] = [dict(row) for row in team_member_rows]

            # Upcoming renewals (next N days)
            renewals_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM practices
                WHERE expiry_date IS NOT NULL
                AND expiry_date > CURRENT_DATE
                AND expiry_date <= CURRENT_DATE + INTERVAL '1 day' * $1
                """,
                RENEWALS_DASHBOARD_DAYS,
            )
            overview["renewals_next_30_days"] = renewals_row["count"] if renewals_row else 0

            # Recent interactions (last N days)
            interactions_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM interactions
                WHERE interaction_date >= NOW() - INTERVAL '1 day' * $1
                """,
                DEFAULT_RECENT_DAYS,
            )
            overview["interactions_last_7_days"] = (
                interactions_row["count"] if interactions_row else 0
            )

            # Practice types distribution
            type_rows = await conn.fetch(
                """
                SELECT
                    pt.code,
                    pt.name,
                    COUNT(p.id) as count
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.status IN ('inquiry', 'in_progress', 'waiting_documents', 'submitted_to_gov')
                GROUP BY pt.code, pt.name
                ORDER BY count DESC
                """
            )
            overview["active_practices_by_type"] = [dict(row) for row in type_rows]

            return overview

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)
