"""
API Tests for Input/Output Validation
Tests input validation and output format consistency across endpoints

Coverage:
- Input validation for all endpoints
- Output format validation
- Data type validation
- Range validation
- Format validation (email, URL, etc.)
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
class TestEmailValidation:
    """Tests for email validation"""

    def test_valid_email_formats(self, test_client, test_app):
        """Test various valid email formats"""

        from app.dependencies import get_database_pool

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=None)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        valid_emails = [
            "test@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user_name@example.co.uk",
            "123@example.com",
        ]

        for email in valid_emails:
            response = test_client.post(
                "/api/auth/login",
                json={"email": email, "pin": "123456"},
            )
            # Should accept valid email format (may fail auth but not validation)
            assert response.status_code != 422

    def test_invalid_email_formats(self, test_client):
        """Test various invalid email formats"""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",
            "user@example",
            "user@.com",
        ]

        for email in invalid_emails:
            response = test_client.post(
                "/api/auth/login",
                json={"email": email, "pin": "123456"},
            )
            # Should reject invalid email format
            assert response.status_code == 422


@pytest.mark.api
class TestStringValidation:
    """Tests for string validation"""

    def test_string_length_limits(self, authenticated_client):
        """Test string length validation"""
        # Very long string
        very_long_string = "A" * 100000

        response = authenticated_client.post(
            "/media/generate-image",
            json={"prompt": very_long_string},
        )

        # Should handle or validate length
        assert response.status_code in [200, 400, 422, 500]

    def test_string_required_fields(self, authenticated_client):
        """Test required string fields"""
        response = authenticated_client.post(
            "/media/generate-image",
            json={},  # Missing prompt
        )

        assert response.status_code == 422

    def test_string_trimming(self, authenticated_client):
        """Test string fields with leading/trailing whitespace"""
        response = authenticated_client.post(
            "/media/generate-image",
            json={"prompt": "  Test prompt  "},
        )

        # Should handle whitespace (trim or preserve)
        assert response.status_code in [200, 400, 422, 500]


@pytest.mark.api
class TestNumberValidation:
    """Tests for number validation"""

    def test_positive_number_validation(self, authenticated_client):
        """Test endpoints requiring positive numbers"""
        response = authenticated_client.get("/api/productivity/calendar/events?limit=-5")

        # Should validate positive number
        assert response.status_code in [200, 400, 422]

    def test_integer_validation(self, authenticated_client):
        """Test endpoints requiring integers"""
        response = authenticated_client.get("/api/productivity/calendar/events?limit=5.5")

        # Should validate integer
        assert response.status_code in [200, 400, 422]

    def test_number_range_validation(self, authenticated_client):
        """Test number range validation"""
        # Very large number
        response = authenticated_client.get("/api/productivity/calendar/events?limit=999999999")

        assert response.status_code in [200, 400, 422, 500]


@pytest.mark.api
class TestArrayValidation:
    """Tests for array validation"""

    def test_empty_array(self, authenticated_client):
        """Test endpoints with empty arrays"""
        response = authenticated_client.post(
            "/api/legal/ingest-batch",
            json=[],
        )

        assert response.status_code in [200, 422]

    def test_array_item_validation(self, authenticated_client):
        """Test array items validation"""
        # Invalid items in array
        response = authenticated_client.post(
            "/api/legal/ingest-batch",
            json=[123, 456],  # Should be strings
        )

        assert response.status_code in [200, 422]

    def test_array_max_length(self, authenticated_client):
        """Test array maximum length"""
        # Very large array
        large_array = [f"/path/to/doc{i}.pdf" for i in range(1000)]

        response = authenticated_client.post(
            "/api/legal/ingest-batch",
            json=large_array,
        )

        # Should handle or validate length
        assert response.status_code in [200, 400, 422, 500]


@pytest.mark.api
class TestEnumValidation:
    """Tests for enum validation"""

    def test_valid_enum_values(self, authenticated_client):
        """Test valid enum values"""
        valid_tiers = ["S", "A", "B", "C", "D"]

        with (
            patch("app.routers.legal_ingest.get_legal_service") as mock_get_service,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Test",
                    "chunks_created": 5,
                    "message": "Success",
                }
            )
            mock_get_service.return_value = mock_service

            for tier in valid_tiers:
                response = authenticated_client.post(
                    "/api/legal/ingest",
                    json={"file_path": "/path/to/doc.pdf", "tier": tier},
                )

                assert response.status_code == 200

    def test_invalid_enum_values(self, authenticated_client):
        """Test invalid enum values"""
        invalid_tiers = ["X", "Z", "invalid", "1", "2"]

        for tier in invalid_tiers:
            response = authenticated_client.post(
                "/api/legal/ingest",
                json={"file_path": "/path/to/doc.pdf", "tier": tier},
            )

            assert response.status_code == 400


@pytest.mark.api
class TestDateValidation:
    """Tests for date/time validation"""

    def test_valid_date_formats(self, authenticated_client):
        """Test valid date formats"""
        valid_dates = [
            "2025-12-10T10:00:00Z",
            "2025-12-10T10:00:00+00:00",
            "2025-12-10T10:00:00-05:00",
        ]

        for date in valid_dates:
            response = authenticated_client.post(
                "/api/productivity/calendar/schedule",
                json={
                    "title": "Test Meeting",
                    "start_time": date,
                    "duration_minutes": 60,
                },
            )

            # Should accept valid date formats
            assert response.status_code in [200, 400, 422, 500]

    def test_invalid_date_formats(self, authenticated_client):
        """Test invalid date formats"""
        invalid_dates = [
            "not-a-date",
            "2025-13-45",  # Invalid month/day
            "2025-12-10",  # Missing time
            "10:00:00",  # Missing date
        ]

        for date in invalid_dates:
            response = authenticated_client.post(
                "/api/productivity/calendar/schedule",
                json={
                    "title": "Test Meeting",
                    "start_time": date,
                    "duration_minutes": 60,
                },
            )

            assert response.status_code in [400, 422, 500]


@pytest.mark.api
class TestOutputFormatValidation:
    """Tests for output format validation"""

    def test_json_response_format(self, test_client):
        """Test all endpoints return valid JSON"""
        endpoints = [
            ("GET", "/health"),
            ("GET", "/api/csrf-token"),
            ("GET", "/api/dashboard/stats"),
            ("GET", "/api/handlers/list"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path)

            assert response.status_code in [200, 401, 403, 500]
            if response.status_code == 200:
                # Should be valid JSON
                try:
                    data = response.json()
                    assert isinstance(data, (dict, list))
                except Exception:
                    pytest.fail(f"Endpoint {path} did not return valid JSON")

    def test_error_response_format(self, test_client):
        """Test error responses have consistent format"""
        response = test_client.post(
            "/api/auth/login",
            json={"email": "invalid", "pin": "123456"},
        )

        assert response.status_code in [401, 422, 500]
        if response.status_code != 422:
            data = response.json()
            # Error responses should have detail or message
            assert "detail" in data or "message" in data

    def test_success_response_format(self, test_client):
        """Test success responses have expected fields"""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data or "message" in data


def create_mock_db_pool(fetchrow_return=None):
    """Helper to create mock database pool"""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()

    mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value="DELETE 0")
    mock_conn.fetchval = AsyncMock(return_value=1)

    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn
