"""
API Tests for Authentication Endpoints
Tests the authentication flow including login, token verification, and user profile

Coverage:
- POST /api/auth/login - User login with email/PIN
- GET /api/auth/profile - Get current user profile
- GET /api/auth/check - Check auth status (verify token)
- POST /api/auth/logout - User logout
- GET /api/auth/csrf-token - Get CSRF token
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from jose import jwt

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


def create_mock_db_pool(
    fetchrow_return="NOT_SET",
    fetch_return=None,
    execute_return="DELETE 0",
    fetchval_return=1,
    fetchrow_side_effect=None,
    execute_side_effect=None,
):
    """Create a properly configured mock database pool."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()

    # Set up connection methods
    if fetchrow_side_effect:
        mock_conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    elif fetchrow_return == "NOT_SET":
        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
    else:
        mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)

    mock_conn.fetch = AsyncMock(return_value=fetch_return or [])

    if execute_side_effect:
        mock_conn.execute = AsyncMock(side_effect=execute_side_effect)
    else:
        mock_conn.execute = AsyncMock(return_value=execute_return)

    mock_conn.fetchval = AsyncMock(return_value=fetchval_return)

    # Mock pool.acquire() as async context manager
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # Support close for teardown
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn


@pytest.fixture
def valid_jwt_token():
    """Generate a valid JWT token for testing"""
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "role": "member",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def expired_jwt_token():
    """Generate an expired JWT token for testing"""
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


def create_hashed_pin(pin: str) -> str:
    """Create bcrypt hash for PIN"""
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# test_app fixture is provided by conftest.py (session-scoped)


@pytest.fixture
def test_client(test_app):
    """Create FastAPI TestClient for API tests."""
    from fastapi.testclient import TestClient

    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


# ============================================================================
# Login Tests
# ============================================================================


class TestAuthLogin:
    """Tests for POST /api/auth/login endpoint"""

    def test_login_success(self, test_client, test_app):
        """Test successful login with valid credentials"""
        from app.dependencies import get_database_pool

        hashed_pin = create_hashed_pin("123456")
        mock_user = {
            "id": 1,
            "email": "test@example.com",
            "name": "Test User",
            "password_hash": hashed_pin,
            "role": "member",
            "status": "active",
            "metadata": None,
            "language_preference": "en",
            "active": True,
        }

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=mock_user)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        # Mock audit service
        with patch("services.audit_service.get_audit_service") as mock_audit:
            mock_audit_instance = MagicMock()
            mock_audit_instance.pool = True
            mock_audit_instance.log_auth_event = AsyncMock()
            mock_audit_instance.connect = AsyncMock()
            mock_audit.return_value = mock_audit_instance

            response = test_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "pin": "123456"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data["data"]
        assert data["data"]["token_type"] == "Bearer"

    def test_login_invalid_email(self, test_client, test_app):
        """Test login with non-existent email"""
        from app.dependencies import get_database_pool

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=None)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        with patch("services.audit_service.get_audit_service") as mock_audit:
            mock_audit_instance = MagicMock()
            mock_audit_instance.pool = True
            mock_audit_instance.log_auth_event = AsyncMock()
            mock_audit_instance.connect = AsyncMock()
            mock_audit.return_value = mock_audit_instance

            response = test_client.post(
                "/api/auth/login",
                json={"email": "nonexistent@example.com", "pin": "123456"},
            )

        assert response.status_code == 401

    def test_login_missing_email(self, test_client):
        """Test login without email field"""
        response = test_client.post(
            "/api/auth/login",
            json={"pin": "123456"},
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# Profile Tests
# ============================================================================


class TestAuthProfile:
    """Tests for GET /api/auth/profile endpoint"""

    def test_get_profile_success(self, test_client, test_app, valid_jwt_token):
        """Test getting current user profile with valid token"""
        from app.dependencies import get_database_pool

        mock_user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "member",
            "status": "active",
            "metadata": None,
            "language_preference": "en",
        }

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=mock_user)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.get(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    def test_get_profile_no_token(self, test_client):
        """Test getting user without authentication"""
        response = test_client.get("/api/auth/profile")

        assert response.status_code in [401, 403]

    def test_get_profile_expired_token(self, test_client, expired_jwt_token):
        """Test getting user with expired token"""
        response = test_client.get(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {expired_jwt_token}"},
        )

        assert response.status_code == 401


# ============================================================================
# Auth Check Tests
# ============================================================================


class TestAuthCheck:
    """Tests for GET /api/auth/check endpoint"""

    def test_check_valid_token(self, test_client, test_app, valid_jwt_token):
        """Test checking a valid token"""
        from app.dependencies import get_database_pool

        mock_user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "member",
        }

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=mock_user)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.get(
            "/api/auth/check",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    def test_check_expired_token(self, test_client, expired_jwt_token):
        """Test checking an expired token"""
        response = test_client.get(
            "/api/auth/check",
            headers={"Authorization": f"Bearer {expired_jwt_token}"},
        )

        assert response.status_code == 401


# ============================================================================
# Logout Tests
# ============================================================================


class TestAuthLogout:
    """Tests for POST /api/auth/logout endpoint"""

    def test_logout_success(self, test_client, test_app, valid_jwt_token):
        """Test successful logout"""
        from app.dependencies import get_database_pool

        mock_user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "member",
        }

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=mock_user)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )

        assert response.status_code in [200, 204]

    def test_logout_no_token(self, test_client):
        """Test logout without authentication"""
        response = test_client.post("/api/auth/logout")

        assert response.status_code in [200, 401, 403]


# ============================================================================
# CSRF Token Tests
# ============================================================================


class TestAuthCsrfToken:
    """Tests for GET /api/auth/csrf-token endpoint"""

    def test_get_csrf_token(self, test_client):
        """Test getting CSRF token - no auth required"""
        response = test_client.get("/api/auth/csrf-token")

        assert response.status_code == 200
        data = response.json()
        assert "csrfToken" in data
        assert "sessionId" in data
        assert len(data["csrfToken"]) == 64
        assert data["sessionId"].startswith("session_")


# ============================================================================
# Refresh Token Tests
# ============================================================================


class TestAuthRefreshToken:
    """Tests for POST /api/auth/refresh endpoint"""

    def test_refresh_token_success(self, test_client, test_app, valid_jwt_token):
        """Test POST /api/auth/refresh - successful token refresh"""
        from app.dependencies import get_database_pool

        mock_user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "member",
            "status": "active",
            "metadata": None,
            "language_preference": "en",
        }

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=mock_user)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data["data"]
        assert data["data"]["token_type"] == "Bearer"

    def test_refresh_token_no_auth(self, test_client):
        """Test POST /api/auth/refresh - without authentication"""
        response = test_client.post("/api/auth/refresh")

        assert response.status_code == 401

    def test_refresh_token_expired_token(self, test_client, expired_jwt_token):
        """Test POST /api/auth/refresh - with expired token"""
        response = test_client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {expired_jwt_token}"},
        )

        assert response.status_code == 401

    def test_refresh_token_inactive_user(self, test_client, test_app, valid_jwt_token):
        """Test POST /api/auth/refresh - inactive user"""
        from app.dependencies import get_database_pool

        # Mock user not found (inactive)
        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=None)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )

        assert response.status_code == 401

    def test_refresh_token_new_token_different(self, test_client, test_app, valid_jwt_token):
        """Test POST /api/auth/refresh - new token is different from old"""
        from app.dependencies import get_database_pool

        mock_user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "member",
            "status": "active",
            "metadata": None,
            "language_preference": "en",
        }

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=mock_user)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        new_token = data["data"]["token"]

        # New token should be different from old token
        assert new_token != valid_jwt_token

    def test_refresh_token_response_structure(self, test_client, test_app, valid_jwt_token):
        """Test POST /api/auth/refresh - response structure"""
        from app.dependencies import get_database_pool

        mock_user = {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "member",
            "status": "active",
            "metadata": None,
            "language_preference": "en",
        }

        mock_pool, mock_conn = create_mock_db_pool(fetchrow_return=mock_user)

        def override_db_pool(request=None):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_db_pool

        response = test_client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {valid_jwt_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert "token" in data["data"]
        assert "token_type" in data["data"]
        assert "expires_in" in data["data"]
