"""Skill Registry router — /api/skill/*.

Organ: canonical reusable procedures in the unified Genome (SYMBIOSIS
Pilastro 2 — Accumulazione). Cells record skills as they distil successful
trajectories; Thinkers consult them before reasoning from scratch; the
weekly maintenance cron promotes hot skills to tier1/tier2 and decays
stale ones.

Produces: cell_core.genome rows (type='skill') in the shared SQLite KB.
Consumes: authenticated POST/GET calls from cells + internal dispatchers.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.dependencies import get_current_user
from backend.core.cache import invalidate_cache
from backend.services.skill.models import (
    SkillQuery,
    SkillRecord,
    SkillResult,
    SkillTier,
)
from backend.services.skill.service import SkillService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skill", tags=["Skill Registry"])

_service_singleton: SkillService | None = None


def get_skill_service() -> SkillService:
    """FastAPI dependency returning the process-wide SkillService."""
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = SkillService()
    return _service_singleton


# ─── POST /record ────────────────────────────────────────────────────


@router.post(
    "/record",
    summary="Record a reusable skill",
    description=(
        "Persist a skill (type='skill') in the shared Genome. Idempotent by "
        "skill_id: re-posting updates procedure/precondition/success_criterion "
        "and keeps the max confidence. Tier (if previously promoted) is preserved."
    ),
)
async def record_skill(
    payload: SkillRecord,
    current_user: dict = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> dict[str, Any]:
    try:
        result = service.record(payload)
    except Exception as exc:  # pragma: no cover
        logger.exception(
            "skill.record failed for skill_id=%s by user=%s",
            payload.skill_id, current_user.get("email", "?"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to record skill",
        ) from exc
    logger.info(
        "skill.record action=%s skill_id=%s cell=%s user=%s",
        result.get("action"), payload.skill_id, payload.cell,
        current_user.get("email", "?"),
    )
    await invalidate_cache("zantara:skill:*")
    return result


# ─── POST /query ─────────────────────────────────────────────────────


@router.post(
    "/query",
    summary="Search skills by FTS + filters",
    description=(
        "Full-text search on procedure / precondition / success_criterion, "
        "optionally filtered by cell, tier, and min_confidence. Results "
        "ordered by FTS rank then confidence."
    ),
)
async def query_skills(
    payload: SkillQuery,
    current_user: dict = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> dict[str, Any]:
    try:
        results = service.query(payload)
    except Exception as exc:  # pragma: no cover
        logger.exception(
            "skill.query failed for query=%r by user=%s",
            payload.query, current_user.get("email", "?"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to query skills",
        ) from exc
    return {
        "query": payload.query,
        "count": len(results),
        "results": [r.model_dump(mode="json") for r in results],
    }


# ─── GET /stats ──────────────────────────────────────────────────────


@router.get(
    "/stats",
    summary="Aggregate skill counts by tier + cell + avg confidence",
)
async def skill_stats(
    current_user: dict = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> dict[str, Any]:
    _ = current_user  # auth guard only
    return service.stats()


# ─── GET /top ────────────────────────────────────────────────────────


@router.get(
    "/top",
    summary="Return active skills at the requested tier (default tier1)",
)
async def top_skills(
    tier: SkillTier = Query(default=SkillTier.TIER1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> dict[str, Any]:
    _ = current_user
    results = service.get_top_skills(tier=tier, limit=limit)
    return {
        "tier": tier.value if hasattr(tier, "value") else tier,
        "count": len(results),
        "results": [r.model_dump(mode="json") for r in results],
    }


# ─── GET /merge-proposals ────────────────────────────────────────────


@router.get(
    "/merge-proposals",
    summary="Read pending skill-merge proposals (from the weekly job)",
    description=(
        "Returns the jsonl of proposals written by the auto-merge job "
        "(Day 5 of Sprint 5.2 Week 3-4). Read-only — Zero approves manually."
    ),
)
async def merge_proposals(
    current_user: dict = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> dict[str, Any]:
    _ = current_user
    proposals = service.merge_proposals()
    return {"count": len(proposals), "proposals": proposals}


# ─── GET /{skill_id} ─────────────────────────────────────────────────


@router.get(
    "/{skill_id}",
    summary="Fetch one skill by id",
    response_model=SkillResult,
)
async def get_skill(
    skill_id: str,
    current_user: dict = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> SkillResult:
    _ = current_user
    result = service.get_by_id(skill_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"skill '{skill_id}' not found",
        )
    return result
