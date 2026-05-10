"""Admin endpoints for the CRM Knowledge Graph mediated/thematic builders.

Endpoints exposed:
  - POST /api/admin/crm-kg/build-mediated  → run Tier-B mediated edge pass
  - GET  /api/admin/crm-kg/health          → counts of nodes/edges per type

Both are admin-API-key-gated via the existing X-API-Key middleware. Designed
to be invoked by:
  - Mini-Pro2 cron via curl (every 6h)
  - Manual ops trigger when populating after a backfill
  - Future LaunchAgent on Pro/Mini if remote cron fails

This router does NOT call the builder synchronously inline if it could
take >30s; it delegates to a BackgroundTask so the cron caller gets
HTTP 200 immediately and can move on.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/crm-kg", tags=["admin"])


@router.post("/build-mediated")
async def trigger_build_mediated(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Trigger one pass of the Tier-B mediated edge builder.

    Cron-friendly: returns HTTP 200 immediately with status='started',
    actual work happens in the background task. Errors are logged but
    do not propagate to the caller (best-effort cron pattern).
    """
    pool = getattr(request.app.state, "db_pool", None)
    if not pool:
        return {"status": "error", "message": "Database pool not available"}

    async def _run() -> None:
        from backend.services.knowledge_graph.mediated_edges_builder import (
            build_mediated_edges,
        )
        result = await build_mediated_edges(pool)
        logger.info("crm_kg.build_mediated background result: %s", result)

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Mediated edge builder running in background"}


@router.get("/health")
async def crm_kg_health(request: Request) -> dict[str, Any]:
    """Quick counts of crm_kg_nodes and crm_kg_edges by type/tier.

    Useful for monitoring growth and verifying the linker / builders
    are actually emitting data.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if not pool:
        return {"status": "error", "message": "Database pool not available"}

    try:
        async with pool.acquire() as conn:
            # Check tables exist (migration 167 may not be applied yet
            # in some envs, e.g. local dev that hasn't pulled main)
            tables_exist = await conn.fetchval(
                """
                SELECT
                    (SELECT EXISTS(
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'crm_kg_nodes'
                    ))
                    AND
                    (SELECT EXISTS(
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'crm_kg_edges'
                    ))
                """,
            )
            if not tables_exist:
                return {
                    "status": "warning",
                    "message": "crm_kg tables not yet present (migration 167 pending)",
                }

            nodes_by_type = await conn.fetch(
                """
                SELECT entity_type, COUNT(*) AS cnt
                FROM crm_kg_nodes
                WHERE deleted_at IS NULL
                GROUP BY entity_type
                ORDER BY entity_type
                """,
            )
            edges_by_tier = await conn.fetch(
                """
                SELECT edge_tier, relationship_type, COUNT(*) AS cnt
                FROM crm_kg_edges
                GROUP BY edge_tier, relationship_type
                ORDER BY edge_tier, relationship_type
                """,
            )

        return {
            "status": "healthy",
            "nodes_by_type": {
                row["entity_type"]: row["cnt"] for row in nodes_by_type
            },
            "edges_by_tier": [
                {
                    "tier": row["edge_tier"],
                    "type": row["relationship_type"],
                    "count": row["cnt"],
                }
                for row in edges_by_tier
            ],
        }
    except Exception as e:
        logger.error("crm_kg health failed: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)[:200]}
