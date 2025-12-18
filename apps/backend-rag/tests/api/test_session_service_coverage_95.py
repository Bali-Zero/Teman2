"""
API Tests for Session Service Router - Coverage 95% Target
Tests all SessionService endpoints and edge cases to achieve 95% coverage

Coverage:
- POST /api/sessions/create - Create session
- GET /api/sessions/{session_id} - Get session history
- PUT /api/sessions/{session_id} - Update session
- PUT /api/sessions/{session_id}/ttl - Update with custom TTL
- DELETE /api/sessions/{session_id} - Delete session
- POST /api/sessions/{session_id}/extend - Extend TTL
- POST /api/sessions/{session_id}/extend-custom - Extend TTL custom
- GET /api/sessions/{session_id}/info - Get session info
- GET /api/sessions/{session_id}/export - Export session
- GET /api/sessions/analytics/overview - Get analytics
- POST /api/sessions/cleanup - Cleanup sessions
- GET /api/sessions/health - Health check
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
# Test Create Session
# ============================================================================


class TestCreateSession:
    """Test suite for POST /api/sessions/create"""

    def test_create_session_success(self, authenticated_client):
        """Test successful session creation"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_session = AsyncMock(return_value="session-123")
            mock_get.return_value = mock_service

            response = authenticated_client.post("/api/sessions/create")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "session_id" in data
            assert data["session_id"] == "session-123"

    def test_create_session_error(self, authenticated_client):
        """Test session creation error"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_session = AsyncMock(side_effect=Exception("Redis error"))
            mock_get.return_value = mock_service

            response = authenticated_client.post("/api/sessions/create")

            assert response.status_code == 500


# ============================================================================
# Test Get Session
# ============================================================================


class TestGetSession:
    """Test suite for GET /api/sessions/{session_id}"""

    def test_get_session_success(self, authenticated_client):
        """Test successful session retrieval"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_history = AsyncMock(
                return_value=[{"role": "user", "content": "Hello"}]
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/session-123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "history" in data
            assert len(data["history"]) == 1

    def test_get_session_not_found(self, authenticated_client):
        """Test session not found"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_history = AsyncMock(return_value=None)
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/nonexistent")

            assert response.status_code == 404


# ============================================================================
# Test Update Session
# ============================================================================


class TestUpdateSession:
    """Test suite for PUT /api/sessions/{session_id}"""

    def test_update_session_success(self, authenticated_client):
        """Test successful session update"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_history = AsyncMock(return_value=True)
            mock_get.return_value = mock_service

            update_data = {"history": [{"role": "user", "content": "Updated"}]}

            response = authenticated_client.put("/api/sessions/session-123", json=update_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_update_session_failure(self, authenticated_client):
        """Test session update failure"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_history = AsyncMock(return_value=False)
            mock_get.return_value = mock_service

            update_data = {"history": [{"role": "user", "content": "Test"}]}

            response = authenticated_client.put("/api/sessions/session-123", json=update_data)

            assert response.status_code == 400


# ============================================================================
# Test Update Session with TTL
# ============================================================================


class TestUpdateSessionWithTTL:
    """Test suite for PUT /api/sessions/{session_id}/ttl"""

    def test_update_session_with_ttl_success(self, authenticated_client):
        """Test successful session update with custom TTL"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_history_with_ttl = AsyncMock(return_value=True)
            mock_get.return_value = mock_service

            update_data = {"history": [{"role": "user", "content": "Test"}], "ttl_hours": 48}

            response = authenticated_client.put("/api/sessions/session-123/ttl", json=update_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_update_session_with_ttl_no_custom(self, authenticated_client):
        """Test session update with default TTL"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_history_with_ttl = AsyncMock(return_value=True)
            mock_get.return_value = mock_service

            update_data = {"history": [{"role": "user", "content": "Test"}]}

            response = authenticated_client.put("/api/sessions/session-123/ttl", json=update_data)

            assert response.status_code == 200


# ============================================================================
# Test Delete Session
# ============================================================================


class TestDeleteSession:
    """Test suite for DELETE /api/sessions/{session_id}"""

    def test_delete_session_success(self, authenticated_client):
        """Test successful session deletion"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.delete_session = AsyncMock(return_value=True)
            mock_get.return_value = mock_service

            response = authenticated_client.delete("/api/sessions/session-123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_delete_session_not_found(self, authenticated_client):
        """Test deleting non-existent session"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.delete_session = AsyncMock(return_value=False)
            mock_get.return_value = mock_service

            response = authenticated_client.delete("/api/sessions/nonexistent")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False


# ============================================================================
# Test Extend TTL
# ============================================================================


class TestExtendTTL:
    """Test suite for POST /api/sessions/{session_id}/extend"""

    def test_extend_ttl_success(self, authenticated_client):
        """Test successful TTL extension"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.extend_ttl = AsyncMock(return_value=True)
            mock_get.return_value = mock_service

            response = authenticated_client.post("/api/sessions/session-123/extend")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_extend_ttl_custom_success(self, authenticated_client):
        """Test successful custom TTL extension"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.extend_ttl_custom = AsyncMock(return_value=True)
            mock_get.return_value = mock_service

            extend_data = {"ttl_hours": 48}

            response = authenticated_client.post(
                "/api/sessions/session-123/extend-custom", json=extend_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# Test Get Session Info
# ============================================================================


class TestGetSessionInfo:
    """Test suite for GET /api/sessions/{session_id}/info"""

    def test_get_session_info_success(self, authenticated_client):
        """Test successful session info retrieval"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_session_info = AsyncMock(
                return_value={
                    "session_id": "session-123",
                    "message_count": 5,
                    "ttl_seconds": 86400,
                    "ttl_hours": 24.0,
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/session-123/info")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "info" in data
            assert data["info"]["message_count"] == 5

    def test_get_session_info_not_found(self, authenticated_client):
        """Test session info not found"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_session_info = AsyncMock(return_value=None)
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/nonexistent/info")

            assert response.status_code == 404


# ============================================================================
# Test Export Session
# ============================================================================


class TestExportSession:
    """Test suite for GET /api/sessions/{session_id}/export"""

    def test_export_session_json(self, authenticated_client):
        """Test exporting session as JSON"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.export_session = AsyncMock(
                return_value='{"session_id": "session-123", "conversation": []}'
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/session-123/export?format=json")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["format"] == "json"

    def test_export_session_markdown(self, authenticated_client):
        """Test exporting session as Markdown"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.export_session = AsyncMock(
                return_value="# Conversation Export\n\n**Messages:** 2\n"
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/session-123/export?format=markdown")

            assert response.status_code == 200
            data = response.json()
            assert data["format"] == "markdown"

    def test_export_session_not_found(self, authenticated_client):
        """Test exporting non-existent session"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.export_session = AsyncMock(return_value=None)
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/nonexistent/export")

            assert response.status_code == 404


# ============================================================================
# Test Analytics
# ============================================================================


class TestAnalytics:
    """Test suite for GET /api/sessions/analytics/overview"""

    def test_get_analytics_success(self, authenticated_client):
        """Test successful analytics retrieval"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_analytics = AsyncMock(
                return_value={
                    "total_sessions": 10,
                    "active_sessions": 5,
                    "avg_messages_per_session": 3.5,
                    "top_session": {"id": "session-1", "messages": 10},
                    "sessions_by_range": {"0-10": 8, "11-20": 2},
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/analytics/overview")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "analytics" in data
            assert data["analytics"]["total_sessions"] == 10

    def test_get_analytics_empty(self, authenticated_client):
        """Test analytics with no sessions"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_analytics = AsyncMock(
                return_value={
                    "total_sessions": 0,
                    "active_sessions": 0,
                    "avg_messages_per_session": 0,
                    "top_session": None,
                    "sessions_by_range": {},
                }
            )
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/analytics/overview")

            assert response.status_code == 200
            data = response.json()
            assert data["analytics"]["total_sessions"] == 0


# ============================================================================
# Test Cleanup
# ============================================================================


class TestCleanup:
    """Test suite for POST /api/sessions/cleanup"""

    def test_cleanup_sessions(self, authenticated_client):
        """Test session cleanup"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.cleanup_expired_sessions = AsyncMock(return_value=0)
            mock_get.return_value = mock_service

            response = authenticated_client.post("/api/sessions/cleanup")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["cleaned"] == 0


# ============================================================================
# Test Health Check
# ============================================================================


class TestHealthCheck:
    """Test suite for GET /api/sessions/health"""

    def test_health_check_success(self, authenticated_client):
        """Test successful health check"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.health_check = AsyncMock(return_value=True)
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/health")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["service"] == "session"

    def test_health_check_failure(self, authenticated_client):
        """Test health check failure"""
        with patch("app.routers.session.get_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.health_check = AsyncMock(return_value=False)
            mock_get.return_value = mock_service

            response = authenticated_client.get("/api/sessions/health")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
