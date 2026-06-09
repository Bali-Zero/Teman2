"""Internal API surface for bounded autonomous lab drafts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.services.autonomous_lab import (
    AutonomousLabOrchestrator,
    AutonomousLabPlanner,
    AutonomousLabReviewer,
    MaterialSourceType,
    ReceiptStore,
    ResearchMaterial,
)

router = APIRouter(prefix="/api/autonomous-lab", tags=["autonomous-lab", "internal"])


class LabMaterialPayload(BaseModel):
    """Raw material envelope accepted by the lab draft endpoint."""

    material_id: str = Field(..., min_length=1, max_length=128)
    source_type: MaterialSourceType
    source_uri: str = Field(..., min_length=1, max_length=512)
    title: str = Field(..., min_length=1, max_length=240)
    text: str = Field(..., min_length=1)
    captured_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class DraftRunRequest(BaseModel):
    """Request body for a deterministic lab draft."""

    objective: str = Field(..., min_length=1, max_length=800)
    task_id: str = Field(..., min_length=1, max_length=128)
    materials: list[LabMaterialPayload] = Field(default_factory=list)
    target_paths: list[str] = Field(default_factory=list)
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


async def require_autonomous_lab_enabled() -> bool:
    """Hide the internal lab API unless explicitly enabled."""
    if not settings.autonomous_lab_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="autonomous lab API is disabled",
        )
    return True


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
    if not candidate or candidate == ".":
        return "must be a non-empty repository-relative path"
    if "\x00" in candidate:
        return "must not contain null bytes"
    if "\\" in candidate:
        return "must use POSIX separators"
    if "://" in candidate:
        return "must not be a URI"
    if candidate.startswith("~"):
        return "must not be home-relative"

    path = PurePosixPath(candidate)
    if path.is_absolute():
        return "must be repository-relative"
    if ".." in path.parts:
        return "must not contain path traversal"
    return None


__all__ = ["require_autonomous_lab_enabled", "router"]
