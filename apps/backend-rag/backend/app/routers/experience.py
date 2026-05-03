"""Experience Library router — /api/experience/*.

Organ: records execution trajectories in the unified Genome (SYMBIOSIS
Pilastro 2 — Accumulazione). Cells call /record after a pulse; Thinkers
call /query before reasoning from scratch.

Produces: cell_core.genome rows (type='trajectory') in the shared SQLite KB.
Consumes: authenticated POST/GET calls from cells + internal dispatchers.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.dependencies import get_current_user
from backend.core.cache import invalidate_cache
from backend.services.experience.models import (
    TrajectoryQuery,
    TrajectoryRecord,
    TrajectoryResult,
)
from backend.services.experience.service import ExperienceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experience", tags=["Experience Library"])

# Module-level singleton: one service per process, backed by the configured
# SQLite path (EXPERIENCE_DB_PATH env var). Keeps the Genome write_lock
# coherent across concurrent requests.
_service_singleton: ExperienceService | None = None


def get_experience_service() -> ExperienceService:
    """FastAPI dependency that returns the process-wide ExperienceService.

    Overridable in tests via ``app.dependency_overrides`` to supply a
    temp-path service without polluting ~/.nuzantara/experience.db.
    """
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = ExperienceService()
    return _service_singleton


@router.post(
    "/record",
    summary="Record an execution trajectory",
    description=(
        "Persist a trajectory (success|failure|partial) in the shared Genome. "
        "Idempotent: re-posting the same trajectory_id updates procedure/tags "
        "and keeps the max confidence."
    ),
)
async def record_trajectory(
    payload: TrajectoryRecord,
    current_user: dict = Depends(get_current_user),
    service: ExperienceService = Depends(get_experience_service),
) -> dict[str, Any]:
    try:
        result = service.record(payload)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception(
            "experience.record failed for trajectory_id=%s by user=%s",
            payload.trajectory_id, current_user.get("email", "?"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to record trajectory",
        ) from exc
    logger.info(
        "experience.record action=%s trajectory_id=%s cell=%s outcome=%s user=%s",
        result.get("action"), payload.trajectory_id, payload.cell,
        payload.outcome, current_user.get("email", "?"),
    )
    # Cache namespace kept tight so unrelated consumers are unaffected.
    await invalidate_cache("zantara:experience:*")
    return result


@router.post(
    "/query",
    summary="Search trajectories by FTS + filters",
    description=(
        "Full-text search on trajectory procedures, optionally filtered by "
        "outcome, cell, tag. Results ordered by FTS rank then confidence."
    ),
)
async def query_trajectories(
    payload: TrajectoryQuery,
    current_user: dict = Depends(get_current_user),
    service: ExperienceService = Depends(get_experience_service),
) -> dict[str, Any]:
    try:
        results = service.query(payload)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception(
            "experience.query failed for query=%r by user=%s",
            payload.query, current_user.get("email", "?"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to query trajectories",
        ) from exc
    return {
        "query": payload.query,
        "count": len(results),
        "results": [r.model_dump(mode="json") for r in results],
    }


@router.get(
    "/stats",
    summary="Aggregate trajectory counts by outcome",
)
async def trajectory_stats(
    cell: str | None = Query(default=None, max_length=64),
    current_user: dict = Depends(get_current_user),
    service: ExperienceService = Depends(get_experience_service),
) -> dict[str, Any]:
    _ = current_user  # auth guard only
    return service.stats(cell=cell)


@router.get(
    "/{trajectory_id}",
    summary="Fetch one trajectory by id",
    response_model=TrajectoryResult,
)
async def get_trajectory(
    trajectory_id: str,
    current_user: dict = Depends(get_current_user),
    service: ExperienceService = Depends(get_experience_service),
) -> TrajectoryResult:
    _ = current_user  # auth guard only
    result = service.get_by_id(trajectory_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"trajectory '{trajectory_id}' not found",
        )
    return result
