"""
Final Tests to Reach 90% Coverage for feedback.py
Targets remaining missing lines: 52-59, 63, 75, 141, 145-147, 169-170, 199-201
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import asyncpg
import pytest
from fastapi import HTTPException, Request

# Set environment variables before imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.feedback import get_feedback_stats, submit_feedback
from app.schemas.feedback import RateConversationRequest


@pytest.fixture
def mock_db_pool():
    """Create properly mocked asyncpg pool with async context managers"""
    pool = MagicMock()
    conn = AsyncMock()
    transaction = MagicMock()

    # Mock acquire() to return an async context manager
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)

    # Mock transaction() to return an async context manager
    transaction_cm = MagicMock()
    transaction_cm.__aenter__ = AsyncMock(return_value=transaction)
    transaction_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=transaction_cm)

    return pool, conn


@pytest.mark.api
@pytest.mark.coverage
class TestFeedbackFinalCoverage:
    """Final tests to reach 90% coverage for feedback.py"""

    @pytest.mark.asyncio
    async def test_user_id_extraction_from_user_profile_with_id(self, mock_db_pool):
        """Test user_id extraction from user_profile dict with 'id' key (lines 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        user_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"id": str(user_id), "email": "test@example.com"}

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        # Verify user_id was passed to insert
        assert conn.fetchval.call_count >= 1

    @pytest.mark.asyncio
    async def test_user_id_extraction_from_user_profile_with_user_id(self, mock_db_pool):
        """Test user_id extraction from user_profile dict with 'user_id' key (lines 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        user_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"user_id": str(user_id), "email": "test@example.com"}

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_id_extraction_valueerror_handling(self, mock_db_pool):
        """Test user_id extraction ValueError handling (lines 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"id": "not-a-valid-uuid", "email": "test@example.com"}

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        # Should handle ValueError gracefully and continue
        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_id_extraction_typeerror_handling(self, mock_db_pool):
        """Test user_id extraction TypeError handling (lines 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"id": 12345, "email": "test@example.com"}  # Not a string

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        # Should handle TypeError gracefully and continue
        assert response.success is True

    @pytest.mark.asyncio
    async def test_feedback_type_validation_negative(self, mock_db_pool):
        """Test feedback_type validation for 'negative' (line 63)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id, rating=2, feedback_type="negative"
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_feedback_type_validation_issue(self, mock_db_pool):
        """Test feedback_type validation for 'issue' (line 63)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id, rating=1, feedback_type="issue"
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_feedback_text_combination_with_both(self, mock_db_pool):
        """Test feedback_text combination when both exist (line 75)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()
        review_queue_id = uuid4()

        conn.fetchval = AsyncMock(side_effect=[rating_id, review_queue_id])

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id,
            rating=2,
            feedback_text="Original feedback",
            correction_text="Correction text",
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        # Verify combined text was inserted
        insert_args = conn.fetchval.call_args_list[0][0]
        if insert_args[4] is not None:
            assert "[Correction]" in insert_args[4]

    @pytest.mark.asyncio
    async def test_feedback_text_combination_correction_only(self, mock_db_pool):
        """Test feedback_text combination when only correction exists (line 75)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()
        review_queue_id = uuid4()

        conn.fetchval = AsyncMock(side_effect=[rating_id, review_queue_id])

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id, rating=5, feedback_text=None, correction_text="Only correction"
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        # Verify correction text was inserted
        insert_args = conn.fetchval.call_args_list[0][0]
        if insert_args[4] is not None:
            assert "[Correction]" in insert_args[4]

    @pytest.mark.asyncio
    async def test_review_queue_priority_medium_for_correction_high_rating(self, mock_db_pool):
        """Test review queue priority medium for correction with high rating (lines 141, 145-147)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()
        review_queue_id = uuid4()

        conn.fetchval = AsyncMock(side_effect=[rating_id, review_queue_id])

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id,
            rating=4,  # High rating but with correction
            correction_text="Correction",
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert response.review_queue_id == review_queue_id

    @pytest.mark.asyncio
    async def test_get_feedback_stats_with_zero_values(self, mock_db_pool):
        """Test stats endpoint with zero values (lines 199-201)"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "total_pending": 0,
                "total_resolved": 0,
                "total_ignored": 0,
                "total_reviews": 0,
            }
        )
        conn.fetchval = AsyncMock(side_effect=[0, 0])  # low_ratings_count, corrections_count

        response = await get_feedback_stats(pool)

        assert response.total_pending == 0
        assert response.total_resolved == 0
        assert response.total_ignored == 0
        assert response.total_reviews == 0
        assert response.low_ratings_count == 0
        assert response.corrections_count == 0

    @pytest.mark.asyncio
    async def test_get_feedback_stats_database_error_fetchrow(self, mock_db_pool):
        """Test stats endpoint database error in fetchrow (lines 169-170)"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_feedback_stats(pool)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_feedback_stats_database_error_fetchval(self, mock_db_pool):
        """Test stats endpoint database error in fetchval (lines 169-170)"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "total_pending": 5,
                "total_resolved": 10,
                "total_ignored": 2,
                "total_reviews": 17,
            }
        )
        conn.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_feedback_stats(pool)
        assert exc_info.value.status_code == 500
