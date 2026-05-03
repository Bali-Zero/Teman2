"""Metabolic Health router — /api/metabolic/*.

Organ: exposes SYMBIOSIS Pillar 7 metabolic metrics (TTR, DO, IA, FE) via
HTTP so dashboards / operators / external agents can read them without
talking to the SQLite file directly.

Produces: HTTP JSON snapshots of organism_metrics.db.
Consumes: authenticated GET calls. Read-only — writes go through the
scripts/metabolic_rollup.py cron job, not this router.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metabolic", tags=["Metabolic Health"])

_DEFAULT_DB = os.path.expanduser(
    os.environ.get("METABOLIC_DB_PATH", "~/.agent/decisions/organism_metrics.db")
)


def _get_store():
    """Lazy import + construct MetabolicStore so router module import
    does not fail if cell-core is missing (degraded-mode parity with
    SkillService pattern in PR #55).
    """
    try:
        from cell_core.metabolic.storage import MetabolicStore
    except ImportError:
        logger.warning("cell_core.metabolic not importable — /api/metabolic will 503")
        return None
    return MetabolicStore(db_path=_DEFAULT_DB)


def _get_analyzer(store):
    from cell_core.metabolic.trend import TrendAnalyzer
    return TrendAnalyzer(store)


@router.get(
    "/latest",
    summary="Latest metabolic snapshot",
    description=(
        "Return the most recent MetabolicSnapshot (4 metrics: TTR, DO, IA, FE). "
        "Empty dict if the store has no snapshots yet (e.g. pre-baseline)."
    ),
)
async def get_latest(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="cell_core.metabolic not available in this deployment",
        )
    snaps = store.latest(n=1)
    if not snaps:
        return {"snapshot": None, "reason": "no_snapshots_yet"}
    return {"snapshot": snaps[0].to_dict()}


@router.get(
    "/trends",
    summary="Trend classification per metric",
    description=(
        "Return Improving / Stable / Degrading classification for each of the "
        "4 metrics, computed over the last N snapshots (default 30)."
    ),
)
async def get_trends(
    window: int = Query(30, ge=3, le=365),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="cell_core.metabolic not available")
    analyzer = _get_analyzer(store)
    return {"window": window, "trends": analyzer.classify_all(window=window)}


@router.get(
    "/series/{metric_type}",
    summary="Time series for one metric",
    description=(
        "Return [(calculated_at, value), ...] for the given metric_type "
        "(ttr | ontology_density | autonomy_index | escalation_freq)."
    ),
)
async def get_series(
    metric_type: str,
    n: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    valid = {"ttr", "ontology_density", "autonomy_index", "escalation_freq"}
    if metric_type not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"metric_type must be one of {sorted(valid)}",
        )
    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="cell_core.metabolic not available")
    series = store.metric_series(metric_type, n=n)
    return {"metric_type": metric_type, "n": len(series), "series": series}


@router.get(
    "/stats",
    summary="Storage statistics",
    description="Total snapshots, first/last timestamps, DB file size.",
)
async def get_stats(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="cell_core.metabolic not available")
    return store.stats()
