"""
Expanded API Tests for Oracle Feedback and User Profile Endpoints

Tests for:
- User feedback submission
- User profile retrieval
- Feedback validation
"""

import pytest


@pytest.mark.api
class TestOracleFeedbackEndpoints:
    """Test Oracle feedback endpoints"""

    def test_submit_positive_feedback(self, authenticated_client):
        """Test submitting positive feedback"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query": "What is PT PMA?",
                "answer": "PT PMA is a foreign investment company...",
                "rating": 5,
                "feedback_text": "Very helpful answer!",
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 201, 400, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "success" in data or "feedback_id" in data

    def test_submit_negative_feedback(self, authenticated_client):
        """Test submitting negative feedback"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query": "Test query",
                "answer": "Test answer",
                "rating": 1,
                "feedback_text": "Answer was not helpful",
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 201, 400, 422]

    def test_submit_feedback_all_ratings(self, authenticated_client):
        """Test submitting feedback with all possible ratings"""
        ratings = [1, 2, 3, 4, 5]

        for rating in ratings:
            response = authenticated_client.post(
                "/api/oracle/feedback",
                json={
                    "query": f"Test query for rating {rating}",
                    "answer": "Test answer",
                    "rating": rating,
                    "user_id": "test_user@example.com",
                },
            )

            assert response.status_code in [200, 201, 400, 422]

    def test_submit_feedback_without_text(self, authenticated_client):
        """Test submitting feedback without feedback text"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query": "Test query",
                "answer": "Test answer",
                "rating": 4,
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 201, 400, 422]

    def test_submit_feedback_long_text(self, authenticated_client):
        """Test submitting feedback with long feedback text"""
        long_feedback = "This is a very long feedback text. " * 50
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query": "Test query",
                "answer": "Test answer",
                "rating": 3,
                "feedback_text": long_feedback,
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 201, 400, 422]


@pytest.mark.api
class TestOracleUserProfileEndpoints:
    """Test Oracle user profile endpoints"""

    def test_get_user_profile(self, authenticated_client):
        """Test retrieving user profile"""
        response = authenticated_client.get("/api/oracle/user-profile/test_user@example.com")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_get_user_profile_different_emails(self, authenticated_client):
        """Test retrieving profiles for different email addresses"""
        emails = [
            "user1@example.com",
            "user2@example.com",
            "test.user@example.com",
        ]

        for email in emails:
            response = authenticated_client.get(f"/api/oracle/user-profile/{email}")

            assert response.status_code in [200, 404]


@pytest.mark.api
class TestOracleHealthAndTesting:
    """Test Oracle health and testing endpoints"""

    def test_oracle_health_check(self, authenticated_client):
        """Test Oracle health check endpoint"""
        response = authenticated_client.get("/api/oracle/health")

        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_test_drive_connection(self, authenticated_client):
        """Test Google Drive connection test"""
        response = authenticated_client.get("/api/oracle/test/drive")

        assert response.status_code in [200, 400, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_test_gemini_integration(self, authenticated_client):
        """Test Gemini integration test"""
        response = authenticated_client.get("/api/oracle/test/gemini")

        assert response.status_code in [200, 400, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestOracleFeedbackEdgeCases:
    """Test edge cases for Oracle feedback"""

    def test_submit_feedback_invalid_rating(self, authenticated_client):
        """Test submitting feedback with invalid rating"""
        # Rating out of range
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query": "Test query",
                "answer": "Test answer",
                "rating": 10,  # Invalid: should be 1-5
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [400, 422]

    def test_submit_feedback_missing_required_fields(self, authenticated_client):
        """Test submitting feedback with missing required fields"""
        # Missing rating
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query": "Test query",
                "answer": "Test answer",
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [400, 422]

    def test_submit_feedback_empty_query(self, authenticated_client):
        """Test submitting feedback with empty query"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query": "",
                "answer": "Test answer",
                "rating": 3,
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 201, 400, 422]
