"""
ZANTARA MEDIA - Content Router
CRUD operations for content management
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.models import (
    Content,
    ContentCreate,
    ContentUpdate,
    ContentStatus,
    ContentType,
    ContentCategory,
    ContentMetadata,
    PaginatedResponse,
    APIResponse,
)

router = APIRouter()

# In-memory storage for now - will be replaced with database
_content_store: dict[str, Content] = {}


def _generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title."""
    import re

    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


@router.get("/", response_model=PaginatedResponse)
async def list_content(
    status: Optional[ContentStatus] = None,
    type: Optional[ContentType] = None,
    category: Optional[ContentCategory] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List all content with optional filtering and pagination.
    """
    items = list(_content_store.values())

    # Apply filters
    if status:
        items = [c for c in items if c.status == status]
    if type:
        items = [c for c in items if c.type == type]
    if category:
        items = [c for c in items if c.category == category]
    if search:
        search_lower = search.lower()
        items = [
            c
            for c in items
            if search_lower in c.title.lower()
            or search_lower in (c.summary or "").lower()
        ]

    # Sort by updated_at descending
    items.sort(key=lambda x: x.updated_at, reverse=True)

    # Pagination
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = items[start:end]

    return PaginatedResponse(
        items=[c.model_dump() for c in paginated_items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )


@router.post("/", response_model=Content)
async def create_content(content: ContentCreate):
    """
    Create new content piece.
    """
    content_id = f"content_{len(_content_store) + 1}"
    now = datetime.utcnow()

    new_content = Content(
        id=content_id,
        slug=_generate_slug(content.title),
        status=ContentStatus.DRAFT,
        author_id="user_1",  # TODO: Get from auth
        author_name="Zero",
        created_at=now,
        updated_at=now,
        metadata=ContentMetadata(
            word_count=len(content.body.split()) if content.body else 0,
            reading_time_minutes=max(1, len(content.body.split()) // 200)
            if content.body
            else 0,
        ),
        **content.model_dump(),
    )

    _content_store[content_id] = new_content
    return new_content


@router.get("/{content_id}", response_model=Content)
async def get_content(content_id: str):
    """
    Get content by ID.
    """
    if content_id not in _content_store:
        raise HTTPException(status_code=404, detail="Content not found")
    return _content_store[content_id]


@router.patch("/{content_id}", response_model=Content)
async def update_content(content_id: str, update: ContentUpdate):
    """
    Update content piece.
    """
    if content_id not in _content_store:
        raise HTTPException(status_code=404, detail="Content not found")

    content = _content_store[content_id]
    update_data = update.model_dump(exclude_unset=True)

    # Update fields
    for field, value in update_data.items():
        setattr(content, field, value)

    content.updated_at = datetime.utcnow()

    # Recalculate metadata if body changed
    if "body" in update_data:
        content.metadata.word_count = len(content.body.split()) if content.body else 0
        content.metadata.reading_time_minutes = max(
            1, content.metadata.word_count // 200
        )

    _content_store[content_id] = content
    return content


@router.delete("/{content_id}", response_model=APIResponse)
async def delete_content(content_id: str):
    """
    Delete content (soft delete - moves to archived).
    """
    if content_id not in _content_store:
        raise HTTPException(status_code=404, detail="Content not found")

    content = _content_store[content_id]
    content.status = ContentStatus.ARCHIVED
    content.updated_at = datetime.utcnow()

    return APIResponse(success=True, message="Content archived successfully")


@router.post("/{content_id}/publish", response_model=Content)
async def publish_content(content_id: str):
    """
    Publish content immediately.
    """
    if content_id not in _content_store:
        raise HTTPException(status_code=404, detail="Content not found")

    content = _content_store[content_id]

    if content.status not in [ContentStatus.APPROVED, ContentStatus.SCHEDULED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish content with status: {content.status}",
        )

    now = datetime.utcnow()
    content.status = ContentStatus.PUBLISHED
    content.published_at = now
    content.updated_at = now

    return content


@router.post("/{content_id}/schedule", response_model=Content)
async def schedule_content(content_id: str, scheduled_at: datetime):
    """
    Schedule content for future publication.
    """
    if content_id not in _content_store:
        raise HTTPException(status_code=404, detail="Content not found")

    content = _content_store[content_id]

    if scheduled_at <= datetime.utcnow():
        raise HTTPException(
            status_code=400, detail="Scheduled time must be in the future"
        )

    content.status = ContentStatus.SCHEDULED
    content.scheduled_at = scheduled_at
    content.updated_at = datetime.utcnow()

    return content


@router.post("/{content_id}/submit-for-review", response_model=Content)
async def submit_for_review(content_id: str):
    """
    Submit content for editorial review.
    """
    if content_id not in _content_store:
        raise HTTPException(status_code=404, detail="Content not found")

    content = _content_store[content_id]

    if content.status != ContentStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Can only submit drafts for review, current status: {content.status}",
        )

    content.status = ContentStatus.REVIEW
    content.updated_at = datetime.utcnow()

    return content


@router.post("/{content_id}/approve", response_model=Content)
async def approve_content(content_id: str):
    """
    Approve content after review.
    """
    if content_id not in _content_store:
        raise HTTPException(status_code=404, detail="Content not found")

    content = _content_store[content_id]

    if content.status != ContentStatus.REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Can only approve content in review, current status: {content.status}",
        )

    content.status = ContentStatus.APPROVED
    content.updated_at = datetime.utcnow()

    return content
