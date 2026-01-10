"""
ZANTARA CRM - Auto-CRM Statistics Router
Endpoints for AUTO CRM extraction statistics and monitoring
"""

from datetime import datetime, timedelta
from typing import Any

import asyncpg
from core.cache import cached
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_current_user, get_database_pool
from app.utils.crm_utils import is_crm_admin
from app.utils.error_handlers import handle_database_error
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/auto", tags=["crm-auto"])

# Constants
CACHE_TTL_STATS_SECONDS = 300  # 5 minutes


# ================================================
# PYDANTIC MODELS
# ================================================


class AutoCRMStats(BaseModel):
    """Auto-CRM statistics response"""

    total_extractions: int
    successful_extractions: int
    failed_extractions: int
    clients_created: int
    clients_updated: int
    practices_created: int
    last_24h: dict[str, int]
    last_7d: dict[str, int]
    extraction_confidence_avg: float | None
    top_practice_types: list[dict[str, Any]]
    recent_extractions: list[dict[str, Any]]


# ================================================
# ENDPOINTS
# ================================================


@router.get("/stats")
@cached(ttl=CACHE_TTL_STATS_SECONDS, prefix="crm_auto_stats")
async def get_auto_crm_stats(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> AutoCRMStats:
    """
    Get AUTO CRM extraction statistics

    Returns:
    - Total extractions (successful + failed)
    - Clients created/updated
    - Practices created
    - Recent activity (24h, 7d)
    - Average extraction confidence
    - Top practice types extracted
    - Recent extraction examples

    Performance: Cached for 5 minutes.
    """
    if not is_crm_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required for AUTO CRM statistics")
    try:
        async with db_pool.acquire() as conn:
            # Base time windows
            now = datetime.now()
            last_24h = now - timedelta(days=1)
            last_7d = now - timedelta(days=7)
            analysis_window = now - timedelta(days=days)

            # Get interactions with extracted_entities (indicates AUTO CRM processing)
            # We identify AUTO CRM extractions by:
            # 1. interaction_type = 'chat' (from conversations)
            # 2. extracted_entities is not null/empty
            # 3. channel = 'web_chat' (from web conversations)

            # Total extractions (interactions with extracted data)
            total_extractions_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM interactions
                WHERE interaction_type = 'chat'
                AND channel = 'web_chat'
                AND extracted_entities IS NOT NULL
                AND jsonb_typeof(extracted_entities) = 'object'
                AND created_at >= $1
                """,
                analysis_window,
            )
            total_extractions = total_extractions_row["count"] if total_extractions_row else 0

            # Successful extractions (have client_id or practice_id)
            successful_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM interactions
                WHERE interaction_type = 'chat'
                AND channel = 'web_chat'
                AND extracted_entities IS NOT NULL
                AND jsonb_typeof(extracted_entities) = 'object'
                AND (client_id IS NOT NULL OR practice_id IS NOT NULL)
                AND created_at >= $1
                """,
                analysis_window,
            )
            successful_extractions = successful_row["count"] if successful_row else 0
            failed_extractions = total_extractions - successful_extractions

            # Clients created (check clients created in the analysis window)
            clients_created_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM clients
                WHERE created_at >= $1
                AND created_by = 'system'
                """,
                analysis_window,
            )
            clients_created = clients_created_row["count"] if clients_created_row else 0

            # Clients updated (check last_interaction_date updated)
            clients_updated_row = await conn.fetchrow(
                """
                SELECT COUNT(DISTINCT client_id) as count
                FROM interactions
                WHERE interaction_type = 'chat'
                AND channel = 'web_chat'
                AND client_id IS NOT NULL
                AND created_at >= $1
                """,
                analysis_window,
            )
            clients_updated = clients_updated_row["count"] if clients_updated_row else 0

            # Practices created (check practices created in the analysis window)
            practices_created_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM practices
                WHERE created_at >= $1
                AND created_by = 'system'
                """,
                analysis_window,
            )
            practices_created = practices_created_row["count"] if practices_created_row else 0

            # Last 24h stats
            last_24h_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as extractions,
                    COUNT(DISTINCT client_id) as clients,
                    COUNT(DISTINCT practice_id) as practices
                FROM interactions
                WHERE interaction_type = 'chat'
                AND channel = 'web_chat'
                AND extracted_entities IS NOT NULL
                AND created_at >= $1
                """,
                last_24h,
            )
            last_24h_stats = {
                "extractions": last_24h_row["extractions"] if last_24h_row else 0,
                "clients": last_24h_row["clients"] if last_24h_row else 0,
                "practices": last_24h_row["practices"] if last_24h_row else 0,
            }

            # Last 7d stats
            last_7d_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as extractions,
                    COUNT(DISTINCT client_id) as clients,
                    COUNT(DISTINCT practice_id) as practices
                FROM interactions
                WHERE interaction_type = 'chat'
                AND channel = 'web_chat'
                AND extracted_entities IS NOT NULL
                AND created_at >= $1
                """,
                last_7d,
            )
            last_7d_stats = {
                "extractions": last_7d_row["extractions"] if last_7d_row else 0,
                "clients": last_7d_row["clients"] if last_7d_row else 0,
                "practices": last_7d_row["practices"] if last_7d_row else 0,
            }

            # Average extraction confidence (from extracted_entities JSON)
            confidence_row = await conn.fetchrow(
                """
                SELECT AVG(
                    CASE
                        WHEN extracted_entities->'client'->>'confidence' IS NOT NULL
                        THEN (extracted_entities->'client'->>'confidence')::float
                        ELSE NULL
                    END
                ) as avg_confidence
                FROM interactions
                WHERE interaction_type = 'chat'
                AND channel = 'web_chat'
                AND extracted_entities IS NOT NULL
                AND jsonb_typeof(extracted_entities) = 'object'
                AND created_at >= $1
                """,
                analysis_window,
            )
            extraction_confidence_avg = (
                float(confidence_row["avg_confidence"])
                if confidence_row and confidence_row["avg_confidence"] is not None
                else None
            )

            # Top practice types extracted
            top_practices_rows = await conn.fetch(
                """
                SELECT
                    pt.code,
                    pt.name,
                    COUNT(DISTINCT i.practice_id) as count
                FROM interactions i
                JOIN practices p ON i.practice_id = p.id
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE i.interaction_type = 'chat'
                AND i.channel = 'web_chat'
                AND i.practice_id IS NOT NULL
                AND i.created_at >= $1
                GROUP BY pt.code, pt.name
                ORDER BY count DESC
                LIMIT 5
                """,
                analysis_window,
            )
            top_practice_types = [dict(row) for row in top_practices_rows]

            # Recent extractions (last 10)
            recent_rows = await conn.fetch(
                """
                SELECT
                    i.id,
                    i.client_id,
                    i.practice_id,
                    i.summary,
                    i.sentiment,
                    i.created_at,
                    c.full_name as client_name,
                    pt.code as practice_type_code
                FROM interactions i
                LEFT JOIN clients c ON i.client_id = c.id
                LEFT JOIN practices p ON i.practice_id = p.id
                LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE i.interaction_type = 'chat'
                AND i.channel = 'web_chat'
                AND i.extracted_entities IS NOT NULL
                AND i.created_at >= $1
                ORDER BY i.created_at DESC
                LIMIT 10
                """,
                analysis_window,
            )
            recent_extractions = [
                {
                    "id": row["id"],
                    "client_id": row["client_id"],
                    "practice_id": row["practice_id"],
                    "summary": row["summary"],
                    "sentiment": row["sentiment"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "client_name": row["client_name"],
                    "practice_type_code": row["practice_type_code"],
                }
                for row in recent_rows
            ]

            return AutoCRMStats(
                total_extractions=total_extractions,
                successful_extractions=successful_extractions,
                failed_extractions=failed_extractions,
                clients_created=clients_created,
                clients_updated=clients_updated,
                practices_created=practices_created,
                last_24h=last_24h_stats,
                last_7d=last_7d_stats,
                extraction_confidence_avg=extraction_confidence_avg,
                top_practice_types=top_practice_types,
                recent_extractions=recent_extractions,
            )

    except Exception as e:
        logger.error(f"Failed to get AUTO CRM stats: {e}", exc_info=True)
        raise handle_database_error(e)
