"""
API Tests for Identity Router - Coverage 95% Target
Tests all identity endpoints and edge cases to achieve 95% coverage

Coverage:
- POST /team/login - Login endpoint with all edge cases
- Error handling and validation
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

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test Login Endpoint
# ============================================================================


class TestTeamLoginEndpoint:
    """Test suite for POST /team/login endpoint"""

    def test_login_success(self, authenticated_client):
        """Test successful login"""
        login_data = {"email": "test@example.com", "pin": "1234"}

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.name = "Test User"
        mock_user.role = "member"
        mock_user.department = "Engineering"
        mock_user.language = "en"
        mock_user.email = "test@example.com"
        mock_user.personalized_response = True

        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(return_value=mock_user)
            mock_service.create_access_token = MagicMock(return_value="jwt_token_123")
            mock_service.get_permissions_for_role = MagicMock(return_value=["read", "write"])
            mock_get_service.return_value = mock_service

            response = authenticated_client.post("/team/login", json=login_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "token" in data
            assert "sessionId" in data
            assert "user" in data
            assert "permissions" in data
            assert data["user"]["email"] == "test@example.com"

    def test_login_invalid_pin_non_digit(self, authenticated_client):
        """Test login with non-digit PIN"""
        login_data = {"email": "test@example.com", "pin": "abcd"}

        response = authenticated_client.post("/team/login", json=login_data)

        assert response.status_code == 400
        assert "PIN format" in response.json()["detail"]

    def test_login_invalid_pin_too_short(self, authenticated_client):
        """Test login with PIN too short"""
        login_data = {"email": "test@example.com", "pin": "123"}

        response = authenticated_client.post("/team/login", json=login_data)

        assert response.status_code == 400
        assert "PIN format" in response.json()["detail"]

    def test_login_invalid_pin_too_long(self, authenticated_client):
        """Test login with PIN too long"""
        login_data = {"email": "test@example.com", "pin": "123456789"}

        response = authenticated_client.post("/team/login", json=login_data)

        assert response.status_code == 400
        assert "PIN format" in response.json()["detail"]

    def test_login_valid_pin_boundaries(self, authenticated_client):
        """Test login with valid PIN at boundaries (4 and 8 digits)"""
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.name = "Test User"
        mock_user.role = "member"
        mock_user.department = "Engineering"
        mock_user.language = "en"
        mock_user.email = "test@example.com"
        mock_user.personalized_response = False

        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(return_value=mock_user)
            mock_service.create_access_token = MagicMock(return_value="jwt_token")
            mock_service.get_permissions_for_role = MagicMock(return_value=[])

            # Test 4-digit PIN
            login_data_4 = {"email": "test@example.com", "pin": "1234"}
            response = authenticated_client.post("/team/login", json=login_data_4)
            assert response.status_code == 200

            # Test 8-digit PIN
            login_data_8 = {"email": "test@example.com", "pin": "12345678"}
            response = authenticated_client.post("/team/login", json=login_data_8)
            assert response.status_code == 200

    def test_login_invalid_credentials(self, authenticated_client):
        """Test login with invalid email or PIN"""
        login_data = {"email": "test@example.com", "pin": "1234"}

        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            response = authenticated_client.post("/team/login", json=login_data)

            assert response.status_code == 401
            assert "Invalid email or PIN" in response.json()["detail"]

    def test_login_user_without_language(self, authenticated_client):
        """Test login with user without language preference"""
        login_data = {"email": "test@example.com", "pin": "1234"}

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.name = "Test User"
        mock_user.role = "admin"
        mock_user.department = None
        mock_user.language = None  # No language preference
        mock_user.email = "test@example.com"
        mock_user.personalized_response = None

        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(return_value=mock_user)
            mock_service.create_access_token = MagicMock(return_value="jwt_token")
            mock_service.get_permissions_for_role = MagicMock(return_value=["admin"])

            response = authenticated_client.post("/team/login", json=login_data)

            assert response.status_code == 200
            data = response.json()
            assert data["user"]["language"] == "en"  # Default
            assert data["personalizedResponse"] is False  # Default

    def test_login_service_error(self, authenticated_client):
        """Test login when service raises error"""
        login_data = {"email": "test@example.com", "pin": "1234"}

        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(side_effect=Exception("Service error"))
            mock_get_service.return_value = mock_service

            response = authenticated_client.post("/team/login", json=login_data)

            assert response.status_code == 500
            assert "unavailable" in response.json()["detail"].lower()

    def test_login_invalid_email_format(self, authenticated_client):
        """Test login with invalid email format"""
        login_data = {"email": "not-an-email", "pin": "1234"}

        # Pydantic validation should catch this before reaching endpoint
        response = authenticated_client.post("/team/login", json=login_data)

        # Should return 422 (validation error) or 400
        assert response.status_code in [400, 422]

    def test_login_response_format(self, authenticated_client):
        """Test login response format matches expected structure"""
        login_data = {"email": "test@example.com", "pin": "1234"}

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.name = "Test User"
        mock_user.role = "member"
        mock_user.department = "Engineering"
        mock_user.language = "id"
        mock_user.email = "test@example.com"
        mock_user.personalized_response = True

        with patch("app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(return_value=mock_user)
            mock_service.create_access_token = MagicMock(return_value="jwt_token_abc")
            mock_service.get_permissions_for_role = MagicMock(return_value=["read"])

            response = authenticated_client.post("/team/login", json=login_data)

            assert response.status_code == 200
            data = response.json()

            # Verify all required fields
            assert "success" in data
            assert "sessionId" in data
            assert "token" in data
            assert "user" in data
            assert "permissions" in data
            assert "personalizedResponse" in data
            assert "loginTime" in data

            # Verify user object structure
            assert "id" in data["user"]
            assert "name" in data["user"]
            assert "role" in data["user"]
            assert "department" in data["user"]
            assert "language" in data["user"]
            assert "email" in data["user"]

            # Verify session ID format
            assert data["sessionId"].startswith("session_")
            assert "user123" in data["sessionId"]

            # Verify login time is ISO format
            assert "T" in data["loginTime"] or "Z" in data["loginTime"]
