"""
Comprehensive Tests for Oracle Universal Router - Updated for refactored module
Tests the API endpoints and Pydantic models
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

# ============================================================================
# PYDANTIC MODEL TESTS
# ============================================================================


class TestPydanticModels:
    """Test Pydantic model validation"""

    def test_conversation_message_model(self):
        """Test ConversationMessage model"""
        from backend.app.routers.oracle_universal import ConversationMessage

        msg = ConversationMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_oracle_query_request_defaults(self):
        """Test OracleQueryRequest with defaults"""
        from backend.app.routers.oracle_universal import OracleQueryRequest

        request = OracleQueryRequest(
            query="What is KITAS?",
            user_email="test@example.com",
        )
        assert request.query == "What is KITAS?"
        assert request.user_email == "test@example.com"
        assert request.use_ai is True
        assert request.include_sources is True

    def test_oracle_query_request_with_history(self):
        """Test OracleQueryRequest with conversation history"""
        from backend.app.routers.oracle_universal import ConversationMessage, OracleQueryRequest

        history = [
            ConversationMessage(role="user", content="Hi"),
            ConversationMessage(role="assistant", content="Hello!"),
        ]
        request = OracleQueryRequest(
            query="Follow up",
            user_email="test@example.com",
            conversation_history=history,
        )
        assert len(request.conversation_history) == 2

    def test_oracle_query_response_model(self):
        """Test OracleQueryResponse model"""
        from backend.app.routers.oracle_universal import OracleQueryResponse

        response = OracleQueryResponse(
            success=True,
            query="Test",
            answer="Response",
            execution_time_ms=100.5,
        )
        assert response.success is True
        assert response.execution_time_ms == 100.5

    def test_oracle_query_response_with_sources(self):
        """Test OracleQueryResponse with sources"""
        from backend.app.routers.oracle_universal import OracleQueryResponse

        response = OracleQueryResponse(
            success=True,
            query="Test",
            answer="Response",
            execution_time_ms=50.0,
            sources=[{"doc": "doc1.pdf"}, {"doc": "doc2.pdf"}],
            golden_answer_used=True,
        )
        assert len(response.sources) == 2
        assert response.golden_answer_used is True

    def test_feedback_request_model(self):
        """Test FeedbackRequest model"""
        from backend.app.routers.oracle_universal import FeedbackRequest

        feedback = FeedbackRequest(
            user_email="test@example.com",
            query_text="Test query",
            original_answer="Test answer",
            feedback_type="helpful",
            rating=5,
        )
        assert feedback.rating == 5
        assert feedback.feedback_type == "helpful"


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================


class TestHybridOracleQuery:
    """Test hybrid_oracle_query endpoint"""

    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test successful query"""
        from backend.app.routers.oracle_universal import OracleQueryRequest, hybrid_oracle_query

        request = OracleQueryRequest(
            query="What is KITAS?",
            user_email="test@example.com",
        )

        mock_service = Mock()
        mock_user = {"email": "test@example.com"}

        with patch("backend.app.routers.oracle_universal.oracle_service") as mock_oracle:
            mock_oracle.process_query = AsyncMock(
                return_value={
                    "success": True,
                    "query": "What is KITAS?",
                    "answer": "KITAS is a permit",
                    "execution_time_ms": 100.0,
                    "sources": [],
                }
            )

            result = await hybrid_oracle_query(request, mock_service, mock_user)
            assert result.success is True
            assert result.answer == "KITAS is a permit"

    @pytest.mark.asyncio
    async def test_query_error_handling(self):
        """Test query error handling"""
        from backend.app.routers.oracle_universal import OracleQueryRequest, hybrid_oracle_query

        request = OracleQueryRequest(
            query="Test error",
            user_email="test@example.com",
        )

        mock_service = Mock()
        mock_user = {"email": "test@example.com"}

        with patch("backend.app.routers.oracle_universal.oracle_service") as mock_oracle:
            mock_oracle.process_query = AsyncMock(side_effect=Exception("Test error"))

            result = await hybrid_oracle_query(request, mock_service, mock_user)
            assert result.success is False
            assert result.error is not None


class TestSubmitFeedback:
    """Test submit_user_feedback endpoint"""

    @pytest.mark.asyncio
    async def test_feedback_success(self):
        """Test successful feedback submission"""
        from backend.app.routers.oracle_universal import FeedbackRequest, submit_user_feedback

        feedback = FeedbackRequest(
            user_email="test@example.com",
            query_text="Test query",
            original_answer="Test answer",
            feedback_type="helpful",
            rating=5,
        )

        with patch("backend.app.routers.oracle_universal.oracle_service") as mock_oracle:
            mock_oracle.submit_feedback = AsyncMock(return_value=True)

            result = await submit_user_feedback(feedback)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_feedback_error(self):
        """Test feedback error handling"""
        from backend.app.routers.oracle_universal import FeedbackRequest, submit_user_feedback

        feedback = FeedbackRequest(
            user_email="test@example.com",
            query_text="Test query",
            original_answer="Test answer",
            feedback_type="helpful",
            rating=5,
        )

        with patch("backend.app.routers.oracle_universal.oracle_service") as mock_oracle:
            mock_oracle.submit_feedback = AsyncMock(side_effect=Exception("DB error"))

            result = await submit_user_feedback(feedback)
            assert result["success"] is False


class TestHealthCheck:
    """Test oracle_health_check endpoint"""

    @pytest.mark.asyncio
    async def test_health_returns_status(self):
        """Test health check returns status"""
        from backend.app.routers.oracle_universal import oracle_health_check

        result = await oracle_health_check()
        assert result["status"] == "active"
        assert "timestamp" in result


class TestDriveConnection:
    """Test test_drive_connection endpoint"""

    @pytest.mark.asyncio
    async def test_drive_returns_status(self):
        """Test drive connection returns status"""
        from backend.app.routers.oracle_universal import test_drive_connection

        result = await test_drive_connection()
        assert "status" in result


class TestGeminiIntegration:
    """Test test_gemini_integration endpoint"""

    @pytest.mark.asyncio
    async def test_gemini_returns_status(self):
        """Test Gemini integration returns status"""
        from backend.app.routers.oracle_universal import test_gemini_integration

        result = await test_gemini_integration()
        assert "status" in result


class TestUserProfile:
    """Test get_user_profile_endpoint"""

    @pytest.mark.asyncio
    async def test_profile_returns_status(self):
        """Test user profile returns status"""
        from backend.app.routers.oracle_universal import get_user_profile_endpoint

        result = await get_user_profile_endpoint("test@example.com")
        assert "status" in result
        assert result["email"] == "test@example.com"
