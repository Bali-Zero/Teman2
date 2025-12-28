"""
Remaining Tests to Reach 90% Coverage for feedback.py
Targets remaining missing lines: 52-59, 63, 141, 169-170, 199-201
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import asyncpg
from fastapi import HTTPException, Request

# Set environment variables before imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.feedback import submit_feedback, get_feedback_stats, get_conversation_rating
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
class TestFeedbackRemainingCoverage:
    """Remaining tests to reach 90% coverage"""

    @pytest.mark.asyncio
    async def test_user_profile_not_dict(self, mock_db_pool):
        """Test user_profile not a dict (lines 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = "not a dict"  # Not a dict

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_profile_dict_no_id_keys(self, mock_db_pool):
        """Test user_profile dict without 'id' or 'user_id' keys (lines 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"email": "test@example.com"}  # No id keys

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_profile_dict_empty_id(self, mock_db_pool):
        """Test user_profile dict with empty id (lines 52-59)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"id": "", "user_id": ""}  # Empty strings

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_feedback_type_validation_positive(self, mock_db_pool):
        """Test feedback_type validation for 'positive' (line 63)"""
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
            feedback_type="positive"
        )

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_exception_handling_generic_exception(self, mock_db_pool):
        """Test generic exception handling (line 141)"""
        pool, conn = mock_db_pool
        session_id = uuid4()

        # Simulate generic exception
        conn.fetchval = AsyncMock(side_effect=Exception("Generic error"))

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        with pytest.raises(HTTPException) as exc_info:
            await submit_feedback(request_data, mock_request, pool)
        assert exc_info.value.status_code == 500
        assert "Internal server error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_conversation_rating_invalid_uuid(self, mock_db_pool):
        """Test get_conversation_rating with invalid UUID (lines 169-170)"""
        pool, conn = mock_db_pool

        with pytest.raises(HTTPException) as exc_info:
            await get_conversation_rating("not-a-uuid", pool)
        assert exc_info.value.status_code == 400
        assert "Invalid session_id format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_conversation_rating_exception_handling(self, mock_db_pool):
        """Test get_conversation_rating exception handling (lines 199-201)"""
        pool, conn = mock_db_pool
        session_id = uuid4()

        # Simulate exception
        conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_conversation_rating(str(session_id), pool)
        assert exc_info.value.status_code == 500
        assert "Internal server error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_feedback_stats_exception_handling(self, mock_db_pool):
        """Test get_feedback_stats exception handling"""
        pool, conn = mock_db_pool

        # Simulate exception
        conn.fetchrow = AsyncMock(side_effect=Exception("Generic error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_feedback_stats(pool)
        assert exc_info.value.status_code == 500
        assert "Internal server error" in exc_info.value.detail

