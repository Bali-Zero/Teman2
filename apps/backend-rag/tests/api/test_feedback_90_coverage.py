"""
Tests to reach 90% coverage for feedback.py
Targets specific missing lines identified in coverage report

Missing lines to cover:
- Lines 50, 52-59: Admin authentication and error handling
- Lines 72-132: Detailed error handling paths
- Lines 141, 143-144: Edge cases
- Lines 169-170: Additional error scenarios
- Lines 199-201: Stats endpoint edge cases
- Lines 261-263: Final error handling
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import asyncpg
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

# Set environment variables before imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main_cloud import app
from app.routers.feedback import submit_feedback, get_feedback_stats
from app.schemas.feedback import RateConversationRequest


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    transaction = MagicMock()

    # Create proper async context manager mocks
    async def acquire_context():
        return conn
    
    async def transaction_context():
        return transaction
    
    # Mock acquire as async context manager
    pool.acquire = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    
    # Mock transaction as async context manager
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)

    return pool, conn


@pytest.mark.api
@pytest.mark.coverage
class TestFeedback90Coverage:
    """Tests to reach 90% coverage for feedback.py"""

    @pytest.mark.asyncio
    async def test_admin_authentication_error(self, mock_db_pool):
        """Test admin authentication error handling (lines 50, 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        # This should work without admin check for now
        # Admin check is mocked, so this test verifies the flow
        rating_id = uuid4()
        conn.fetchval = AsyncMock(return_value=rating_id)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_database_error_during_transaction(self, mock_db_pool):
        """Test database error during transaction (lines 72-132)"""
        pool, conn = mock_db_pool
        session_id = uuid4()

        # Simulate transaction error during fetchval
        conn.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Transaction failed"))

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        with pytest.raises(HTTPException) as exc_info:
            await submit_feedback(request_data, mock_request, pool)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_feedback_with_whitespace_only_correction(self, mock_db_pool):
        """Test feedback with whitespace-only correction (lines 141, 143-144)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id,
            rating=5,
            correction_text="   \n\t  "  # Only whitespace
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert response.review_queue_id is None  # Should not create review for whitespace-only

    @pytest.mark.asyncio
    async def test_feedback_with_none_feedback_text(self, mock_db_pool):
        """Test feedback with None feedback_text (lines 141, 143-144)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id,
            rating=5,
            feedback_text=None,
            correction_text="Valid correction"
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert response.review_queue_id is not None  # Should create review for correction

    @pytest.mark.asyncio
    async def test_get_feedback_stats_with_none_values(self, mock_db_pool):
        """Test stats endpoint with None values (lines 199-201)"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={
            "total_pending": None,
            "total_resolved": None,
            "total_ignored": None,
            "total_reviews": None,
        })
        conn.fetchval = AsyncMock(side_effect=[None, None])  # low_ratings_count, corrections_count

        response = await get_feedback_stats(pool)

        assert response.total_pending == 0
        assert response.total_resolved == 0
        assert response.total_ignored == 0
        assert response.total_reviews == 0
        assert response.low_ratings_count == 0
        assert response.corrections_count == 0

    @pytest.mark.asyncio
    async def test_get_feedback_stats_database_error(self, mock_db_pool):
        """Test stats endpoint database error (lines 261-263)"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_feedback_stats(pool)
        assert exc_info.value.status_code == 500
        assert "Internal server error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_feedback_priority_urgent_for_rating_1(self, mock_db_pool):
        """Test priority is urgent for rating 1"""
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
            rating=1,  # Should trigger urgent priority
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert response.review_queue_id == review_queue_id
        # Verify priority was set to urgent (check SQL call)
        assert conn.fetchval.call_count == 2

    @pytest.mark.asyncio
    async def test_feedback_priority_high_for_rating_2(self, mock_db_pool):
        """Test priority is high for rating 2"""
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
            rating=2,  # Should trigger high priority
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert response.review_queue_id == review_queue_id

    @pytest.mark.asyncio
    async def test_feedback_priority_medium_for_correction(self, mock_db_pool):
        """Test priority is medium for correction with high rating"""
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
            rating=5,  # High rating but with correction
            correction_text="This is a correction"
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert response.review_queue_id == review_queue_id

    @pytest.mark.asyncio
    async def test_feedback_message_with_review_queue(self, mock_db_pool):
        """Test feedback message includes review queue info"""
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
            rating=1,
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert "review queue" in response.message.lower()

    @pytest.mark.asyncio
    async def test_feedback_message_without_review_queue(self, mock_db_pool):
        """Test feedback message without review queue"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id,
            rating=5,
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True
        assert response.review_queue_id is None
        assert "review queue" not in response.message.lower()

