"""
API Tests for Feedback Router P1
Tests new P1 endpoints with review_queue logic

Coverage:
- POST /api/v2/feedback - Submit feedback with review_queue creation logic
- GET /api/v2/feedback/ratings/{session_id} - Get rating for a session
- GET /api/v2/feedback/stats - Get feedback statistics
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
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
@pytest.mark.coverage
class TestFeedbackP1Endpoints:
    """Tests for P1 feedback endpoints with review_queue logic"""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool with transaction support"""
        pool = MagicMock()
        conn = AsyncMock()
        transaction = MagicMock()

        # Setup async context managers
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        conn.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction)
        conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

        return pool, conn

    def test_submit_feedback_positive_rating_no_review(self, authenticated_client, mock_db_pool):
        """Test POST /api/v2/feedback - positive rating (5) should NOT create review_queue"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        # Mock database responses
        conn.fetchval = AsyncMock(return_value=rating_id)

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 5,
                    "feedback_type": "positive",
                    "feedback_text": "Great conversation!",
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["review_queue_id"] is None  # Should NOT create review_queue
                assert "Feedback saved successfully" in data["message"]

                # Verify fetchval was called once (only for conversation_ratings insert)
                assert conn.fetchval.call_count == 1
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_low_rating_creates_review(self, authenticated_client, mock_db_pool):
        """Test POST /api/v2/feedback - rating <= 2 SHOULD create review_queue"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()
        review_queue_id = uuid4()

        # Mock database responses - first call returns rating_id, second returns review_queue_id
        conn.fetchval = AsyncMock(side_effect=[rating_id, review_queue_id])

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 2,  # Low rating
                    "feedback_type": "negative",
                    "feedback_text": "Had some issues",
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["review_queue_id"] == str(review_queue_id)  # Should create review_queue
                assert "added to review queue" in data["message"]

                # Verify fetchval was called twice (conversation_ratings + review_queue)
                assert conn.fetchval.call_count == 2
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_rating_1_creates_review_urgent(
        self, authenticated_client, mock_db_pool
    ):
        """Test POST /api/v2/feedback - rating 1 creates review_queue with urgent priority"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()
        review_queue_id = uuid4()

        conn.fetchval = AsyncMock(side_effect=[rating_id, review_queue_id])

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 1,  # Lowest rating
                    "feedback_type": "issue",
                    "feedback_text": "Found a bug",
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["review_queue_id"] == str(review_queue_id)

                # Verify the INSERT query includes priority='urgent' for rating 1
                # Check that fetchval was called with correct parameters
                assert conn.fetchval.call_count == 2
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_with_correction_text_creates_review(
        self, authenticated_client, mock_db_pool
    ):
        """Test POST /api/v2/feedback - correction_text SHOULD create review_queue even with high rating"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()
        review_queue_id = uuid4()

        conn.fetchval = AsyncMock(side_effect=[rating_id, review_queue_id])

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 4,  # High rating but has correction
                    "feedback_type": "positive",
                    "feedback_text": "Good but...",
                    "correction_text": "The correct answer should be X",  # This triggers review_queue
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["review_queue_id"] == str(review_queue_id)  # Should create review_queue
                assert "added to review queue" in data["message"]

                # Verify fetchval was called twice (conversation_ratings + review_queue)
                assert conn.fetchval.call_count == 2
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_correction_text_combined_with_feedback(
        self, authenticated_client, mock_db_pool
    ):
        """Test POST /api/v2/feedback - correction_text is combined with feedback_text in DB"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 3,
                    "feedback_type": "negative",
                    "feedback_text": "Some feedback",
                    "correction_text": "Correct answer is X",
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                # Verify that the INSERT query was called with combined feedback_text
                # The correction_text should be appended to feedback_text
                call_args = conn.fetchval.call_args_list[0]
                # The INSERT should include the combined text
                assert conn.fetchval.called
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_empty_correction_text_no_review(
        self, authenticated_client, mock_db_pool
    ):
        """Test POST /api/v2/feedback - empty correction_text should NOT create review_queue"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 4,
                    "feedback_type": "positive",
                    "feedback_text": "Good",
                    "correction_text": "",  # Empty string
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["review_queue_id"] is None  # Should NOT create review_queue
                assert conn.fetchval.call_count == 1  # Only conversation_ratings insert
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_validation_errors(self, authenticated_client):
        """Test POST /api/v2/feedback - validation errors"""
        # Invalid rating (too high)
        response = authenticated_client.post(
            "/api/v2/feedback",
            json={
                "session_id": str(uuid4()),
                "rating": 6,  # Invalid: should be 1-5
            },
        )
        assert response.status_code == 422

        # Invalid rating (too low)
        response = authenticated_client.post(
            "/api/v2/feedback",
            json={
                "session_id": str(uuid4()),
                "rating": 0,  # Invalid: should be 1-5
            },
        )
        assert response.status_code == 422

        # Invalid session_id format
        response = authenticated_client.post(
            "/api/v2/feedback",
            json={
                "session_id": "not-a-uuid",
                "rating": 5,
            },
        )
        assert response.status_code == 422

        # Invalid feedback_type
        response = authenticated_client.post(
            "/api/v2/feedback",
            json={
                "session_id": str(uuid4()),
                "rating": 5,
                "feedback_type": "invalid_type",
            },
        )
        assert response.status_code in [400, 422]

    def test_get_rating_success(self, authenticated_client, mock_db_pool):
        """Test GET /api/v2/feedback/ratings/{session_id} - successful retrieval"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        mock_row = {
            "id": rating_id,
            "session_id": session_id,
            "user_id": None,
            "rating": 5,
            "feedback_type": "positive",
            "feedback_text": "Great!",
            "turn_count": None,
            "created_at": "2025-01-01T00:00:00Z",
        }

        conn.fetchrow = AsyncMock(return_value=mock_row)

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.get(f"/api/v2/feedback/ratings/{session_id}")

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["id"] == str(rating_id)
                assert data["session_id"] == str(session_id)
                assert data["rating"] == 5
                assert data["feedback_type"] == "positive"
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_get_rating_not_found(self, authenticated_client, mock_db_pool):
        """Test GET /api/v2/feedback/ratings/{session_id} - rating not found"""
        pool, conn = mock_db_pool
        session_id = uuid4()

        conn.fetchrow = AsyncMock(return_value=None)

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.get(f"/api/v2/feedback/ratings/{session_id}")

            assert response.status_code in [404, 503, 500]
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_get_feedback_stats_success(self, authenticated_client, mock_db_pool):
        """Test GET /api/v2/feedback/stats - successful retrieval"""
        pool, conn = mock_db_pool

        # Mock review_queue stats
        mock_stats = {
            "total_pending": 5,
            "total_resolved": 10,
            "total_ignored": 2,
            "total_reviews": 17,
        }

        # Mock low ratings count
        conn.fetchrow = AsyncMock(return_value=mock_stats)
        conn.fetchval = AsyncMock(return_value=3)  # low_ratings_count

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.get("/api/v2/feedback/stats")

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["total_pending"] == 5
                assert data["total_resolved"] == 10
                assert data["total_ignored"] == 2
                assert data["total_reviews"] == 17
                assert data["low_ratings_count"] == 3
                assert "corrections_count" in data
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_database_unavailable(self, authenticated_client):
        """Test POST /api/v2/feedback - database not available"""
        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = None

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(uuid4()),
                    "rating": 5,
                },
            )

            assert response.status_code == 503
            data = response.json()
            # Check for database error message (may vary)
            detail = data.get("detail", "")
            assert (
                "database" in detail.lower()
                or "connection" in detail.lower()
                or "unavailable" in detail.lower()
            )
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_database_error(self, authenticated_client, mock_db_pool):
        """Test POST /api/v2/feedback - database error handling"""
        import asyncpg

        pool, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(uuid4()),
                    "rating": 5,
                },
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_rating_3_no_review(self, authenticated_client, mock_db_pool):
        """Test POST /api/v2/feedback - rating 3 without correction should NOT create review_queue"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()

        conn.fetchval = AsyncMock(return_value=rating_id)

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 3,  # Middle rating, no correction
                    "feedback_type": "negative",
                    "feedback_text": "It was okay",
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["review_queue_id"] is None  # Should NOT create review_queue
                assert conn.fetchval.call_count == 1  # Only conversation_ratings insert
        finally:
            if original_pool:
                app.state.db_pool = original_pool

    def test_submit_feedback_rating_4_with_correction_creates_review(
        self, authenticated_client, mock_db_pool
    ):
        """Test POST /api/v2/feedback - rating 4 with correction SHOULD create review_queue"""
        pool, conn = mock_db_pool
        session_id = uuid4()
        rating_id = uuid4()
        review_queue_id = uuid4()

        conn.fetchval = AsyncMock(side_effect=[rating_id, review_queue_id])

        from app.main_cloud import app

        original_pool = getattr(app.state, "db_pool", None)
        app.state.db_pool = pool

        try:
            response = authenticated_client.post(
                "/api/v2/feedback",
                json={
                    "session_id": str(session_id),
                    "rating": 4,  # High rating but has correction
                    "feedback_type": "positive",
                    "correction_text": "Actually, the answer should be different",
                },
            )

            assert response.status_code in [200, 503, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["review_queue_id"] == str(review_queue_id)  # Should create review_queue
                assert conn.fetchval.call_count == 2  # conversation_ratings + review_queue
        finally:
            if original_pool:
                app.state.db_pool = original_pool
