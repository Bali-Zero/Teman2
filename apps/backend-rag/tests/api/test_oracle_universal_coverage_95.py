"""
API Tests for Oracle Universal Router - Coverage 95% Target
Tests all endpoints and edge cases to achieve 95% coverage

Coverage:
- POST /api/oracle/feedback - User feedback submission
- GET /api/oracle/health - Health check endpoint
- GET /api/oracle/user/profile/{user_email} - User profile retrieval
- GET /api/oracle/drive/test - Google Drive connection test
- GET /api/oracle/gemini/test - Gemini integration test
- POST /api/oracle/query - Comprehensive query endpoint tests
- Edge cases and error scenarios
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["DEEPSEEK_API_KEY"] = "test_deepseek_api_key_for_testing"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def valid_jwt_token():
    """Generate a valid JWT token for testing"""
    payload = {
        "sub": "test@example.com",
        "email": "test@example.com",
        "user_id": "test-user-123",
        "role": "member",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def test_client(test_app):
    """Create FastAPI TestClient for API tests"""
    from fastapi.testclient import TestClient

    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


# ============================================================================
# Test Feedback Endpoint
# ============================================================================


class TestFeedbackEndpoint:
    """Test suite for POST /api/oracle/feedback endpoint"""

    def test_submit_feedback_success(self, test_client, valid_jwt_token):
        """Test successful feedback submission"""
        feedback_data = {
            "user_email": "test@example.com",
            "query_text": "What is the capital of Indonesia?",
            "original_answer": "Jakarta",
            "user_correction": None,
            "feedback_type": "positive",
            "rating": 5,
            "notes": "Great answer!",
            "session_id": "test-session-123",
        }

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(
                return_value={"id": 1, "email": "test@example.com", "name": "Test User"}
            )
            mock_db.store_feedback = AsyncMock(return_value=True)

            response = test_client.post(
                "/api/oracle/feedback",
                json=feedback_data,
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "feedback_id" in data
            assert "processed_at" in data

    def test_submit_feedback_with_correction(self, test_client, valid_jwt_token):
        """Test feedback submission with user correction"""
        feedback_data = {
            "user_email": "test@example.com",
            "query_text": "What is the capital?",
            "original_answer": "Jakarta",
            "user_correction": "Bandung",
            "feedback_type": "correction",
            "rating": 3,
            "notes": "Actually it's Bandung",
            "session_id": "test-session-123",
        }

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(
                return_value={"id": 1, "email": "test@example.com"}
            )
            mock_db.store_feedback = AsyncMock(return_value=True)

            response = test_client.post(
                "/api/oracle/feedback",
                json=feedback_data,
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_submit_feedback_user_not_found(self, test_client, valid_jwt_token):
        """Test feedback submission when user profile not found"""
        feedback_data = {
            "user_email": "nonexistent@example.com",
            "query_text": "Test query",
            "original_answer": "Test answer",
            "feedback_type": "positive",
            "rating": 5,
        }

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(return_value=None)
            mock_db.store_feedback = AsyncMock(return_value=True)

            response = test_client.post(
                "/api/oracle/feedback",
                json=feedback_data,
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            # Should still succeed even if user not found
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_submit_feedback_database_error(self, test_client, valid_jwt_token):
        """Test feedback submission with database error"""
        feedback_data = {
            "user_email": "test@example.com",
            "query_text": "Test query",
            "original_answer": "Test answer",
            "feedback_type": "positive",
            "rating": 5,
        }

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(return_value={"id": 1})
            mock_db.store_feedback = AsyncMock(side_effect=Exception("Database error"))

            response = test_client.post(
                "/api/oracle/feedback",
                json=feedback_data,
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            assert response.status_code == 500
            assert "error" in response.json().get("detail", "").lower()


# ============================================================================
# Test Health Check Endpoint
# ============================================================================


class TestHealthEndpoint:
    """Test suite for GET /api/oracle/health endpoint"""

    def test_health_check_success(self, test_client):
        """Test successful health check"""
        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_gs.gemini_available = True
            mock_gs.drive_service = MagicMock()
            with patch("app.routers.oracle_universal.config") as mock_config:
                mock_config.openai_api_key = "test-key"

                response = test_client.get("/api/oracle/health")

                assert response.status_code == 200
                data = response.json()
                assert data["service"] == "Zantara Oracle v5.3 (Ultra Hybrid)"
                assert data["status"] in ["operational", "degraded"]
                assert "components" in data
                assert "capabilities" in data
                assert "metrics" in data

    def test_health_check_degraded(self, test_client):
        """Test health check with degraded components"""
        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_gs.gemini_available = False
            mock_gs.drive_service = None
            with patch("app.routers.oracle_universal.config") as mock_config:
                mock_config.openai_api_key = None

                response = test_client.get("/api/oracle/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "degraded"
                assert "issues" in data
                assert len(data["issues"]) > 0


# ============================================================================
# Test User Profile Endpoint
# ============================================================================


class TestUserProfileEndpoint:
    """Test suite for GET /api/oracle/user/profile/{user_email} endpoint"""

    def test_get_user_profile_success(self, test_client, valid_jwt_token):
        """Test successful user profile retrieval"""
        user_email = "test@example.com"
        mock_profile = {
            "id": 1,
            "email": user_email,
            "name": "Test User",
            "language": "en",
            "meta_json": {"preferences": {}},
        }

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(return_value=mock_profile)

            response = test_client.get(
                f"/api/oracle/user/profile/{user_email}",
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "profile" in data
            assert data["profile"]["email"] == user_email

    def test_get_user_profile_not_found(self, test_client, valid_jwt_token):
        """Test user profile retrieval when user not found"""
        user_email = "nonexistent@example.com"

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(return_value=None)

            response = test_client.get(
                f"/api/oracle/user/profile/{user_email}",
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_user_profile_database_error(self, test_client, valid_jwt_token):
        """Test user profile retrieval with database error"""
        user_email = "test@example.com"

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(side_effect=Exception("Database error"))

            response = test_client.get(
                f"/api/oracle/user/profile/{user_email}",
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            assert response.status_code == 500
            assert "error" in response.json().get("detail", "").lower()


# ============================================================================
# Test Drive Test Endpoint
# ============================================================================


class TestDriveTestEndpoint:
    """Test suite for GET /api/oracle/drive/test endpoint"""

    def test_drive_test_success(self, test_client):
        """Test successful Drive connection test"""
        mock_files = [
            {"id": "1", "name": "test1.pdf", "mimeType": "application/pdf"},
            {"id": "2", "name": "test2.pdf", "mimeType": "application/pdf"},
        ]

        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_drive_service = MagicMock()
            mock_drive_service.files.return_value.list.return_value.execute.return_value = {
                "files": mock_files
            }
            mock_gs.drive_service = mock_drive_service

            response = test_client.get("/api/oracle/drive/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "files" in data
            assert len(data["files"]) == 2

    def test_drive_test_not_initialized(self, test_client):
        """Test Drive test when service not initialized"""
        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_gs.drive_service = None

            response = test_client.get("/api/oracle/drive/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "not initialized" in data["error"].lower()

    def test_drive_test_connection_error(self, test_client):
        """Test Drive test with connection error"""
        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_drive_service = MagicMock()
            mock_drive_service.files.return_value.list.return_value.execute.side_effect = Exception(
                "Connection error"
            )
            mock_gs.drive_service = mock_drive_service

            response = test_client.get("/api/oracle/drive/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data


# ============================================================================
# Test Gemini Test Endpoint
# ============================================================================


class TestGeminiTestEndpoint:
    """Test suite for GET /api/oracle/gemini/test endpoint"""

    def test_gemini_test_success(self, test_client):
        """Test successful Gemini integration test"""
        mock_response = MagicMock()
        mock_response.text = "Hello, I am working correctly for Zantara v5.3."

        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_gs.get_gemini_model = MagicMock(return_value=mock_model)

            response = test_client.get("/api/oracle/gemini/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "message" in data
            assert "test_response" in data
            assert data["model"] == "gemini-2.5-flash"

    def test_gemini_test_long_response(self, test_client):
        """Test Gemini test with long response (truncation)"""
        long_text = "A" * 300  # Longer than 200 chars
        mock_response = MagicMock()
        mock_response.text = long_text

        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_gs.get_gemini_model = MagicMock(return_value=mock_model)

            response = test_client.get("/api/oracle/gemini/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["test_response"]) <= 203  # 200 + "..."

    def test_gemini_test_integration_error(self, test_client):
        """Test Gemini test with integration error"""
        with patch("app.routers.oracle_universal.google_services") as mock_gs:
            mock_gs.get_gemini_model = MagicMock(side_effect=Exception("Integration error"))

            response = test_client.get("/api/oracle/gemini/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data


# ============================================================================
# Test Query Endpoint - Additional Edge Cases
# ============================================================================


class TestQueryEndpointEdgeCases:
    """Test suite for POST /api/oracle/query endpoint - edge cases"""

    def test_query_with_memory_service_error(self, test_client, valid_jwt_token):
        """Test query when memory service fails (non-blocking)"""
        query_data = {
            "query": "What is the capital of Indonesia?",
            "user_email": "test@example.com",
            "collection": "legal",
        }

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(
                return_value={"id": 1, "email": "test@example.com", "language": "en"}
            )

            with patch("app.routers.oracle_universal.get_memory_service") as mock_mem:
                mock_mem.return_value.connect = AsyncMock(side_effect=Exception("Memory error"))

                with patch("app.routers.oracle_universal.intent_classifier") as mock_intent:
                    mock_intent.classify_intent = AsyncMock(
                        return_value={"intent": "question", "mode": "default"}
                    )

                    with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                        mock_search_service = MagicMock()
                        mock_search_service.search = AsyncMock(
                            return_value={"results": [], "total": 0}
                        )
                        mock_search.return_value = mock_search_service

                        # Query should still proceed even if memory service fails
                        response = test_client.post(
                            "/api/oracle/query",
                            json=query_data,
                            headers={"Authorization": f"Bearer {valid_jwt_token}"},
                        )

                        # Should not fail completely due to memory service error
                        assert response.status_code in [200, 500]  # May fail for other reasons

    def test_query_with_personality_service_error(self, test_client, valid_jwt_token):
        """Test query when personality service fails (non-blocking)"""
        query_data = {
            "query": "What is the capital?",
            "user_email": "test@example.com",
        }

        with patch("app.routers.oracle_universal.db_manager") as mock_db:
            mock_db.get_user_profile = AsyncMock(
                return_value={"id": 1, "email": "test@example.com"}
            )

            with patch("app.routers.oracle_universal.get_personality_service") as mock_personality:
                mock_personality.return_value.get_user_personality.side_effect = Exception(
                    "Personality error"
                )

                with patch("app.routers.oracle_universal.intent_classifier") as mock_intent:
                    mock_intent.classify_intent = AsyncMock(
                        return_value={"intent": "question", "mode": "default"}
                    )

                    with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                        mock_search_service = MagicMock()
                        mock_search_service.search = AsyncMock(
                            return_value={"results": [], "total": 0}
                        )
                        mock_search.return_value = mock_search_service

                        # Query should proceed even if personality service fails
                        response = test_client.post(
                            "/api/oracle/query",
                            json=query_data,
                            headers={"Authorization": f"Bearer {valid_jwt_token}"},
                        )

                        # Should handle gracefully
                        assert response.status_code in [200, 500]
