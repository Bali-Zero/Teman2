"""
ZANTARA MEDIA - Intel Signals Router
Handles intelligence signals from INTEL SCRAPING system
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.models import (
    IntelSignal,
    IntelSignalProcess,
    IntelPriority,
    ContentCategory,
    PaginatedResponse,
    APIResponse,
)

router = APIRouter()

# In-memory storage - in production, this will be populated from INTEL SCRAPING
_intel_store: dict[str, IntelSignal] = {
    "intel_1": IntelSignal(
        id="intel_1",
        title="New visa regulation: E33G Remote Worker KITAS processing time reduced to 3 days",
        source_name="Imigrasi Indonesia",
        source_url="https://imigrasi.go.id/news/123",
        category=ContentCategory.IMMIGRATION,
        priority=IntelPriority.HIGH,
        summary="The Directorate General of Immigration announced that E33G Remote Worker KITAS applications will now be processed within 3 working days.",
        detected_at=datetime.utcnow(),
        processed=False,
    ),
    "intel_2": IntelSignal(
        id="intel_2",
        title="Tax deadline reminder: SPT Tahunan due March 31, 2025",
        source_name="DJP Online",
        source_url="https://djponline.pajak.go.id/",
        category=ContentCategory.TAX,
        priority=IntelPriority.HIGH,
        summary="Annual tax return (SPT Tahunan) deadline approaching. PT PMA companies must file by March 31, 2025.",
        detected_at=datetime.utcnow(),
        processed=False,
    ),
}


@router.get("/", response_model=PaginatedResponse)
async def list_intel_signals(
    category: Optional[ContentCategory] = None,
    priority: Optional[IntelPriority] = None,
    processed: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List all intel signals with optional filtering.
    """
    items = list(_intel_store.values())

    if category:
        items = [s for s in items if s.category == category]
    if priority:
        items = [s for s in items if s.priority == priority]
    if processed is not None:
        items = [s for s in items if s.processed == processed]

    # Sort by priority (high first) then by detection time
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(
        key=lambda x: (priority_order.get(x.priority.value, 99), x.detected_at),
        reverse=True,
    )

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return PaginatedResponse(
        items=[s.model_dump() for s in items[start:end]],
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )


@router.get("/stats")
async def get_intel_stats():
    """
    Get statistics about intel signals.
    """
    signals = list(_intel_store.values())
    unprocessed = [s for s in signals if not s.processed]

    return {
        "total": len(signals),
        "unprocessed": len(unprocessed),
        "by_priority": {
            "high": len([s for s in unprocessed if s.priority == IntelPriority.HIGH]),
            "medium": len(
                [s for s in unprocessed if s.priority == IntelPriority.MEDIUM]
            ),
            "low": len([s for s in unprocessed if s.priority == IntelPriority.LOW]),
        },
        "by_category": {
            cat.value: len([s for s in unprocessed if s.category == cat])
            for cat in ContentCategory
        },
    }


@router.get("/{signal_id}", response_model=IntelSignal)
async def get_intel_signal(signal_id: str):
    """
    Get intel signal by ID.
    """
    if signal_id not in _intel_store:
        raise HTTPException(status_code=404, detail="Intel signal not found")
    return _intel_store[signal_id]


@router.post("/{signal_id}/process", response_model=APIResponse)
async def process_intel_signal(signal_id: str, process_request: IntelSignalProcess):
    """
    Process an intel signal (create content, dismiss, or archive).
    """
    if signal_id not in _intel_store:
        raise HTTPException(status_code=404, detail="Intel signal not found")

    signal = _intel_store[signal_id]

    if signal.processed:
        raise HTTPException(status_code=400, detail="Signal already processed")

    if process_request.action == "create_content":
        # TODO: Trigger AI content generation
        signal.processed = True
        signal.content_id = f"content_from_{signal_id}"
        return APIResponse(
            success=True,
            message="Content creation triggered",
            data={"content_id": signal.content_id},
        )

    elif process_request.action == "dismiss":
        signal.processed = True
        return APIResponse(success=True, message="Signal dismissed")

    elif process_request.action == "archive":
        signal.processed = True
        return APIResponse(success=True, message="Signal archived")

    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown action: {process_request.action}"
        )


@router.post("/refresh", response_model=APIResponse)
async def refresh_intel_signals():
    """
    Trigger a refresh of intel signals from INTEL SCRAPING system.
    """
    # TODO: Call INTEL SCRAPING API to fetch new signals
    return APIResponse(
        success=True,
        message="Intel refresh triggered",
        data={"sources_checked": 630, "new_signals": 0},
    )


@router.post("/bulk-dismiss", response_model=APIResponse)
async def bulk_dismiss_signals(signal_ids: list[str]):
    """
    Dismiss multiple signals at once.
    """
    dismissed = 0
    for signal_id in signal_ids:
        if signal_id in _intel_store and not _intel_store[signal_id].processed:
            _intel_store[signal_id].processed = True
            dismissed += 1

    return APIResponse(
        success=True,
        message=f"Dismissed {dismissed} signals",
        data={"dismissed": dismissed},
    )
