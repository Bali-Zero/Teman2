"""Owner-only HR endpoints for weekly cashout.

All routes gated by require_owner. 403 for non-owner team members.
"""
from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.app.deps.database import get_database_pool
from backend.app.deps.owner import require_owner
from backend.services.hr.owner_cashout import repository, sync_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/hr/owner/cashout",
    tags=["hr-owner-cashout"],
)


@router.get("/overview")
async def get_overview(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    return await repository.get_overview(pool)


@router.get("/weeks")
async def list_weeks(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    return {"weeks": await repository.list_weeks(pool)}


@router.get("/weeks/{week_id}")
async def get_week(
    week_id: int,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    detail = await repository.get_week_details(pool, week_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Week not found")
    return detail


@router.get("/visa-types")
async def get_visa_types(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    return await repository.get_visa_types(pool)


@router.post("/sync", status_code=202)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    pool: asyncpg.Pool = Depends(get_database_pool),
    user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    email = user.get("email", "owner")

    async def _runner() -> None:
        try:
            await sync_service.run_sync(
                pool, triggered_by=f"manual:{email}"
            )
        except Exception:
            logger.exception("[CASHOUT] background sync failed")

    background_tasks.add_task(_runner)
    return {"status": "started"}


@router.get("/sync-status")
async def get_sync_status(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    async with pool.acquire() as c:
        row = await c.fetchrow(
            """
            SELECT id, started_at, finished_at, status, weeks_processed,
                   weeks_skipped, rows_upserted, unknown_tabs, error, triggered_by
            FROM owner_cashout_sync_log
            ORDER BY started_at DESC LIMIT 1
            """
        )
    return {"last_sync": dict(row) if row else None}
