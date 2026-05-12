"""Admin endpoints for the CRM Knowledge Graph workers.

Endpoints exposed:
  - GET  /api/admin/crm-kg/health           → counts of nodes/edges per type
  - POST /api/admin/crm-kg/backfill-drive-documents
                                             → OCR/KG pass over current CRM docs
  - POST /api/admin/crm-kg/build-mediated   → run Tier-B mediated edge pass (PR-B)
  - POST /api/admin/crm-kg/garbage-collect  → soft-delete orphan nodes,
                                                hard-delete old edges (PR-D)

All admin-API-key-gated via the existing X-API-Key middleware. Designed
to be invoked by Mini-Pro2 cron via curl. Background-task pattern: HTTP
200 returns in <1s, work happens async on the api machine without
blocking other requests.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/crm-kg", tags=["admin"])


@router.post("/backfill-drive-documents")
async def trigger_backfill_drive_documents(
    request: Request,
    background_tasks: BackgroundTasks,
    limit: int = Query(25, ge=1, le=250),
    dry_run: bool = Query(True),
    client_id: int | None = Query(None, ge=1),
    allow_ocr: bool = Query(False),
) -> dict[str, Any]:
    """Backfill current CRM Drive documents into OCR and crm_kg.

    Dry-run returns the candidate summary immediately. Live mode runs in a
    background task. OCR/Gemini dispatch is disabled unless allow_ocr=true.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if not pool:
        return {"status": "error", "message": "Database pool not available"}

    from backend.services.documents.crm_drive_backfill_service import (
        run_crm_drive_backfill,
    )

    if dry_run:
        return await run_crm_drive_backfill(
            pool,
            limit=limit,
            dry_run=True,
            client_id=client_id,
            allow_ocr=allow_ocr,
        )

    async def _run() -> None:
        result = await run_crm_drive_backfill(
            pool,
            limit=limit,
            dry_run=False,
            client_id=client_id,
            allow_ocr=allow_ocr,
        )
        logger.info("crm_kg.backfill_drive_documents background result: %s", result)

    background_tasks.add_task(_run)
    return {
        "status": "started",
        "message": "CRM Drive document backfill running in background",
        "dry_run": False,
        "allow_ocr": allow_ocr,
        "limit": limit,
        "client_id": client_id,
    }


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


@router.post("/garbage-collect")
async def trigger_garbage_collect(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Trigger one pass of the CRM KG garbage collector (PR-D).

    Soft-deletes nodes whose backing CRM data is gone, hard-deletes
    edges past grace window. See garbage_collector.py docstring.

    Cron-friendly: returns HTTP 200 immediately. Best-effort behavior.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if not pool:
        return {"status": "error", "message": "Database pool not available"}

    async def _run() -> None:
        from backend.services.knowledge_graph.garbage_collector import (
            garbage_collect,
        )
        result = await garbage_collect(pool)
        logger.info("crm_kg.garbage_collect background result: %s", result)

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Garbage collector running in background"}


@router.get("/health")
async def crm_kg_health(request: Request) -> dict[str, Any]:
    """Quick counts of crm_kg_nodes and crm_kg_edges by type/tier.

    Splits live vs soft_deleted node counts so PR-D's garbage collector
    progress is visible. Useful for monitoring dashboards and verifying
    the linker / builders are actually emitting data.
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
                SELECT
                    entity_type,
                    COUNT(*) FILTER (WHERE deleted_at IS NULL) AS live,
                    COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) AS soft_deleted
                FROM crm_kg_nodes
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
                row["entity_type"]: {
                    "live": row["live"],
                    "soft_deleted": row["soft_deleted"],
                }
                for row in nodes_by_type
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
