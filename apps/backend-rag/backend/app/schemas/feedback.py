"""
NUZANTARA PRIME - Feedback Module Schemas
Pydantic schemas for conversation ratings and review queue API
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RateConversationRequest(BaseModel):
    """Request model for rating a conversation"""

    session_id: UUID = Field(..., description="Session ID of the conversation (UUID)")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    feedback_text: str | None = Field(
        None, description="Optional feedback text describing the experience"
    )
    feedback_type: str | None = Field(
        None,
        description="Type of feedback: 'positive', 'negative', or 'issue'",
        pattern="^(positive|negative|issue)$",
    )
    correction_text: str | None = Field(
        None, description="Optional correction text if the AI response was incorrect"
    )


class FeedbackResponse(BaseModel):
    """Response model for rating submission"""

    success: bool = Field(..., description="Whether the feedback was saved successfully")
    review_queue_id: UUID | None = Field(
        None, description="ID of review_queue entry if created (for low ratings or corrections)"
    )
    message: str = Field(..., description="Human-readable message")


class ConversationRatingResponse(BaseModel):
    """Response model for retrieving a conversation rating"""

    id: UUID
    session_id: UUID
    user_id: UUID | None
    rating: int
    feedback_type: str | None
    feedback_text: str | None
    turn_count: int | None
    created_at: datetime


class ReviewQueueStatsResponse(BaseModel):
    """Response model for review queue statistics (Admin only)"""

    total_pending: int = Field(..., description="Total pending reviews")
    total_resolved: int = Field(..., description="Total resolved reviews")
    total_ignored: int = Field(..., description="Total ignored reviews")
    total_reviews: int = Field(..., description="Total reviews in queue")
    low_ratings_count: int = Field(..., description="Count of ratings <= 2")
    corrections_count: int = Field(..., description="Count of feedbacks with corrections")


