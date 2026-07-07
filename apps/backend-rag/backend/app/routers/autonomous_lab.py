"""Internal API surface for bounded autonomous lab drafts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.dependencies import get_optional_database_pool
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.services.autonomous_lab import (
    AutonomousLabOrchestrator,
    AutonomousLabPlanner,
    AutonomousLabReviewer,
    AutonomousLabStateStore,
    AutonomousLabWorker,
    CuratorDecision,
    MaterialSourceType,
    OrchestrationBounds,
    ReceiptStore,
    ResearchMaterial,
    build_lab_scheduler_status,
    build_runtime_snapshot,
    build_shadow_run,
    default_sandbox_policy,
)
from backend.services.autonomous_lab.reviewer import invalid_autonomous_lab_target_path_reason

router = APIRouter(prefix="/api/autonomous-lab", tags=["autonomous-lab", "internal"])
LAB_BOUNDS = OrchestrationBounds()


class LabMaterialPayload(BaseModel):
    """Raw material envelope accepted by the lab draft endpoint."""

    material_id: str = Field(..., min_length=1, max_length=128)
    source_type: MaterialSourceType
    source_uri: str = Field(..., min_length=1, max_length=512)
    title: str = Field(..., min_length=1, max_length=240)
    text: str = Field(..., min_length=1, max_length=LAB_BOUNDS.max_material_text_chars)
    captured_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class DraftRunRequest(BaseModel):
    """Request body for a deterministic lab draft."""

    objective: str = Field(..., min_length=1, max_length=800)
    task_id: str = Field(..., min_length=1, max_length=128)
    materials: list[LabMaterialPayload] = Field(
        default_factory=list,
        max_length=LAB_BOUNDS.max_materials,
    )
    target_paths: list[str] = Field(
        default_factory=list,
        max_length=LAB_BOUNDS.max_target_paths,
    )
    worktree_lane: str = Field(default="ops", min_length=1, max_length=64)
    created_at: datetime | None = None
    persist_receipt: bool = False


class DraftRunResponse(BaseModel):
    """Receipt-safe response for a lab draft."""

    accepted: bool
    run_id: str
    blocked: bool
    failed_blockers: list[str]
    receipt: dict[str, Any]
    receipt_path: str | None = None
    event_path: str | None = None


class CuratorDecisionRequest(BaseModel):
    """Operator decision at the Lab curator gate."""

    decision: CuratorDecision
    decision_id: str | None = Field(default=None, min_length=1, max_length=191)
    note: str | None = Field(default=None, max_length=4000)


class CancelRunRequest(BaseModel):
    """Operator request to cancel a non-running Lab run."""

    cancel_id: str | None = Field(default=None, min_length=1, max_length=191)
    reason: str | None = Field(default=None, max_length=4000)


class SchedulerTickRequest(BaseModel):
    """Operator-triggered bounded scheduler tick."""

    worker_id: str = Field(
        default="lab-worker:api",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
    )


async def require_autonomous_lab_enabled() -> bool:
    """Hide the internal lab API unless explicitly enabled."""
    if not settings.autonomous_lab_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="autonomous lab API is disabled",
        )
    return True


@router.get(
    "/status",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Read the Autonomous Lab control-room status",
)
async def get_autonomous_lab_status(
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Return a receipt-safe, read-only runtime snapshot."""
    return build_runtime_snapshot().to_receipt()


@router.get(
    "/runs",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Read Autonomous Lab run previews",
)
async def list_autonomous_lab_runs(
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Return the current dry-run worker lifecycle preview."""
    dry_run = AutonomousLabWorker().dry_run()
    return {
        "runs": [dry_run.to_receipt()],
        "execution_allowed": False,
        "manual_promotion_required": True,
    }


@router.get(
    "/scheduler",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Read the Autonomous Lab H24 scheduler status",
)
async def get_autonomous_lab_scheduler_status(
    db_pool: Any = Depends(get_optional_database_pool),
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Return H24 scheduler readiness without mutating runtime state."""
    return build_lab_scheduler_status(db_available=db_pool is not None).to_receipt()


@router.post(
    "/scheduler/tick",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Execute one bounded Autonomous Lab scheduler tick",
)
async def tick_autonomous_lab_scheduler(
    body: SchedulerTickRequest,
    db_pool: Any = Depends(get_optional_database_pool),
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Claim and advance at most one Lab run, fail-closed outside runtime policy."""
    scheduler = build_lab_scheduler_status(
        db_available=db_pool is not None,
        worker_id=body.worker_id,
    )
    if db_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"scheduler": scheduler.to_receipt()},
        )
    if not scheduler.can_tick:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"scheduler": scheduler.to_receipt()},
        )

    conn = _require_database_pool(db_pool)
    try:
        async with conn.acquire() as db_conn:
            tick = await AutonomousLabWorker().tick(
                db_conn,
                worker_id=body.worker_id,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return {"scheduler": scheduler.to_receipt(), "tick": tick.to_receipt()}


@router.get(
    "/runs/{run_id}",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Read one durable Autonomous Lab run",
)
async def get_autonomous_lab_run(
    run_id: str,
    db_pool: Any = Depends(get_optional_database_pool),
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Return one persisted Lab run without leaking raw objective text."""
    conn = _require_database_pool(db_pool)
    try:
        async with conn.acquire() as db_conn:
            record = await AutonomousLabStateStore().get_run(db_conn, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="autonomous lab run not found")
    return {"run": record.to_receipt()}


@router.get(
    "/runs/{run_id}/events",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Read durable Autonomous Lab run events",
)
async def list_autonomous_lab_run_events(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db_pool: Any = Depends(get_optional_database_pool),
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Return persisted Lab outbox events for one run."""
    conn = _require_database_pool(db_pool)
    try:
        async with conn.acquire() as db_conn:
            events = await AutonomousLabStateStore().list_run_events(
                db_conn,
                run_id=run_id,
                limit=limit,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"run_id": run_id, "events": [event.to_receipt() for event in events]}


@router.post(
    "/runs/{run_id}/decision",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Record an Autonomous Lab curator decision",
)
async def record_autonomous_lab_curator_decision(
    run_id: str,
    body: CuratorDecisionRequest,
    db_pool: Any = Depends(get_optional_database_pool),
    api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Record an idempotent manual gate decision for a paused Lab run."""
    conn = _require_database_pool(db_pool)
    decision_id = body.decision_id or f"{run_id}:{body.decision.value}"
    operator_id = _operator_id(api_key_verified)
    try:
        async with conn.acquire() as db_conn:
            result = await AutonomousLabStateStore().record_curator_decision(
                db_conn,
                run_id=run_id,
                decision=body.decision.value,
                decision_id=decision_id,
                operator_id=operator_id,
                note=body.note,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not result.changed and not result.idempotent_replay:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="curator decision requires an existing paused lab run",
        )
    return {"decision": result.to_receipt(), "promotion_allowed": False}


@router.post(
    "/runs/{run_id}/cancel",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Cancel a pending or paused Autonomous Lab run",
)
async def cancel_autonomous_lab_run(
    run_id: str,
    body: CancelRunRequest,
    db_pool: Any = Depends(get_optional_database_pool),
    api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Cancel a non-running Lab run through an explicit operator action."""
    conn = _require_database_pool(db_pool)
    cancel_id = body.cancel_id or f"{run_id}:cancel"
    operator_id = _operator_id(api_key_verified)
    try:
        async with conn.acquire() as db_conn:
            result = await AutonomousLabStateStore().cancel_run(
                db_conn,
                run_id=run_id,
                cancel_id=cancel_id,
                operator_id=operator_id,
                reason=body.reason,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not result.changed and not result.idempotent_replay:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cancel requires an existing pending or paused lab run",
        )
    return {"cancel": result.to_receipt(), "promotion_allowed": False}


@router.get(
    "/sandbox-policy",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Read the Autonomous Lab sandbox policy",
)
async def get_autonomous_lab_sandbox_policy(
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Return the fail-closed sandbox policy contract."""
    return default_sandbox_policy().to_receipt()


@router.get(
    "/shadow-run",
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Read an end-to-end Autonomous Lab shadow run",
)
async def get_autonomous_lab_shadow_run(
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Return a deterministic watch-to-curate shadow run without side effects."""
    return build_shadow_run().to_receipt()


@router.post(
    "/drafts",
    response_model=DraftRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_autonomous_lab_enabled)],
    summary="Draft a bounded autonomous lab run",
)
async def create_autonomous_lab_draft(
    body: DraftRunRequest,
    _api_key_verified: dict[str, Any] = Depends(verify_internal_api_key),
) -> DraftRunResponse:
    """Create a receipt-safe, planned-only autonomous lab draft."""
    orchestrator = AutonomousLabOrchestrator(
        planner=AutonomousLabPlanner(worktree_lane=body.worktree_lane)
    )
    try:
        result = orchestrator.orchestrate(
            objective=body.objective,
            materials=[_to_research_material(material) for material in body.materials],
            target_paths=_clean_target_paths(body.target_paths),
            task_id=body.task_id,
            created_at=body.created_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    receipt = result.to_receipt()
    final_review = AutonomousLabReviewer().review(result.run)
    failed_blockers = [
        *result.failed_blockers,
        *(finding.rule_id for finding in final_review.blockers),
    ]
    receipt["final_review"] = final_review.to_receipt()
    receipt["failed_blockers"] = sorted(set(failed_blockers))
    receipt["blocked"] = result.blocked or final_review.blocked

    receipt_path: str | None = None
    event_path: str | None = None
    if body.persist_receipt:
        if not settings.autonomous_lab_persistence_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="autonomous lab receipt persistence is disabled",
            )
        record = ReceiptStore(Path(settings.autonomous_lab_receipt_dir)).write_receipt(receipt)
        receipt_path = str(record.receipt_path)
        event_path = str(record.event_path)

    return DraftRunResponse(
        accepted=True,
        run_id=result.run.run_id,
        blocked=bool(receipt["blocked"]),
        failed_blockers=receipt["failed_blockers"],
        receipt=receipt,
        receipt_path=receipt_path,
        event_path=event_path,
    )


def _to_research_material(payload: LabMaterialPayload) -> ResearchMaterial:
    return ResearchMaterial(
        material_id=payload.material_id.strip(),
        source_type=payload.source_type,
        source_uri=payload.source_uri.strip(),
        title=payload.title.strip(),
        text=payload.text,
        captured_at=payload.captured_at or datetime.now().astimezone(),
        metadata={str(key): str(value) for key, value in payload.metadata.items()},
    )


def _clean_target_paths(target_paths: list[str]) -> list[str]:
    cleaned: list[str] = []
    for index, raw_path in enumerate(target_paths):
        candidate = raw_path.strip()
        if candidate.startswith("./"):
            candidate = candidate[2:]
        reason = _invalid_target_path_reason(candidate)
        if reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"target_paths[{index}] {reason}",
            )
        if candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


def _invalid_target_path_reason(candidate: str) -> str | None:
    return invalid_autonomous_lab_target_path_reason(candidate)


def _require_database_pool(db_pool: Any) -> Any:
    if db_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="autonomous lab runtime database is unavailable",
        )
    return db_pool


def _operator_id(api_key_verified: dict[str, Any]) -> str:
    for key in ("service", "sub", "subject", "client_id"):
        value = api_key_verified.get(key)
        if value:
            return str(value)
    return "internal-api"


__all__ = ["require_autonomous_lab_enabled", "router"]
