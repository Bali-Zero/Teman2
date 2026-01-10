"""
System Observability API Router
Exposes real-time health checks and system metrics for the Admin "Control Room" Dashboard.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.routers.team_activity import get_admin_user
from backend.services.monitoring.unified_health_service import (
    UnifiedHealthService,
    get_unified_health_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["system-observability"])


@router.get("/system-health")
async def get_system_health(
    admin_user: dict = Depends(get_admin_user),
    service: UnifiedHealthService = Depends(get_unified_health_service),
) -> dict[str, Any]:
    """
    Get comprehensive system health report (ADMIN ONLY).

    Aggregates status from:
    - PostgreSQL (Connectivity + Latency)
    - Qdrant (Vector DB Health)
    - Redis (Cache Status)
    - API (Self-check)
    - System Metrics (CPU, RAM, Disk, Uptime)
    """
    try:
        # Initialize HTTP/Redis clients if needed (lazy init)
        if not service.http_client:
            await service.initialize()

        report = await service.run_all_checks(use_cache=True)
        return report

    except Exception as e:
        logger.error(f"❌ System health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Data Explorer: PostgreSQL
# ============================================================================


@router.get("/postgres/tables")
async def get_postgres_tables(
    admin_user: dict = Depends(get_admin_user),
) -> list[str]:
    """List all public tables in PostgreSQL (ADMIN ONLY)"""
    import asyncpg

    from backend.app.core.config import settings

    try:
        conn = await asyncpg.connect(settings.database_url)
        try:
            query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """
            rows = await conn.fetch(query)
            return [r["table_name"] for r in rows]
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"❌ Failed to list tables: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/postgres/data")
async def get_table_data(
    table: str,
    limit: int = 50,
    offset: int = 0,
    admin_user: dict = Depends(get_admin_user),
) -> dict[str, Any]:
    """Get raw data from a table (ADMIN ONLY)"""
    from datetime import datetime

    import asyncpg

    from backend.app.core.config import settings

    # Basic sanitized table name check (prevent injection)
    if not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid table name")

    try:
        conn = await asyncpg.connect(settings.database_url)
        try:
            # Get columns
            # Get row count
            count_query = f"SELECT COUNT(*) FROM {table}"
            total_rows = await conn.fetchval(count_query)

            # Get data
            query = f"SELECT * FROM {table} LIMIT $1 OFFSET $2"
            rows = await conn.fetch(query, limit, offset)

            # Serialize rows
            results = []
            columns = []
            if rows:
                columns = list(rows[0].keys())
                for row in rows:
                    item = {}
                    for col, val in row.items():
                        # Handle datetime serialization
                        if isinstance(val, datetime):
                            item[col] = val.isoformat()
                        else:
                            item[col] = val
                    results.append(item)

            return {
                "table": table,
                "total_rows": total_rows,
                "columns": columns,
                "rows": results,
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"❌ Failed to fetch table data: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Data Explorer: Qdrant
# ============================================================================


@router.get("/qdrant/collections")
async def get_qdrant_collections(
    admin_user: dict = Depends(get_admin_user),
) -> dict[str, Any]:
    """List Qdrant collections with stats (ADMIN ONLY)"""
    from backend.core.qdrant_db import QdrantClient

    from backend.app.core.config import settings

    try:
        client = QdrantClient(qdrant_url=settings.qdrant_url)
        # Using raw REST API via client because methods might vary
        # Or usually client.client.get_collections()
        # For simplicity, we assume standard qdrant_client usage if available,
        # but let's stick to the core wrapper or direct invocation if needed.
        # The core wrapper usually exposes .client (Sync or Async).
        # Assuming QdrantClient wrapper has .client which is the QdrantClient instance

        # Let's try raw HTTP request to Qdrant if the wrapper is opaque,
        # but better to use the wrapper.
        # Re-using UnifiedHealthService pattern of direct check if possible,
        # but here we need data.
        import httpx

        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{settings.qdrant_url}/collections")
            resp.raise_for_status()
            data = resp.json()
            return data["result"]  # { collections: [...] }

    except Exception as e:
        logger.error(f"❌ Failed to list Qdrant collections: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/qdrant/points")
async def get_qdrant_points(
    collection: str,
    limit: int = 20,
    offset: str | None = None,  # scroll_id
    admin_user: dict = Depends(get_admin_user),
) -> dict[str, Any]:
    """Browse Qdrant points (ADMIN ONLY)"""
    import httpx

    from backend.app.core.config import settings

    try:
        # Using scroll API
        payload = {"limit": limit, "with_payload": True, "with_vector": False}
        if offset:
            payload["offset"] = offset

        async with httpx.AsyncClient() as http_client:
            resp = await http_client.post(
                f"{settings.qdrant_url}/collections/{collection}/points/scroll",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["result"]

    except Exception as e:
        logger.error(f"❌ Failed to fetch Qdrant points: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
