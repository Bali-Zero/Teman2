"""Admin endpoints for the unified jobs runner.

Exposes:
  GET  /api/jobs                    — registry + last run per job
  POST /api/jobs/{name}/run         — manual trigger (bypasses allowlist)
  GET  /api/jobs/{name}/runs        — recent history

Auth: X-API-Key: <env NUZANTARA_API_KEY>  OR  X-Debug-Key: <settings.admin_api_key>.
Matches the dual-auth pattern used by sibling admin routers
(e.g. admin_practice_auto_create.py).

NOTE on the legacy /api/admin/practice/auto-create endpoint: that route
still lives in admin_practice_auto_create.py and calls
run_auto_practice_creator directly — NOT via the runner. Migrating the
Air crontab caller to /api/jobs/auto-practice-creator/run is a separate
follow-up PR; this task leaves the legacy route alone to avoid breaking
the Air-side consumer's response-shape assumptions.
"""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.app.core.config import settings
from backend.jobs.models import JobRunRepository
from backend.jobs.runner import JobsRunner


# Module-level placeholder; the real runner is injected by router_registration
# at app startup via build_router(runner=...). We guard against None so a
# misregistration is obvious.
_runner: JobsRunner | None = None


def _require_api_key(
    x_api_key: str | None = Header(default=None, alias="x-api-key", convert_underscores=False),
    x_debug_key: str | None = Header(default=None, alias="x-debug-key", convert_underscores=False),
) -> bool:
    expected = os.environ.get("NUZANTARA_API_KEY", "")
    if x_api_key and expected and hmac.compare_digest(x_api_key, expected):
        return True
    if settings.admin_api_key and x_debug_key == settings.admin_api_key:
        return True
    raise HTTPException(status_code=401, detail="Invalid API key")


def build_router(*, runner: JobsRunner) -> APIRouter:
    global _runner
    _runner = runner

    router = APIRouter(tags=["admin-jobs"])

    @router.get("/api/jobs")
    async def list_jobs(_: bool = Depends(_require_api_key)) -> dict:
        assert _runner is not None
        repo = JobRunRepository(_runner._pool)
        out: list[dict] = []
        for decl in _runner._registry.all():
            runs = await repo.list_recent(decl.name, limit=1)
            last = runs[0] if runs else None
            out.append({
                "name": decl.name,
                "cron": decl.cron,
                "tz": decl.timezone,
                "enabled": decl.name in _runner._enabled,
                "last_run": None if last is None else {
                    "run_id": last.id,
                    "scheduled_tick": last.scheduled_tick.isoformat(),
                    "status": last.status,
                    "attempt": last.attempt,
                    "cost_cents": last.cost_cents,
                },
            })
        return {"jobs": out}

    @router.post("/api/jobs/{name}/run")
    async def run_job(name: str, _: bool = Depends(_require_api_key)) -> dict:
        assert _runner is not None
        try:
            decl = _runner._registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown job {name!r}")
        run_id = await _runner.dispatch_with_retry(
            decl=decl,
            scheduled_tick=datetime.now(timezone.utc),
            source="manual",
        )
        repo = JobRunRepository(_runner._pool)
        row = await repo.get(run_id)
        return {"run_id": run_id, "status": row.status}

    @router.get("/api/jobs/{name}/runs")
    async def list_runs(
        name: str, limit: int = 50, _: bool = Depends(_require_api_key)
    ) -> dict:
        assert _runner is not None
        try:
            _runner._registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown job {name!r}")
        repo = JobRunRepository(_runner._pool)
        rows = await repo.list_recent(name, limit=min(limit, 200))
        return {"runs": [
            {
                "run_id": r.id,
                "scheduled_tick": r.scheduled_tick.isoformat(),
                "status": r.status,
                "attempt": r.attempt,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error": r.error,
                "cost_cents": r.cost_cents,
                "meta": r.meta,
            } for r in rows
        ]}

    return router
