"""
Exact Coverage Tests for feedback.py - Target specific missing lines
These tests are designed to hit exact lines that are not covered
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

from app.routers.feedback import submit_feedback
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
class TestFeedbackExactCoverage:
    """Tests to hit exact missing lines"""

    @pytest.mark.asyncio
    async def test_user_id_extraction_from_user_id_exact_line_50(self, mock_db_pool):
        """Test user_id extraction from req.state.user_id (line 50)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        user_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = user_id  # Set user_id directly (line 50)
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_id_extraction_from_profile_dict_id_exact_line_54(self, mock_db_pool):
        """Test user_id extraction from user_profile dict with 'id' key (line 54)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        user_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"id": str(user_id)}  # Use 'id' key (line 54)

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_id_extraction_from_profile_dict_user_id_exact_line_54(self, mock_db_pool):
        """Test user_id extraction from user_profile dict with 'user_id' key (line 54)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        user_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"user_id": str(user_id)}  # Use 'user_id' key (line 54)

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_id_extraction_valueerror_exact_line_58(self, mock_db_pool):
        """Test user_id extraction ValueError handling (line 58)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"id": "not-a-valid-uuid"}  # Invalid UUID (line 58)

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        # Should handle ValueError gracefully (line 58)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_user_id_extraction_typeerror_exact_line_58(self, mock_db_pool):
        """Test user_id extraction TypeError handling (line 58)"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = {"id": 12345}  # Not a string (line 58)

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        response = await submit_feedback(request_data, mock_request, pool)

        # Should handle TypeError gracefully (line 58)
        assert response.success is True

    @pytest.mark.asyncio
    async def test_feedback_type_validation_invalid_exact_line_63(self, mock_db_pool):
        """Test feedback_type validation with invalid type (line 63)"""
        pool, conn = mock_db_pool
        session_id = uuid4()

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(
            session_id=session_id,
            rating=5,
            feedback_type="invalid_type"  # Invalid type (line 63)
        )

        with pytest.raises(HTTPException) as exc_info:
            await submit_feedback(request_data, mock_request, pool)
        assert exc_info.value.status_code == 400
        assert "Invalid feedback_type" in exc_info.value.detail or "feedback_type" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_exception_handling_generic_exact_line_141(self, mock_db_pool):
        """Test generic exception handling (line 141)"""
        pool, conn = mock_db_pool
        session_id = uuid4()

        # Simulate generic exception (not HTTPException, not asyncpg.PostgresError)
        conn.fetchval = AsyncMock(side_effect=RuntimeError("Generic runtime error"))

        mock_request = MagicMock(spec=Request)
        mock_request.state.user_id = None
        mock_request.state.user_profile = None

        request_data = RateConversationRequest(session_id=session_id, rating=5)

        with pytest.raises(HTTPException) as exc_info:
            await submit_feedback(request_data, mock_request, pool)
        assert exc_info.value.status_code == 500
        assert "Internal server error" in exc_info.value.detail

