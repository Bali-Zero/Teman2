"""
ZANTARA MEDIA - Distribution Router
Handles content distribution across social platforms
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.models import (
    Distribution,
    DistributionCreate,
    DistributionStatus,
    DistributionPlatform,
    DistributionMetrics,
    PaginatedResponse,
    APIResponse,
)

router = APIRouter()

# In-memory storage
_distribution_store: dict[str, Distribution] = {}


@router.get("/", response_model=PaginatedResponse)
async def list_distributions(
    content_id: Optional[str] = None,
    platform: Optional[DistributionPlatform] = None,
    status: Optional[DistributionStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List all distributions with optional filtering.
    """
    items = list(_distribution_store.values())

    if content_id:
        items = [d for d in items if d.content_id == content_id]
    if platform:
        items = [d for d in items if d.platform == platform]
    if status:
        items = [d for d in items if d.status == status]

    # Sort by created time (using scheduled_at or published_at)
    items.sort(
        key=lambda x: x.scheduled_at or x.published_at or datetime.min, reverse=True
    )

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return PaginatedResponse(
        items=[d.model_dump() for d in items[start:end]],
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )


@router.post("/", response_model=Distribution)
async def create_distribution(dist: DistributionCreate):
    """
    Create a new distribution (schedule content for a platform).
    """
    dist_id = f"dist_{len(_distribution_store) + 1}"

    new_dist = Distribution(
        id=dist_id,
        content_id=dist.content_id,
        platform=dist.platform,
        status=DistributionStatus.SCHEDULED
        if dist.scheduled_at
        else DistributionStatus.PENDING,
        scheduled_at=dist.scheduled_at,
    )

    _distribution_store[dist_id] = new_dist
    return new_dist


@router.get("/{distribution_id}", response_model=Distribution)
async def get_distribution(distribution_id: str):
    """
    Get distribution by ID.
    """
    if distribution_id not in _distribution_store:
        raise HTTPException(status_code=404, detail="Distribution not found")
    return _distribution_store[distribution_id]


@router.post("/{distribution_id}/publish", response_model=Distribution)
async def publish_distribution(distribution_id: str):
    """
    Publish distribution immediately to the platform.
    """
    if distribution_id not in _distribution_store:
        raise HTTPException(status_code=404, detail="Distribution not found")

    dist = _distribution_store[distribution_id]

    # TODO: Implement actual publishing to platform
    # This would call the appropriate social media API

    dist.status = DistributionStatus.PUBLISHED
    dist.published_at = datetime.utcnow()
    dist.platform_post_id = f"mock_post_{distribution_id}"
    dist.platform_url = f"https://example.com/post/{dist.platform_post_id}"

    return dist


@router.delete("/{distribution_id}", response_model=APIResponse)
async def cancel_distribution(distribution_id: str):
    """
    Cancel a pending or scheduled distribution.
    """
    if distribution_id not in _distribution_store:
        raise HTTPException(status_code=404, detail="Distribution not found")

    dist = _distribution_store[distribution_id]

    if dist.status == DistributionStatus.PUBLISHED:
        raise HTTPException(
            status_code=400, detail="Cannot cancel already published distribution"
        )

    del _distribution_store[distribution_id]
    return APIResponse(success=True, message="Distribution cancelled")


@router.get("/{distribution_id}/metrics", response_model=DistributionMetrics)
async def get_distribution_metrics(distribution_id: str):
    """
    Get engagement metrics for a distribution.
    """
    if distribution_id not in _distribution_store:
        raise HTTPException(status_code=404, detail="Distribution not found")

    dist = _distribution_store[distribution_id]

    if dist.status != DistributionStatus.PUBLISHED:
        raise HTTPException(
            status_code=400, detail="Metrics only available for published distributions"
        )

    # TODO: Fetch real metrics from platform APIs
    return DistributionMetrics(
        impressions=1500,
        engagements=120,
        clicks=45,
        shares=12,
    )


@router.get("/queue/pending")
async def get_pending_queue():
    """
    Get all pending distributions ready to be published.
    """
    pending = [
        d
        for d in _distribution_store.values()
        if d.status in [DistributionStatus.PENDING, DistributionStatus.SCHEDULED]
    ]

    # Sort by scheduled time
    pending.sort(key=lambda x: x.scheduled_at or datetime.max)

    return {"items": [d.model_dump() for d in pending]}


@router.post("/batch")
async def batch_create_distributions(
    content_id: str, platforms: list[DistributionPlatform]
):
    """
    Create distributions for multiple platforms at once.
    """
    created = []
    for platform in platforms:
        dist_id = f"dist_{len(_distribution_store) + 1}"
        new_dist = Distribution(
            id=dist_id,
            content_id=content_id,
            platform=platform,
            status=DistributionStatus.PENDING,
        )
        _distribution_store[dist_id] = new_dist
        created.append(new_dist)

    return {"created": len(created), "distributions": [d.model_dump() for d in created]}
