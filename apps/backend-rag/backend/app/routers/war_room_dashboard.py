"""War Room Dashboard Router — /api/war-room/metrics/*

Reads-only endpoints powering the /war-room/metrics Next.js page.
Requires admin access (same pattern as admin_logs).

Reference: docs/war-room-2.0-design.md §7.3 (Dashboard widgets).
"""

from __future__ import annotations

from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.services.war_room.dashboard_service import DashboardService
from backend.services.war_room.repository import WarRoomRepository

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/war-room/metrics",
    tags=["war-room-metrics"],
)


# ── Helpers ───────────────────────────────────────────────────


def _service(pool: asyncpg.Pool) -> DashboardService:
    return DashboardService(repo=WarRoomRepository(db_pool=pool))


DaysParam = Literal[14, 30, 90]


# ── Endpoints ─────────────────────────────────────────────────


@router.get("/timeline")
async def get_timeline(
    days: DaysParam = Query(14),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Timeline of published posts per day per tonal register."""
    svc = _service(pool)
    buckets = await svc.timeline(days=days)
    return {
        "days": days,
        "buckets": [b.to_dict() for b in buckets],
    }


@router.get("/heatmap")
async def get_heatmap(
    days: DaysParam = Query(30),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Register × metric_name heatmap (avg values + sample counts)."""
    svc = _service(pool)
    cells = await svc.register_performance_heatmap(days=days)
    return {
        "days": days,
        "cells": [c.to_dict() for c in cells],
    }


@router.get("/distribution")
async def get_distribution(
    days: DaysParam = Query(30),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Distribution of registers in the last N days + >40% alert flag."""
    svc = _service(pool)
    result = await svc.register_distribution(days=days)
    return result.to_dict() | {"days": days}


@router.get("/funnel")
async def get_funnel(
    days: DaysParam = Query(30),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Drafts → approved → published → leads funnel."""
    svc = _service(pool)
    stages = await svc.funnel(days=days)
    return {
        "days": days,
        "stages": [s.to_dict() for s in stages],
    }


@router.get("/rejections")
async def get_rejections(
    days: DaysParam = Query(30),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Rejection counts grouped by reason."""
    svc = _service(pool)
    buckets = await svc.rejection_reasons(days=days)
    return {
        "days": days,
        "buckets": [b.to_dict() for b in buckets],
    }


@router.get("/costs")
async def get_costs(
    days: DaysParam = Query(30),
    limit: int = Query(50, ge=1, le=200),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Top-N drafts by total cost (Imagen/Fireworks/DeepSeek/other) in period."""
    svc = _service(pool)
    rows = await svc.cost_per_draft(days=days, limit=limit)
    return {
        "days": days,
        "limit": limit,
        "rows": [r.to_dict() for r in rows],
        "grand_total_usd": round(sum(r.total_usd for r in rows), 4),
    }
