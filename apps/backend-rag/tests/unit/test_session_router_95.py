"""
Unit Tests for Session Router - 95% Coverage Target
Tests all endpoints in backend/app/routers/session.py directly
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["REDIS_URL"] = "redis://localhost:6379"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test get_session_service dependency
# ============================================================================


class TestGetSessionService:
    """Test suite for get_session_service dependency"""

    def test_get_session_service_creates_new_instance(self):
        """Test that get_session_service creates a new instance when none exists"""
        import app.routers.session as session_module

        # Reset global service
        session_module._session_service = None

        with patch("app.routers.session.SessionService") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result = session_module.get_session_service()

            mock_cls.assert_called_once()
            assert result == mock_instance

    def test_get_session_service_returns_existing_instance(self):
        """Test that get_session_service returns existing instance"""
        import app.routers.session as session_module

        mock_existing = MagicMock()
        session_module._session_service = mock_existing

        result = session_module.get_session_service()

        assert result == mock_existing

        # Cleanup
        session_module._session_service = None


# ============================================================================
# Test Create Session Endpoint
# ============================================================================


class TestCreateSession:
    """Test suite for POST /api/sessions/create"""

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test successful session creation"""
        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(return_value="session_123")

        from app.routers.session import create_session

        result = await create_session(service=mock_service)

        assert result["success"] is True
        assert result["session_id"] == "session_123"
        mock_service.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_error(self):
        """Test session creation error handling"""
        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(side_effect=Exception("Redis connection error"))

        from fastapi import HTTPException

        from app.routers.session import create_session

        with pytest.raises(HTTPException) as exc_info:
            await create_session(service=mock_service)

        assert exc_info.value.status_code == 500
        assert "Redis connection error" in str(exc_info.value.detail)


# ============================================================================
# Test Get Session Endpoint
# ============================================================================


class TestGetSession:
    """Test suite for GET /api/sessions/{session_id}"""

    @pytest.mark.asyncio
    async def test_get_session_success(self):
        """Test successful session retrieval"""
        mock_service = MagicMock()
        mock_service.get_history = AsyncMock(
            return_value=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]
        )

        from app.routers.session import get_session

        result = await get_session(session_id="session_123", service=mock_service)

        assert result["success"] is True
        assert result["session_id"] == "session_123"
        assert len(result["history"]) == 2

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test session not found"""
        mock_service = MagicMock()
        mock_service.get_history = AsyncMock(return_value=None)

        from fastapi import HTTPException

        from app.routers.session import get_session

        with pytest.raises(HTTPException) as exc_info:
            await get_session(session_id="nonexistent", service=mock_service)

        assert exc_info.value.status_code == 404
        assert "Session not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_session_error(self):
        """Test session retrieval error"""
        mock_service = MagicMock()
        mock_service.get_history = AsyncMock(side_effect=Exception("Database error"))

        from fastapi import HTTPException

        from app.routers.session import get_session

        with pytest.raises(HTTPException) as exc_info:
            await get_session(session_id="session_123", service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Update Session Endpoint
# ============================================================================


class TestUpdateSession:
    """Test suite for PUT /api/sessions/{session_id}"""

    @pytest.mark.asyncio
    async def test_update_session_success(self):
        """Test successful session update"""
        mock_service = MagicMock()
        mock_service.update_history = AsyncMock(return_value=True)

        from app.routers.session import SessionHistoryRequest, update_session

        request = SessionHistoryRequest(history=[{"role": "user", "content": "Test"}])
        result = await update_session(
            session_id="session_123", request=request, service=mock_service
        )

        assert result["success"] is True
        assert result["session_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_update_session_failed(self):
        """Test session update failure"""
        mock_service = MagicMock()
        mock_service.update_history = AsyncMock(return_value=False)

        from fastapi import HTTPException

        from app.routers.session import SessionHistoryRequest, update_session

        request = SessionHistoryRequest(history=[])

        with pytest.raises(HTTPException) as exc_info:
            await update_session(session_id="session_123", request=request, service=mock_service)

        assert exc_info.value.status_code == 400
        assert "Failed to update session" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_session_error(self):
        """Test session update error handling"""
        mock_service = MagicMock()
        mock_service.update_history = AsyncMock(side_effect=Exception("Update error"))

        from fastapi import HTTPException

        from app.routers.session import SessionHistoryRequest, update_session

        request = SessionHistoryRequest(history=[])

        with pytest.raises(HTTPException) as exc_info:
            await update_session(session_id="session_123", request=request, service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Update Session with TTL Endpoint
# ============================================================================


class TestUpdateSessionWithTTL:
    """Test suite for PUT /api/sessions/{session_id}/ttl"""

    @pytest.mark.asyncio
    async def test_update_session_with_ttl_success(self):
        """Test successful session update with TTL"""
        mock_service = MagicMock()
        mock_service.update_history_with_ttl = AsyncMock(return_value=True)

        from app.routers.session import SessionUpdateRequest, update_session_with_ttl

        request = SessionUpdateRequest(history=[{"role": "user", "content": "Test"}], ttl_hours=24)
        result = await update_session_with_ttl(
            session_id="session_123", request=request, service=mock_service
        )

        assert result["success"] is True
        mock_service.update_history_with_ttl.assert_called_once_with(
            "session_123", request.history, 24
        )

    @pytest.mark.asyncio
    async def test_update_session_with_ttl_failed(self):
        """Test session update with TTL failure"""
        mock_service = MagicMock()
        mock_service.update_history_with_ttl = AsyncMock(return_value=False)

        from fastapi import HTTPException

        from app.routers.session import SessionUpdateRequest, update_session_with_ttl

        request = SessionUpdateRequest(history=[], ttl_hours=12)

        with pytest.raises(HTTPException) as exc_info:
            await update_session_with_ttl(
                session_id="session_123", request=request, service=mock_service
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_session_with_ttl_error(self):
        """Test session update with TTL error handling"""
        mock_service = MagicMock()
        mock_service.update_history_with_ttl = AsyncMock(side_effect=Exception("TTL error"))

        from fastapi import HTTPException

        from app.routers.session import SessionUpdateRequest, update_session_with_ttl

        request = SessionUpdateRequest(history=[])

        with pytest.raises(HTTPException) as exc_info:
            await update_session_with_ttl(
                session_id="session_123", request=request, service=mock_service
            )

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Delete Session Endpoint
# ============================================================================


class TestDeleteSession:
    """Test suite for DELETE /api/sessions/{session_id}"""

    @pytest.mark.asyncio
    async def test_delete_session_success(self):
        """Test successful session deletion"""
        mock_service = MagicMock()
        mock_service.delete_session = AsyncMock(return_value=True)

        from app.routers.session import delete_session

        result = await delete_session(session_id="session_123", service=mock_service)

        assert result["success"] is True
        assert result["session_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self):
        """Test deleting non-existent session"""
        mock_service = MagicMock()
        mock_service.delete_session = AsyncMock(return_value=False)

        from app.routers.session import delete_session

        result = await delete_session(session_id="nonexistent", service=mock_service)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_session_error(self):
        """Test session deletion error handling"""
        mock_service = MagicMock()
        mock_service.delete_session = AsyncMock(side_effect=Exception("Delete error"))

        from fastapi import HTTPException

        from app.routers.session import delete_session

        with pytest.raises(HTTPException) as exc_info:
            await delete_session(session_id="session_123", service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Extend Session TTL Endpoint
# ============================================================================


class TestExtendSessionTTL:
    """Test suite for POST /api/sessions/{session_id}/extend"""

    @pytest.mark.asyncio
    async def test_extend_session_ttl_success(self):
        """Test successful TTL extension"""
        mock_service = MagicMock()
        mock_service.extend_ttl = AsyncMock(return_value=True)

        from app.routers.session import extend_session_ttl

        result = await extend_session_ttl(session_id="session_123", service=mock_service)

        assert result["success"] is True
        assert result["session_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_extend_session_ttl_error(self):
        """Test TTL extension error handling"""
        mock_service = MagicMock()
        mock_service.extend_ttl = AsyncMock(side_effect=Exception("Extend error"))

        from fastapi import HTTPException

        from app.routers.session import extend_session_ttl

        with pytest.raises(HTTPException) as exc_info:
            await extend_session_ttl(session_id="session_123", service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Extend Session TTL Custom Endpoint
# ============================================================================


class TestExtendSessionTTLCustom:
    """Test suite for POST /api/sessions/{session_id}/extend-custom"""

    @pytest.mark.asyncio
    async def test_extend_session_ttl_custom_success(self):
        """Test successful custom TTL extension"""
        mock_service = MagicMock()
        mock_service.extend_ttl_custom = AsyncMock(return_value=True)

        from app.routers.session import SessionTTLRequest, extend_session_ttl_custom

        request = SessionTTLRequest(ttl_hours=48)
        result = await extend_session_ttl_custom(
            session_id="session_123", request=request, service=mock_service
        )

        assert result["success"] is True
        mock_service.extend_ttl_custom.assert_called_once_with("session_123", 48)

    @pytest.mark.asyncio
    async def test_extend_session_ttl_custom_error(self):
        """Test custom TTL extension error handling"""
        mock_service = MagicMock()
        mock_service.extend_ttl_custom = AsyncMock(side_effect=Exception("Custom TTL error"))

        from fastapi import HTTPException

        from app.routers.session import SessionTTLRequest, extend_session_ttl_custom

        request = SessionTTLRequest(ttl_hours=24)

        with pytest.raises(HTTPException) as exc_info:
            await extend_session_ttl_custom(
                session_id="session_123", request=request, service=mock_service
            )

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Get Session Info Endpoint
# ============================================================================


class TestGetSessionInfo:
    """Test suite for GET /api/sessions/{session_id}/info"""

    @pytest.mark.asyncio
    async def test_get_session_info_success(self):
        """Test successful session info retrieval"""
        mock_service = MagicMock()
        mock_service.get_session_info = AsyncMock(
            return_value={"created_at": "2024-01-01", "message_count": 10, "ttl_remaining": 3600}
        )

        from app.routers.session import get_session_info

        result = await get_session_info(session_id="session_123", service=mock_service)

        assert result["success"] is True
        assert result["info"]["message_count"] == 10

    @pytest.mark.asyncio
    async def test_get_session_info_not_found(self):
        """Test session info not found"""
        mock_service = MagicMock()
        mock_service.get_session_info = AsyncMock(return_value=None)

        from fastapi import HTTPException

        from app.routers.session import get_session_info

        with pytest.raises(HTTPException) as exc_info:
            await get_session_info(session_id="nonexistent", service=mock_service)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_session_info_error(self):
        """Test session info retrieval error"""
        mock_service = MagicMock()
        mock_service.get_session_info = AsyncMock(side_effect=Exception("Info error"))

        from fastapi import HTTPException

        from app.routers.session import get_session_info

        with pytest.raises(HTTPException) as exc_info:
            await get_session_info(session_id="session_123", service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Export Session Endpoint
# ============================================================================


class TestExportSession:
    """Test suite for GET /api/sessions/{session_id}/export"""

    @pytest.mark.asyncio
    async def test_export_session_json_success(self):
        """Test successful session export as JSON"""
        mock_service = MagicMock()
        mock_service.export_session = AsyncMock(return_value='{"messages": []}')

        from app.routers.session import export_session

        result = await export_session(session_id="session_123", format="json", service=mock_service)

        assert result["success"] is True
        assert result["format"] == "json"
        assert result["data"] == '{"messages": []}'

    @pytest.mark.asyncio
    async def test_export_session_markdown_success(self):
        """Test successful session export as markdown"""
        mock_service = MagicMock()
        mock_service.export_session = AsyncMock(return_value="# Session\n**User**: Hello")

        from app.routers.session import export_session

        result = await export_session(
            session_id="session_123", format="markdown", service=mock_service
        )

        assert result["success"] is True
        assert result["format"] == "markdown"

    @pytest.mark.asyncio
    async def test_export_session_not_found(self):
        """Test export session not found"""
        mock_service = MagicMock()
        mock_service.export_session = AsyncMock(return_value=None)

        from fastapi import HTTPException

        from app.routers.session import export_session

        with pytest.raises(HTTPException) as exc_info:
            await export_session(session_id="nonexistent", service=mock_service)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_export_session_error(self):
        """Test export session error handling"""
        mock_service = MagicMock()
        mock_service.export_session = AsyncMock(side_effect=Exception("Export error"))

        from fastapi import HTTPException

        from app.routers.session import export_session

        with pytest.raises(HTTPException) as exc_info:
            await export_session(session_id="session_123", service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Get Analytics Endpoint
# ============================================================================


class TestGetAnalytics:
    """Test suite for GET /api/sessions/analytics/overview"""

    @pytest.mark.asyncio
    async def test_get_analytics_success(self):
        """Test successful analytics retrieval"""
        mock_service = MagicMock()
        mock_service.get_analytics = AsyncMock(
            return_value={"total_sessions": 100, "active_sessions": 25, "avg_messages": 10.5}
        )

        from app.routers.session import get_analytics

        result = await get_analytics(service=mock_service)

        assert result["success"] is True
        assert result["analytics"]["total_sessions"] == 100

    @pytest.mark.asyncio
    async def test_get_analytics_error(self):
        """Test analytics retrieval error handling"""
        mock_service = MagicMock()
        mock_service.get_analytics = AsyncMock(side_effect=Exception("Analytics error"))

        from fastapi import HTTPException

        from app.routers.session import get_analytics

        with pytest.raises(HTTPException) as exc_info:
            await get_analytics(service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Cleanup Sessions Endpoint
# ============================================================================


class TestCleanupSessions:
    """Test suite for POST /api/sessions/cleanup"""

    @pytest.mark.asyncio
    async def test_cleanup_sessions_success(self):
        """Test successful session cleanup"""
        mock_service = MagicMock()
        mock_service.cleanup_expired_sessions = AsyncMock(return_value=5)

        from app.routers.session import cleanup_sessions

        result = await cleanup_sessions(service=mock_service)

        assert result["success"] is True
        assert result["cleaned"] == 5

    @pytest.mark.asyncio
    async def test_cleanup_sessions_zero(self):
        """Test cleanup with no expired sessions"""
        mock_service = MagicMock()
        mock_service.cleanup_expired_sessions = AsyncMock(return_value=0)

        from app.routers.session import cleanup_sessions

        result = await cleanup_sessions(service=mock_service)

        assert result["success"] is True
        assert result["cleaned"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_sessions_error(self):
        """Test cleanup error handling"""
        mock_service = MagicMock()
        mock_service.cleanup_expired_sessions = AsyncMock(side_effect=Exception("Cleanup error"))

        from fastapi import HTTPException

        from app.routers.session import cleanup_sessions

        with pytest.raises(HTTPException) as exc_info:
            await cleanup_sessions(service=mock_service)

        assert exc_info.value.status_code == 500


# ============================================================================
# Test Health Check Endpoint
# ============================================================================


class TestHealthCheck:
    """Test suite for GET /api/sessions/health"""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test healthy service"""
        mock_service = MagicMock()
        mock_service.health_check = AsyncMock(return_value=True)

        from app.routers.session import health_check

        result = await health_check(service=mock_service)

        assert result["success"] is True
        assert result["service"] == "session"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """Test unhealthy service"""
        mock_service = MagicMock()
        mock_service.health_check = AsyncMock(return_value=False)

        from app.routers.session import health_check

        result = await health_check(service=mock_service)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        """Test health check error - returns error response instead of raising"""
        mock_service = MagicMock()
        mock_service.health_check = AsyncMock(side_effect=Exception("Health check failed"))

        from app.routers.session import health_check

        result = await health_check(service=mock_service)

        assert result["success"] is False
        assert result["service"] == "session"
        assert "Health check failed" in result["error"]


# ============================================================================
# Test Router Configuration
# ============================================================================


class TestRouterConfiguration:
    """Test router prefix and tags configuration"""

    def test_router_prefix(self):
        """Test that router has correct prefix"""
        from app.routers.session import router

        assert router.prefix == "/api/sessions"

    def test_router_tags(self):
        """Test that router has correct tags"""
        from app.routers.session import router

        assert "sessions" in router.tags


# ============================================================================
# Test Pydantic Models
# ============================================================================


class TestPydanticModels:
    """Test Pydantic request models"""

    def test_session_history_request(self):
        """Test SessionHistoryRequest model"""
        from app.routers.session import SessionHistoryRequest

        request = SessionHistoryRequest(history=[{"role": "user", "content": "Hello"}])
        assert len(request.history) == 1
        assert request.history[0]["role"] == "user"

    def test_session_update_request(self):
        """Test SessionUpdateRequest model"""
        from app.routers.session import SessionUpdateRequest

        request = SessionUpdateRequest(history=[], ttl_hours=24)
        assert request.ttl_hours == 24

    def test_session_update_request_optional_ttl(self):
        """Test SessionUpdateRequest with optional TTL"""
        from app.routers.session import SessionUpdateRequest

        request = SessionUpdateRequest(history=[])
        assert request.ttl_hours is None

    def test_session_ttl_request(self):
        """Test SessionTTLRequest model"""
        from app.routers.session import SessionTTLRequest

        request = SessionTTLRequest(ttl_hours=48)
        assert request.ttl_hours == 48
