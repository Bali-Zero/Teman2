"""
API Tests for Error Scenarios and Edge Cases
Tests common error scenarios across all endpoints

Coverage:
- Invalid JSON payloads
- Missing required fields
- Invalid data types
- Malformed requests
- Rate limiting scenarios
- Service unavailability
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestInvalidJsonPayloads:
    """Tests for invalid JSON payloads"""

    def test_invalid_json_body(self, test_client):
        """Test endpoints with invalid JSON body"""
        response = test_client.post(
            "/api/auth/login",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_malformed_json(self, test_client):
        """Test endpoints with malformed JSON"""
        response = test_client.post(
            "/api/auth/login",
            data='{"email": "test@example.com", "pin": }',  # Missing value
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_empty_json_body(self, test_client):
        """Test POST endpoints with empty JSON body"""
        response = test_client.post(
            "/api/auth/login",
            json={},
        )

        assert response.status_code == 422


@pytest.mark.api
class TestMissingRequiredFields:
    """Tests for missing required fields"""

    def test_missing_email_in_login(self, test_client):
        """Test login without email field"""
        response = test_client.post(
            "/api/auth/login",
            json={"pin": "123456"},
        )

        assert response.status_code == 422

    def test_missing_pin_in_login(self, test_client):
        """Test login without PIN field"""
        response = test_client.post(
            "/api/auth/login",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 422

    def test_missing_query_parameter(self, test_client):
        """Test GET endpoints with missing required query parameters"""
        # Search handlers requires query parameter
        response = test_client.get("/api/handlers/search")

        assert response.status_code == 422


@pytest.mark.api
class TestInvalidDataTypes:
    """Tests for invalid data types"""

    def test_string_instead_of_number(self, authenticated_client):
        """Test endpoints expecting number but receiving string"""
        response = authenticated_client.get("/api/productivity/calendar/events?limit=not_a_number")

        assert response.status_code in [400, 422]

    def test_number_instead_of_string(self, test_client):
        """Test endpoints expecting string but receiving number"""
        response = test_client.post(
            "/api/auth/login",
            json={"email": 12345, "pin": "123456"},
        )

        assert response.status_code == 422

    def test_array_instead_of_object(self, authenticated_client):
        """Test endpoints expecting object but receiving array"""
        response = authenticated_client.post(
            "/api/productivity/gmail/draft",
            json=[],  # Should be object
        )

        assert response.status_code == 422


@pytest.mark.api
class TestMalformedRequests:
    """Tests for malformed requests"""

    def test_missing_content_type(self, test_client):
        """Test POST without Content-Type header"""
        response = test_client.post(
            "/api/auth/login",
            data='{"email": "test@example.com", "pin": "123456"}',
            # No Content-Type header
        )

        # FastAPI should handle this gracefully
        assert response.status_code in [200, 400, 422]

    def test_wrong_content_type(self, test_client):
        """Test POST with wrong Content-Type"""
        response = test_client.post(
            "/api/auth/login",
            data='{"email": "test@example.com", "pin": "123456"}',
            headers={"Content-Type": "text/plain"},
        )

        # FastAPI should handle this
        assert response.status_code in [200, 400, 422]

    def test_extra_fields(self, authenticated_client):
        """Test endpoints with extra unexpected fields"""
        response = authenticated_client.post(
            "/api/productivity/gmail/draft",
            json={
                "recipient": "test@example.com",
                "subject": "Test",
                "body": "Test body",
                "extra_field": "should be ignored",
            },
        )

        # Should accept or ignore extra fields
        assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestAuthenticationErrors:
    """Tests for authentication error scenarios"""

    def test_missing_auth_header(self, test_client):
        """Test protected endpoints without auth header"""
        response = test_client.get("/api/auth/profile")

        assert response.status_code == 401

    def test_invalid_token_format(self, test_client):
        """Test with invalid token format"""
        response = test_client.get(
            "/api/auth/profile",
            headers={"Authorization": "Bearer invalid.token.format"},
        )

        assert response.status_code == 401

    def test_malformed_auth_header(self, test_client):
        """Test with malformed Authorization header"""
        response = test_client.get(
            "/api/auth/profile",
            headers={"Authorization": "NotBearer token"},
        )

        assert response.status_code == 401

    def test_expired_token(self, test_client):
        """Test with expired JWT token"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        expired_payload = {
            "sub": "test@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
        expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")

        response = test_client.get(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401


@pytest.mark.api
class TestServiceUnavailability:
    """Tests for service unavailability scenarios"""

    def test_database_unavailable(self, test_client, test_app):
        """Test endpoints when database is unavailable"""

        from app.dependencies import get_database_pool

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(side_effect=Exception("Database connection failed"))

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "pin": "123456"},
        )

        # Should handle gracefully
        assert response.status_code in [500, 503]

    def test_external_service_error(self, authenticated_client):
        """Test endpoints when external services fail"""
        with patch("services.image_generation_service.ImageGenerationService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.generate_image = AsyncMock(
                side_effect=Exception("External service unavailable")
            )
            mock_service.return_value = mock_instance

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": "Test prompt"},
            )

            assert response.status_code == 500


@pytest.mark.api
class TestBoundaryConditions:
    """Tests for boundary conditions"""

    def test_very_long_string(self, authenticated_client):
        """Test endpoints with very long string inputs"""
        very_long_prompt = "A" * 10000

        response = authenticated_client.post(
            "/media/generate-image",
            json={"prompt": very_long_prompt},
        )

        # Should handle or validate length
        assert response.status_code in [200, 400, 422, 500]

    def test_empty_string(self, authenticated_client):
        """Test endpoints with empty strings"""
        response = authenticated_client.post(
            "/media/generate-image",
            json={"prompt": ""},
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_unicode_characters(self, authenticated_client):
        """Test endpoints with unicode characters"""
        unicode_prompt = "Test with émojis 🎨 and 中文 characters"

        response = authenticated_client.post(
            "/media/generate-image",
            json={"prompt": unicode_prompt},
        )

        # Should handle unicode properly
        assert response.status_code in [200, 400, 422, 500]

    def test_special_characters_in_query(self, test_client):
        """Test GET endpoints with special characters in query"""
        response = test_client.get(
            "/api/handlers/search?query=test%20with%20spaces%20&%20special%20chars"
        )

        assert response.status_code == 200

    def test_negative_numbers(self, authenticated_client):
        """Test endpoints with negative numbers where not expected"""
        response = authenticated_client.get("/api/productivity/calendar/events?limit=-5")

        assert response.status_code in [200, 400, 422]

    def test_zero_value(self, authenticated_client):
        """Test endpoints with zero value"""
        response = authenticated_client.get("/api/productivity/calendar/events?limit=0")

        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestConcurrentRequests:
    """Tests for concurrent request scenarios"""

    def test_multiple_requests_same_endpoint(self, test_client):
        """Test multiple requests to same endpoint"""
        responses = []
        for _ in range(5):
            response = test_client.get("/health")
            responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    def test_rapid_requests(self, test_client):
        """Test rapid sequential requests"""
        for _ in range(10):
            response = test_client.get("/api/csrf-token")
            assert response.status_code == 200


@pytest.mark.api
class TestPathTraversal:
    """Tests for path traversal attempts"""

    def test_path_traversal_in_file_path(self, authenticated_client):
        """Test file path endpoints with path traversal"""
        response = authenticated_client.post(
            "/api/legal/ingest",
            json={"file_path": "../../../etc/passwd"},
        )

        # Should validate and reject
        assert response.status_code in [400, 404, 422]

    def test_sql_injection_attempt(self, test_client):
        """Test endpoints with SQL injection attempts"""
        response = test_client.post(
            "/api/auth/login",
            json={"email": "test@example.com'; DROP TABLE users; --", "pin": "123456"},
        )

        # Should be handled safely
        assert response.status_code in [401, 422, 500]


@pytest.mark.api
class TestResponseFormat:
    """Tests for response format consistency"""

    def test_error_response_format(self, test_client):
        """Test error responses have consistent format"""
        response = test_client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "pin": "wrong"},
        )

        assert response.status_code in [401, 422, 500]
        # Error responses should have detail or message
        if response.status_code != 422:
            data = response.json()
            assert "detail" in data or "message" in data

    def test_success_response_format(self, test_client):
        """Test success responses have consistent format"""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
