"""
Episodic Memory API Router
Endpoints for managing user timeline events and experiences
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_database_pool as get_db_pool
from app.routers.auth import get_current_user
from services.episodic_memory_service import Emotion, EpisodicMemoryService, EventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/episodic-memory", tags=["Episodic Memory"])


class AddEventRequest(BaseModel):
    """Request to add an event to user's timeline"""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: str = Field(
        default="general"
    )  # milestone, problem, resolution, decision, meeting, deadline
    emotion: str = Field(default="neutral")  # positive, negative, neutral, urgent, frustrated
    occurred_at: Optional[datetime] = None
    related_entities: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ExtractEventRequest(BaseModel):
    """Request to extract and save event from message"""

    message: str = Field(..., min_length=1)
    ai_response: Optional[str] = None


@router.post("/events")
async def add_event(
    request: AddEventRequest,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Add an event to the user's episodic memory timeline.

    Events track the user's journey through time:
    - Milestones achieved
    - Problems encountered
    - Resolutions found
    - Decisions made
    - Meetings held
    - Deadlines set
    """
    try:
        service = EpisodicMemoryService(pool=db_pool)

        # Parse event_type and emotion
        try:
            event_type = EventType(request.event_type)
        except ValueError:
            event_type = EventType.GENERAL

        try:
            emotion = Emotion(request.emotion)
        except ValueError:
            emotion = Emotion.NEUTRAL

        occurred_at = request.occurred_at or datetime.now(timezone.utc)

        result = await service.add_event(
            user_id=current_user["email"],
            title=request.title,
            description=request.description,
            event_type=event_type,
            emotion=emotion,
            occurred_at=occurred_at,
            related_entities=request.related_entities,
            metadata=request.metadata,
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        return {"success": True, "message": "Event added to timeline", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding episodic event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract")
async def extract_and_save_event(
    request: ExtractEventRequest,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Automatically extract an event from a message and save it.

    Looks for temporal references like:
    - "oggi", "today", "yesterday"
    - "N giorni fa", "days ago"
    - "last week", "settimana scorsa"
    - Specific dates: DD/MM, DD/MM/YYYY

    If no temporal reference is found, no event is created.
    """
    try:
        service = EpisodicMemoryService(pool=db_pool)

        result = await service.extract_and_save_event(
            user_id=current_user["email"],
            message=request.message,
            ai_response=request.ai_response,
        )

        if result is None:
            return {
                "success": True,
                "message": "No temporal reference found, no event created",
                "data": None,
            }

        return {"success": True, "message": "Event extracted and saved", "data": result}
    except Exception as e:
        logger.error(f"Error extracting episodic event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline")
async def get_timeline(
    event_type: Optional[str] = None,
    emotion: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Get the user's event timeline.

    Returns events in reverse chronological order (most recent first).
    Optional filters:
    - event_type: Filter by type (milestone, problem, etc.)
    - emotion: Filter by emotional context
    - start_date/end_date: Filter by date range
    - limit: Maximum number of events (default 20)
    """
    try:
        service = EpisodicMemoryService(pool=db_pool)

        events = await service.get_timeline(
            user_id=current_user["email"],
            event_type=event_type,
            emotion=emotion,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return {"success": True, "events": events, "count": len(events)}
    except Exception as e:
        logger.error(f"Error getting timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context")
async def get_context_summary(
    limit: int = 5,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Get a formatted context summary for AI prompts.

    Returns recent events formatted as markdown for inclusion
    in AI system prompts.
    """
    try:
        service = EpisodicMemoryService(pool=db_pool)

        summary = await service.get_context_summary(
            user_id=current_user["email"],
            limit=limit,
        )

        return {"success": True, "summary": summary, "has_events": bool(summary)}
    except Exception as e:
        logger.error(f"Error getting context summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Get user's episodic memory statistics.

    Returns counts by event type and overall stats.
    """
    try:
        service = EpisodicMemoryService(pool=db_pool)

        stats = await service.get_stats(user_id=current_user["email"])

        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Delete an event from the user's timeline.

    Users can only delete their own events.
    """
    try:
        service = EpisodicMemoryService(pool=db_pool)

        deleted = await service.delete_event(
            event_id=event_id,
            user_id=current_user["email"],
        )

        if not deleted:
            raise HTTPException(status_code=404, detail="Event not found or not owned by user")

        return {"success": True, "message": "Event deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event: {e}")
        raise HTTPException(status_code=500, detail=str(e))
