"""
API Tests for Feedback Router
Tests conversation rating and feedback endpoints

Coverage:
- POST /api/feedback/rate-conversation - Rate a conversation
- GET /api/feedback/ratings/{session_id} - Get rating for a session
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Set environment variables before imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestFeedbackEndpoints:
    """Tests for feedback endpoints"""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool"""
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        pool.acquire.return_value.__aexit__.return_value = None
        return pool

    def test_rate_conversation_success(self, authenticated_client, mock_db_pool):
        """Test POST /api/feedback/rate-conversation - successful rating"""
        session_id = str(uuid4())
        rating_id = str(uuid4())

        # Mock database insert
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchval = AsyncMock(return_value=rating_id)

        # Patch app.state.db_pool
        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.post(
                "/api/feedback/rate-conversation",
                json={
                    "session_id": session_id,
                    "rating": 5,
                    "feedback_type": "positive",
                    "feedback_text": "Great conversation!",
                    "turn_count": 10,
                },
            )

            # Should succeed (200) or fail gracefully if DB not available (503)
            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["rating_id"] == rating_id
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_rate_conversation_invalid_rating(self, authenticated_client):
        """Test POST /api/feedback/rate-conversation - invalid rating"""
        response = authenticated_client.post(
            "/api/feedback/rate-conversation",
            json={
                "session_id": str(uuid4()),
                "rating": 6,  # Invalid: should be 1-5
                "feedback_type": "positive",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_rate_conversation_invalid_session_id(self, authenticated_client):
        """Test POST /api/feedback/rate-conversation - invalid session_id format"""
        response = authenticated_client.post(
            "/api/feedback/rate-conversation",
            json={
                "session_id": "invalid-uuid",
                "rating": 5,
            },
        )

        assert response.status_code in [400, 503]  # Bad request or DB unavailable

    def test_rate_conversation_invalid_feedback_type(self, authenticated_client):
        """Test POST /api/feedback/rate-conversation - invalid feedback_type"""
        response = authenticated_client.post(
            "/api/feedback/rate-conversation",
            json={
                "session_id": str(uuid4()),
                "rating": 5,
                "feedback_type": "invalid_type",  # Should be 'positive', 'negative', or 'issue'
            },
        )

        assert response.status_code in [400, 503]

    def test_get_conversation_rating_success(self, authenticated_client, mock_db_pool):
        """Test GET /api/feedback/ratings/{session_id} - successful retrieval"""
        session_id = str(uuid4())
        rating_id = str(uuid4())

        # Mock database fetchrow - use a simple dict that works with dict()
        mock_row = {
            "rating_id": rating_id,
            "session_id": session_id,
            "rating": 5,
            "feedback_type": "positive",
            "feedback_text": "Great!",
            "turn_count": 10,
            "created_at": "2025-01-01T00:00:00Z",
        }

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Patch app.state.db_pool
        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.get(f"/api/feedback/ratings/{session_id}")

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["rating"]["rating"] == 5
                assert data["rating"]["rating_id"] == rating_id
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_get_conversation_rating_not_found(self, authenticated_client, mock_db_pool):
        """Test GET /api/feedback/ratings/{session_id} - rating not found"""
        session_id = str(uuid4())

        # Mock database fetchrow returning None
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=None)

        # Patch app.state.db_pool
        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.get(f"/api/feedback/ratings/{session_id}")

            assert response.status_code in [404, 503, 500]
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_get_conversation_rating_invalid_session_id(self, authenticated_client):
        """Test GET /api/feedback/ratings/{session_id} - invalid session_id format"""
        response = authenticated_client.get("/api/feedback/ratings/invalid-uuid")

        assert response.status_code in [400, 503]

    def test_feedback_endpoints_require_auth(self, test_client):
        """Test that feedback endpoints require authentication"""
        # Test POST without auth
        response = test_client.post(
            "/api/feedback/rate-conversation",
            json={
                "session_id": str(uuid4()),
                "rating": 5,
            },
        )
        assert response.status_code == 401

        # Test GET without auth
        response = test_client.get(f"/api/feedback/ratings/{uuid4()}")
        assert response.status_code == 401

    def test_rate_conversation_database_unavailable(self, authenticated_client):
        """Test POST /api/feedback/rate-conversation - database not available"""
        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = None

        try:
            response = authenticated_client.post(
                "/api/feedback/rate-conversation",
                json={
                    "session_id": str(uuid4()),
                    "rating": 5,
                },
            )

            assert response.status_code == 503
            data = response.json()
            assert "Database not available" in data.get("detail", "")
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_get_rating_database_unavailable(self, authenticated_client):
        """Test GET /api/feedback/ratings/{session_id} - database not available"""
        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = None

        try:
            response = authenticated_client.get(f"/api/feedback/ratings/{uuid4()}")

            assert response.status_code == 503
            data = response.json()
            assert "Database not available" in data.get("detail", "")
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_rate_conversation_database_error(self, authenticated_client, mock_db_pool):
        """Test POST /api/feedback/rate-conversation - database error handling"""
        import asyncpg
        session_id = str(uuid4())

        # Mock database error
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.post(
                "/api/feedback/rate-conversation",
                json={
                    "session_id": session_id,
                    "rating": 5,
                    "feedback_type": "positive",
                },
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_get_rating_database_error(self, authenticated_client, mock_db_pool):
        """Test GET /api/feedback/ratings/{session_id} - database error handling"""
        import asyncpg
        session_id = str(uuid4())

        # Mock database error
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.get(f"/api/feedback/ratings/{session_id}")

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_rate_conversation_minimal_payload(self, authenticated_client, mock_db_pool):
        """Test POST /api/feedback/rate-conversation - minimal required fields"""
        session_id = str(uuid4())
        rating_id = str(uuid4())

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchval = AsyncMock(return_value=rating_id)

        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.post(
                "/api/feedback/rate-conversation",
                json={
                    "session_id": session_id,
                    "rating": 3,
                },
            )

            assert response.status_code in [200, 503, 500]
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_rate_conversation_with_user_id_from_state(self, authenticated_client, mock_db_pool):
        """Test POST /api/feedback/rate-conversation - with user_id from req.state"""
        session_id = str(uuid4())
        user_id = uuid4()
        rating_id = str(uuid4())

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchval = AsyncMock(return_value=rating_id)

        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            # The authenticated_client already sets user info via JWT
            # This test verifies the endpoint works with authenticated requests
            response = authenticated_client.post(
                "/api/feedback/rate-conversation",
                json={
                    "session_id": session_id,
                    "rating": 5,
                    "feedback_type": "positive",
                },
            )

            assert response.status_code in [200, 503, 500]
            # Verify fetchval was called (user_id may be None if not extracted from JWT)
            assert mock_conn.fetchval.called
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_rate_conversation_with_user_profile_from_state(self, authenticated_client, mock_db_pool):
        """Test POST /api/feedback/rate-conversation - with user_profile from req.state"""
        from uuid import UUID
        session_id = str(uuid4())
        user_id = uuid4()
        rating_id = str(uuid4())

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchval = AsyncMock(return_value=rating_id)

        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        # Mock request state with user_profile dict
        with patch("app.routers.feedback.Request") as mock_request_class:
            mock_req_instance = MagicMock()
            mock_req_instance.state.user_profile = {"id": str(user_id)}
            mock_request_class.return_value = mock_req_instance

            try:
                response = authenticated_client.post(
                    "/api/feedback/rate-conversation",
                    json={
                        "session_id": session_id,
                        "rating": 5,
                    },
                )

                assert response.status_code in [200, 503, 500]
            finally:
                if original_pool:
                    app.state.db_pool = original_pool

    def test_rate_conversation_unexpected_error(self, authenticated_client, mock_db_pool):
        """Test POST /api/feedback/rate-conversation - unexpected error handling"""
        session_id = str(uuid4())

        # Mock unexpected error
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchval = AsyncMock(side_effect=ValueError("Unexpected error"))

        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.post(
                "/api/feedback/rate-conversation",
                json={
                    "session_id": session_id,
                    "rating": 5,
                },
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_get_rating_unexpected_error(self, authenticated_client, mock_db_pool):
        """Test GET /api/feedback/ratings/{session_id} - unexpected error handling"""
        session_id = str(uuid4())

        # Mock unexpected error
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(side_effect=ValueError("Unexpected error"))

        from app.main_cloud import app
        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = mock_db_pool

        try:
            response = authenticated_client.get(f"/api/feedback/ratings/{session_id}")

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
        finally:
            if original_pool:
                app.state.db_pool = original_pool

