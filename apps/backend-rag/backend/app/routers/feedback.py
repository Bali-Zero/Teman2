"""
Feedback Router
Handles conversation ratings and feedback collection
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class RateConversationRequest(BaseModel):
    """Request model for rating a conversation"""

    session_id: str = Field(..., description="Session ID of the conversation")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    feedback_type: str | None = Field(
        None, description="Type of feedback: 'positive', 'negative', or 'issue'"
    )
    feedback_text: str | None = Field(None, description="Optional feedback text")
    turn_count: int | None = Field(None, description="Number of turns in conversation")


class RateConversationResponse(BaseModel):
    """Response model for rating a conversation"""

    success: bool
    message: str
    rating_id: str | None = None


@router.post("/rate-conversation", response_model=RateConversationResponse)
async def rate_conversation(
    request: RateConversationRequest,
    req: Request,
) -> RateConversationResponse:
    """
    Rate a conversation and save feedback

    This endpoint saves user ratings and feedback for conversations.
    High-rated conversations (rating >= 4) are used by ConversationTrainer agent
    to improve system prompts.

    Args:
        request: Rating request with session_id, rating, and optional feedback
        req: FastAPI request object (for accessing app.state)

    Returns:
        Success response with rating_id
    """
    try:
        # Get database pool from app.state
        db_pool: asyncpg.Pool | None = getattr(req.app.state, "db_pool", None)
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")

        # Get user_id from request state (set by auth middleware if authenticated)
        user_id: UUID | None = None
        if hasattr(req.state, "user_id"):
            user_id = req.state.user_id
        elif hasattr(req.state, "user_profile"):
            user_profile = req.state.user_profile
            if isinstance(user_profile, dict):
                user_id_str = user_profile.get("id") or user_profile.get("user_id")
                if user_id_str:
                    try:
                        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid user_id format: {user_id_str}")

        # Validate session_id format (should be UUID)
        try:
            session_uuid = UUID(request.session_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid session_id format: {request.session_id}"
            )

        # Validate feedback_type if provided
        if request.feedback_type and request.feedback_type not in ["positive", "negative", "issue"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid feedback_type: {request.feedback_type}. Must be 'positive', 'negative', or 'issue'",
            )

        # Insert rating into database
        async with db_pool.acquire() as conn:
            rating_id = await conn.fetchval(
                """
                INSERT INTO conversation_ratings (
                    session_id,
                    user_id,
                    rating,
                    feedback_type,
                    feedback_text,
                    turn_count
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id::text
                """,
                session_uuid,
                user_id,
                request.rating,
                request.feedback_type,
                request.feedback_text,
                request.turn_count,
            )

            logger.info(
                f"✅ Conversation rated: session_id={request.session_id}, "
                f"rating={request.rating}, rating_id={rating_id}"
            )

            return RateConversationResponse(
                success=True,
                message="Rating saved successfully",
                rating_id=rating_id,
            )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"Database error saving rating: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error saving rating: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/ratings/{session_id}")
async def get_conversation_rating(session_id: str, req: Request) -> dict[str, Any]:
    """
    Get rating for a specific conversation session

    Args:
        session_id: Session ID of the conversation
        req: FastAPI request object

    Returns:
        Rating data if found, 404 if not found
    """
    try:
        db_pool: asyncpg.Pool | None = getattr(req.app.state, "db_pool", None)
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")

        try:
            session_uuid = UUID(session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid session_id format: {session_id}")

        async with db_pool.acquire() as conn:
            rating = await conn.fetchrow(
                """
                SELECT
                    id::text as rating_id,
                    session_id::text,
                    rating,
                    feedback_type,
                    feedback_text,
                    turn_count,
                    created_at
                FROM conversation_ratings
                WHERE session_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                session_uuid,
            )

            if not rating:
                raise HTTPException(status_code=404, detail="Rating not found for this session")

            return {
                "success": True,
                "rating": dict(rating),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving rating: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

