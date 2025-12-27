"""
Feedback Router - P1 Implementation
Handles conversation ratings, feedback collection, and review queue management
"""

import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_database_pool
from app.schemas.feedback import (
    ConversationRatingResponse,
    FeedbackResponse,
    RateConversationRequest,
    ReviewQueueStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/feedback", tags=["feedback"])


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    request: RateConversationRequest,
    req: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> FeedbackResponse:
    """
    Submit conversation rating and feedback

    CRITICAL LOGIC:
    - If rating <= 2 OR correction_text is NOT empty -> Creates entry in review_queue with status 'pending'
    - All feedback is saved to conversation_ratings table

    Args:
        request: Rating request with session_id, rating, and optional feedback/correction
        req: FastAPI request object (for accessing user info)
        db_pool: Database connection pool

    Returns:
        Success response with optional review_queue_id if created
    """
    try:
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

        # Validate feedback_type if provided
        if request.feedback_type and request.feedback_type not in ["positive", "negative", "issue"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid feedback_type: {request.feedback_type}. Must be 'positive', 'negative', or 'issue'",
            )

        # Insert rating into database
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Combine feedback_text and correction_text if both exist
                combined_feedback = request.feedback_text or ""
                if request.correction_text:
                    if combined_feedback:
                        combined_feedback = f"{combined_feedback}\n\n[Correction]: {request.correction_text}"
                    else:
                        combined_feedback = f"[Correction]: {request.correction_text}"

                # Insert into conversation_ratings
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
                    VALUES ($1, $2, $3, $4, $5, NULL)
                    RETURNING id
                    """,
                    request.session_id,
                    user_id,
                    request.rating,
                    request.feedback_type,
                    combined_feedback if combined_feedback else None,
                )

                logger.info(
                    f"✅ Conversation rated: session_id={request.session_id}, "
                    f"rating={request.rating}, rating_id={rating_id}"
                )

                # CRITICAL LOGIC: Create review_queue entry if rating <= 2 OR correction_text provided
                review_queue_id: UUID | None = None
                should_review = request.rating <= 2 or (request.correction_text and request.correction_text.strip())

                if should_review:
                    # Determine priority based on rating
                    priority = "urgent" if request.rating == 1 else "high" if request.rating == 2 else "medium"

                    review_queue_id = await conn.fetchval(
                        """
                        INSERT INTO review_queue (
                            source_feedback_id,
                            status,
                            priority
                        )
                        VALUES ($1, 'pending', $2)
                        RETURNING id
                        """,
                        rating_id,
                        priority,
                    )

                    logger.info(
                        f"📋 Review queue entry created: review_queue_id={review_queue_id}, "
                        f"rating={request.rating}, has_correction={bool(request.correction_text)}"
                    )

                return FeedbackResponse(
                    success=True,
                    review_queue_id=review_queue_id,
                    message="Feedback saved successfully" + (
                        " and added to review queue" if review_queue_id else ""
                    ),
                )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"Database error saving feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error saving feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


@router.get("/ratings/{session_id}", response_model=ConversationRatingResponse)
async def get_conversation_rating(
    session_id: str,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConversationRatingResponse:
    """
    Get rating for a specific conversation session

    Args:
        session_id: Session ID of the conversation (UUID)
        req: FastAPI request object
        db_pool: Database connection pool

    Returns:
        Rating data if found, 404 if not found
    """
    try:
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid session_id format: {session_id}")

        async with db_pool.acquire() as conn:
            rating = await conn.fetchrow(
                """
                SELECT
                    id,
                    session_id,
                    user_id,
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

            return ConversationRatingResponse(**dict(rating))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving rating: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


@router.get("/stats", response_model=ReviewQueueStatsResponse)
async def get_feedback_stats(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ReviewQueueStatsResponse:
    """
    Get feedback statistics (Admin only - mock for now)

    Returns:
        Statistics about review queue and feedback
    """
    try:
        # TODO: Add admin authentication check
        # For now, this is a mock endpoint

        async with db_pool.acquire() as conn:
            # Get review queue stats
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') as total_pending,
                    COUNT(*) FILTER (WHERE status = 'resolved') as total_resolved,
                    COUNT(*) FILTER (WHERE status = 'ignored') as total_ignored,
                    COUNT(*) as total_reviews
                FROM review_queue
                """
            )

            # Get low ratings count (ratings <= 2)
            low_ratings = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM conversation_ratings
                WHERE rating <= 2
                """
            )

            # Get corrections count (feedbacks with correction_text)
            # Note: We don't have correction_text column in conversation_ratings yet
            # This is a placeholder for future implementation
            corrections_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM review_queue rq
                JOIN conversation_ratings cr ON rq.source_feedback_id = cr.id
                WHERE cr.feedback_text IS NOT NULL AND cr.feedback_text != ''
                """
            )

            return ReviewQueueStatsResponse(
                total_pending=stats["total_pending"] or 0,
                total_resolved=stats["total_resolved"] or 0,
                total_ignored=stats["total_ignored"] or 0,
                total_reviews=stats["total_reviews"] or 0,
                low_ratings_count=low_ratings or 0,
                corrections_count=corrections_count or 0,
            )

    except Exception as e:
        logger.error(f"Error retrieving feedback stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e
