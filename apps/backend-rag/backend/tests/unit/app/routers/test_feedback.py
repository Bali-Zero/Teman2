"""
Unit tests for feedback router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.dependencies import get_database_pool
from app.routers.feedback import router


@pytest.fixture
def mock_db_pool():
    """Mock database pool with proper async context managers"""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=uuid4())
    conn.fetchrow = AsyncMock(return_value=None)

    # Create async context manager for transaction
    transaction_cm = AsyncMock()
    transaction_cm.__aenter__ = AsyncMock(return_value=None)
    transaction_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=transaction_cm)

    # Create async context manager for acquire
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)

    return pool


@pytest.fixture
def app(mock_db_pool):
    """Create FastAPI app with router and dependency override"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestFeedbackRouter:
    """Tests for feedback router"""

    def test_submit_feedback_success(self, client, mock_db_pool):
        """Test submitting feedback successfully"""

        response = client.post(
            "/api/v2/feedback/",
            json={"session_id": str(uuid4()), "rating": 5, "feedback_type": "positive"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_feedback_low_rating(self, app, client, mock_db_pool):
        """Test submitting feedback with low rating (creates review queue)"""
        # Get the conn mock from the acquire context manager
        acquire_cm = mock_db_pool.acquire.return_value
        conn = acquire_cm.__aenter__.return_value
        conn.fetchval = AsyncMock(side_effect=[uuid4(), uuid4()])  # rating_id, review_queue_id

        response = client.post(
            "/api/v2/feedback/",
            json={"session_id": str(uuid4()), "rating": 1, "feedback_type": "negative"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["review_queue_id"] is not None

    def test_submit_feedback_with_correction(self, app, client, mock_db_pool):
        """Test submitting feedback with correction text"""
        acquire_cm = mock_db_pool.acquire.return_value
        conn = acquire_cm.__aenter__.return_value
        conn.fetchval = AsyncMock(side_effect=[uuid4(), uuid4()])

        response = client.post(
            "/api/v2/feedback/",
            json={
                "session_id": str(uuid4()),
                "rating": 5,
                "correction_text": "This is a correction",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["review_queue_id"] is not None

    def test_submit_feedback_invalid_type(self, client):
        """Test submitting feedback with invalid feedback_type"""
        response = client.post(
            "/api/v2/feedback/",
            json={"session_id": str(uuid4()), "rating": 5, "feedback_type": "invalid"},
        )
        # FastAPI returns 422 for validation errors
        assert response.status_code in [400, 422]

    def test_get_conversation_rating(self, app, client, mock_db_pool):
        """Test getting conversation rating"""
        acquire_cm = mock_db_pool.acquire.return_value
        conn = acquire_cm.__aenter__.return_value
        rating_id = uuid4()
        session_id = uuid4()
        # Create a dict-like mock that works with dict() conversion
        mock_rating = {
            "id": rating_id,
            "session_id": session_id,
            "user_id": None,
            "rating": 5,
            "feedback_type": "positive",
            "feedback_text": None,
            "turn_count": None,
            "created_at": "2025-01-01T00:00:00",
        }
        conn.fetchrow = AsyncMock(return_value=mock_rating)

        response = client.get(f"/api/v2/feedback/ratings/{session_id}")
        assert response.status_code == 200

    def test_get_conversation_rating_not_found(self, app, client, mock_db_pool):
        """Test getting non-existent conversation rating"""
        acquire_cm = mock_db_pool.acquire.return_value
        conn = acquire_cm.__aenter__.return_value
        conn.fetchrow = AsyncMock(return_value=None)

        response = client.get(f"/api/v2/feedback/ratings/{uuid4()}")
        assert response.status_code == 404

    def test_get_conversation_rating_invalid_uuid(self, client):
        """Test getting rating with invalid UUID"""
        response = client.get("/api/v2/feedback/ratings/invalid-uuid")
        assert response.status_code == 400

    def test_get_feedback_stats(self, app, client, mock_db_pool):
        """Test getting feedback statistics"""
        acquire_cm = mock_db_pool.acquire.return_value
        conn = acquire_cm.__aenter__.return_value
        mock_stats = {
            "total_pending": 5,
            "total_resolved": 10,
            "total_ignored": 2,
            "total_reviews": 17,
        }
        conn.fetchrow = AsyncMock(return_value=mock_stats)
        conn.fetchval = AsyncMock(return_value=3)

        response = client.get("/api/v2/feedback/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_pending" in data
        assert "total_resolved" in data
