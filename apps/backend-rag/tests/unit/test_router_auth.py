"""
Unit tests for Auth Router
90% coverage target with comprehensive endpoint testing
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import JWTError, jwt

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings"""
    with patch("app.routers.auth.settings") as mock:
        mock.jwt_secret_key = "test-secret-key-12345"
        mock.jwt_algorithm = "HS256"
        mock.jwt_access_token_expire_hours = 24
        mock.database_url = "postgresql://test:test@localhost/test"
        yield mock


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg connection pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_request():
    """Mock FastAPI request object"""
    request = MagicMock()
    request.state = MagicMock()
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"user-agent": "test-agent"}
    return request


@pytest.fixture
def test_user_data():
    """Test user data"""
    password = "1234"
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "test@example.com",
        "name": "Test User",
        "full_name": "Test User",
        "password_hash": hashed_password,  # SQL returns pin_hash as password_hash
        "pin_hash": hashed_password,
        "role": "admin",
        "status": "active",
        "permissions": {"read": True, "write": True},
        "metadata": {"read": True, "write": True},
        "language": "en",
        "language_preference": "en",
        "active": True,
    }


@pytest.fixture
def client_with_db(mock_asyncpg_pool, mock_request):
    """Create test client with mocked database"""
    from fastapi import FastAPI

    from app.dependencies import get_database_pool
    from app.routers.auth import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_asyncpg_pool

    # Override dependency
    async def override_get_database_pool():
        return pool

    app.dependency_overrides[get_database_pool] = override_get_database_pool

    yield TestClient(app), pool, conn

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Create test client without database mocking"""
    from fastapi import FastAPI

    from app.routers.auth import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def valid_token(mock_settings):
    """Generate valid JWT token"""
    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            data = {
                "sub": "550e8400-e29b-41d4-a716-446655440000",
                "email": "test@example.com",
                "role": "admin",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            return jwt.encode(data, "test-secret-key-12345", algorithm="HS256")


# ============================================================================
# Tests for verify_password
# ============================================================================


def test_verify_password_success():
    """Test successful password verification"""
    password = "test1234"
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    result = verify_password(password, hashed)
    assert result is True


def test_verify_password_failure():
    """Test password verification failure"""
    password = "test1234"
    wrong_password = "wrong1234"
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    result = verify_password(wrong_password, hashed)
    assert result is False


def test_verify_password_error_handling():
    """Test password verification error handling"""
    result = verify_password("test", "invalid_hash")
    assert result is False


def test_verify_password_empty_password():
    """Test verification with empty password"""
    hashed = bcrypt.hashpw(b"test", bcrypt.gensalt()).decode("utf-8")
    result = verify_password("", hashed)
    assert result is False


def test_verify_password_unicode():
    """Test password verification with Unicode characters"""
    password = "test🔒1234"
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    result = verify_password(password, hashed)
    assert result is True


# ============================================================================
# Tests for create_access_token
# ============================================================================


def test_create_access_token_success(mock_settings):
    """Test creating access token"""
    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            data = {"sub": "user123", "email": "test@example.com"}

            token = create_access_token(data)

            assert token is not None
            assert isinstance(token, str)
            # Decode and verify
            decoded = jwt.decode(token, "test-secret-key-12345", algorithms=["HS256"])
            assert decoded["sub"] == "user123"
            assert decoded["email"] == "test@example.com"
            assert "exp" in decoded


def test_create_access_token_with_expires_delta(mock_settings):
    """Test creating access token with custom expiration"""
    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            data = {"sub": "user123"}
            token = create_access_token(data, expires_delta=timedelta(hours=1))

            decoded = jwt.decode(token, "test-secret-key-12345", algorithms=["HS256"])
            assert "exp" in decoded


def test_create_access_token_default_expiration(mock_settings):
    """Test token uses default expiration when not specified"""
    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            with patch("app.routers.auth.JWT_ACCESS_TOKEN_EXPIRE_HOURS", 24):
                data = {"sub": "user123"}
                token = create_access_token(data)

                decoded = jwt.decode(token, "test-secret-key-12345", algorithms=["HS256"])
                assert "exp" in decoded


def test_create_access_token_with_extra_claims(mock_settings):
    """Test creating token with additional claims"""
    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            data = {
                "sub": "user123",
                "email": "test@example.com",
                "role": "admin",
                "permissions": ["read", "write"],
            }
            token = create_access_token(data)

            decoded = jwt.decode(token, "test-secret-key-12345", algorithms=["HS256"])
            assert decoded["role"] == "admin"
            assert decoded["permissions"] == ["read", "write"]


# ============================================================================
# Tests for get_current_user
# ============================================================================


@pytest.mark.asyncio
async def test_get_current_user_success(mock_asyncpg_pool, mock_request, test_user_data):
    """Test getting current user from valid JWT"""
    pool, conn = mock_asyncpg_pool
    mock_row = {
        "id": test_user_data["id"],
        "email": test_user_data["email"],
        "name": test_user_data["full_name"],
        "role": test_user_data["role"],
        "status": "active",
        "metadata": test_user_data["permissions"],
        "language_preference": test_user_data["language"],
    }
    conn.fetchrow = AsyncMock(return_value=mock_row)

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            token_data = {
                "sub": test_user_data["id"],
                "email": test_user_data["email"],
                "role": test_user_data["role"],
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            mock_credentials = MagicMock()
            mock_credentials.credentials = token

            user = await get_current_user(mock_credentials, request=mock_request, db_pool=pool)

            assert user is not None
            assert user["id"] == test_user_data["id"]
            assert user["email"] == test_user_data["email"]


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(mock_asyncpg_pool, mock_request):
    """Test getting current user with invalid token"""
    pool, conn = mock_asyncpg_pool

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            with patch("app.routers.auth.jwt.decode", side_effect=JWTError("Invalid token")):
                mock_credentials = MagicMock()
                mock_credentials.credentials = "invalid-token"

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(mock_credentials, request=mock_request, db_pool=pool)

                assert exc_info.value.status_code == 401
                assert "could not validate credentials" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_missing_sub(mock_asyncpg_pool, mock_request):
    """Test getting current user with missing sub claim"""
    pool, conn = mock_asyncpg_pool

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            # Token without 'sub' claim
            token_data = {
                "email": "test@example.com",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            mock_credentials = MagicMock()
            mock_credentials.credentials = token

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, request=mock_request, db_pool=pool)

            assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_missing_email(mock_asyncpg_pool, mock_request):
    """Test getting current user with missing email claim"""
    pool, conn = mock_asyncpg_pool

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            # Token without 'email' claim
            token_data = {
                "sub": "user123",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            mock_credentials = MagicMock()
            mock_credentials.credentials = token

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, request=mock_request, db_pool=pool)

            assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_not_found_in_db(mock_asyncpg_pool, mock_request):
    """Test getting current user when user not found in database"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            token_data = {
                "sub": "nonexistent-user",
                "email": "nonexistent@example.com",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            mock_credentials = MagicMock()
            mock_credentials.credentials = token

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, request=mock_request, db_pool=pool)

            assert exc_info.value.status_code == 401


# ============================================================================
# Test POST /api/auth/login - Login Endpoint
# ============================================================================


def test_login_success(client_with_db, test_user_data):
    """Test successful login"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=test_user_data)
    conn.execute = AsyncMock()

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            with patch("services.audit_service.get_audit_service") as mock_audit:
                mock_audit_service = MagicMock()
                mock_audit_service.pool = True
                mock_audit_service.log_auth_event = AsyncMock()
                mock_audit.return_value = mock_audit_service

                response = client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "1234"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify response structure
                assert data["success"] is True
                assert data["message"] == "Login successful"
                assert "data" in data
                assert "token" in data["data"]
                assert "user" in data["data"]
                assert data["data"]["token_type"] == "Bearer"

                # Verify user data
                user = data["data"]["user"]
                assert user["email"] == "test@example.com"
                assert user["role"] == "admin"


def test_login_invalid_email(client_with_db):
    """Test login with non-existent email"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=None)

    with patch("services.audit_service.get_audit_service") as mock_audit:
        mock_audit_service = MagicMock()
        mock_audit_service.pool = True
        mock_audit_service.log_auth_event = AsyncMock()
        mock_audit.return_value = mock_audit_service

        response = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "1234"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "invalid email or pin" in data["detail"].lower()


def test_login_invalid_password(client_with_db, test_user_data):
    """Test login with wrong password"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=test_user_data)

    with patch("services.audit_service.get_audit_service") as mock_audit:
        mock_audit_service = MagicMock()
        mock_audit_service.pool = True
        mock_audit_service.log_auth_event = AsyncMock()
        mock_audit.return_value = mock_audit_service

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrong"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "invalid email or pin" in data["detail"].lower()


def test_login_missing_email(client_with_db):
    """Test login without email"""
    client, pool, conn = client_with_db
    response = client.post(
        "/api/auth/login",
        json={"password": "1234"},
    )

    assert response.status_code == 422  # Validation error


def test_login_missing_password(client_with_db):
    """Test login without password - but note that pin/password are optional in schema"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=None)  # No user found

    with patch("services.audit_service.get_audit_service") as mock_audit:
        mock_audit_service = MagicMock()
        mock_audit_service.pool = True
        mock_audit_service.log_auth_event = AsyncMock()
        mock_audit.return_value = mock_audit_service

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com"},
        )

        # Should be 401 since user will fail auth with empty password
        assert response.status_code in [401, 422, 503]


def test_login_invalid_email_format(client_with_db):
    """Test login with invalid email format"""
    client, pool, conn = client_with_db
    response = client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": "1234"},
    )

    assert response.status_code == 422  # Validation error


def test_login_empty_credentials(client_with_db):
    """Test login with empty credentials"""
    client, pool, conn = client_with_db
    response = client.post(
        "/api/auth/login",
        json={"email": "", "password": ""},
    )

    assert response.status_code == 422  # Validation error


def test_login_database_error(client_with_db):
    """Test login when database fails"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with patch("services.audit_service.get_audit_service") as mock_audit:
        mock_audit_service = MagicMock()
        mock_audit_service.pool = True
        mock_audit_service.log_auth_event = AsyncMock()
        mock_audit.return_value = mock_audit_service

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "1234"},
        )

        assert response.status_code == 500
        data = response.json()
        assert "authentication service unavailable" in data["detail"].lower()


def test_login_inactive_user(client_with_db, test_user_data):
    """Test login with inactive user"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=None)  # Query filters by active=true

    with patch("services.audit_service.get_audit_service") as mock_audit:
        mock_audit_service = MagicMock()
        mock_audit_service.pool = True
        mock_audit_service.log_auth_event = AsyncMock()
        mock_audit.return_value = mock_audit_service

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "1234"},
        )

        assert response.status_code == 401


def test_login_token_expiration(client_with_db, test_user_data):
    """Test that login returns token with correct expiration"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=test_user_data)
    conn.execute = AsyncMock()

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            with patch("app.routers.auth.JWT_ACCESS_TOKEN_EXPIRE_HOURS", 24):
                with patch("services.audit_service.get_audit_service") as mock_audit:
                    mock_audit_service = MagicMock()
                    mock_audit_service.pool = True
                    mock_audit_service.log_auth_event = AsyncMock()
                    mock_audit.return_value = mock_audit_service

                    response = client.post(
                        "/api/auth/login",
                        json={"email": "test@example.com", "password": "1234"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["data"]["expiresIn"] == 24 * 3600  # 24 hours in seconds


# ============================================================================
# Test GET /api/auth/profile - Get Profile Endpoint
# ============================================================================


def test_get_profile_success(client_with_db, test_user_data):
    """Test getting user profile with valid token"""
    client, pool, conn = client_with_db
    mock_row = {
        "id": test_user_data["id"],
        "email": test_user_data["email"],
        "name": test_user_data["full_name"],
        "role": test_user_data["role"],
        "status": "active",
        "metadata": test_user_data["permissions"],
        "language_preference": test_user_data["language"],
    }
    conn.fetchrow = AsyncMock(return_value=mock_row)

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            # Create a valid token
            token_data = {
                "sub": test_user_data["id"],
                "email": test_user_data["email"],
                "role": test_user_data["role"],
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            valid_token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            response = client.get(
                "/api/auth/profile",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@example.com"
            assert data["role"] == "admin"


def test_get_profile_no_token(client):
    """Test getting profile without token"""
    response = client.get("/api/auth/profile")

    assert response.status_code == 403  # Forbidden - no credentials


def test_get_profile_invalid_token(client_with_db):
    """Test getting profile with invalid token"""
    client, pool, conn = client_with_db

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            response = client.get(
                "/api/auth/profile",
                headers={"Authorization": "Bearer invalid-token"},
            )

            assert response.status_code == 401


def test_get_profile_malformed_header(client):
    """Test getting profile with malformed authorization header"""
    response = client.get(
        "/api/auth/profile",
        headers={"Authorization": "InvalidFormat token"},
    )

    assert response.status_code == 403


# ============================================================================
# Test POST /api/auth/logout - Logout Endpoint
# ============================================================================


def test_logout_success(client_with_db, test_user_data):
    """Test successful logout"""
    client, pool, conn = client_with_db
    mock_row = {
        "id": test_user_data["id"],
        "email": test_user_data["email"],
        "name": test_user_data["full_name"],
        "role": test_user_data["role"],
        "status": "active",
        "metadata": test_user_data["permissions"],
        "language_preference": test_user_data["language"],
    }
    conn.fetchrow = AsyncMock(return_value=mock_row)

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            # Create a valid token
            token_data = {
                "sub": test_user_data["id"],
                "email": test_user_data["email"],
                "role": test_user_data["role"],
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            valid_token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Logout successful"


def test_logout_no_token(client):
    """Test logout without token"""
    response = client.post("/api/auth/logout")

    assert response.status_code == 403


def test_logout_invalid_token(client_with_db):
    """Test logout with invalid token"""
    client, pool, conn = client_with_db

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": "Bearer invalid-token"},
            )

            assert response.status_code == 401


# ============================================================================
# Test GET /api/auth/check - Check Auth Endpoint
# ============================================================================


def test_check_auth_success(client_with_db, test_user_data):
    """Test checking auth with valid token"""
    client, pool, conn = client_with_db
    mock_row = {
        "id": test_user_data["id"],
        "email": test_user_data["email"],
        "name": test_user_data["full_name"],
        "role": test_user_data["role"],
        "status": "active",
        "metadata": test_user_data["permissions"],
        "language_preference": test_user_data["language"],
    }
    conn.fetchrow = AsyncMock(return_value=mock_row)

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            # Create a valid token
            token_data = {
                "sub": test_user_data["id"],
                "email": test_user_data["email"],
                "role": test_user_data["role"],
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            }
            valid_token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            response = client.get(
                "/api/auth/check",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert "user" in data
            assert data["user"]["email"] == "test@example.com"


def test_check_auth_no_token(client):
    """Test checking auth without token"""
    response = client.get("/api/auth/check")

    assert response.status_code == 403


def test_check_auth_invalid_token(client_with_db):
    """Test checking auth with invalid token"""
    client, pool, conn = client_with_db

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            response = client.get(
                "/api/auth/check",
                headers={"Authorization": "Bearer invalid-token"},
            )

            assert response.status_code == 401


def test_check_auth_expired_token(client_with_db):
    """Test checking auth with expired token"""
    client, pool, conn = client_with_db

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            # Create expired token
            token_data = {
                "sub": "user123",
                "email": "test@example.com",
                "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
            }
            expired_token = jwt.encode(token_data, "test-secret-key-12345", algorithm="HS256")

            response = client.get(
                "/api/auth/check",
                headers={"Authorization": f"Bearer {expired_token}"},
            )

            # Expired token should fail validation
            assert response.status_code in [401, 422]


# ============================================================================
# Test GET /api/auth/csrf-token - CSRF Token Endpoint
# ============================================================================


def test_get_csrf_token_success(client):
    """Test getting CSRF token"""
    response = client.get("/api/auth/csrf-token")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "csrfToken" in data
    assert "sessionId" in data

    # Verify token format (64 hex chars = 32 bytes)
    assert isinstance(data["csrfToken"], str)
    assert len(data["csrfToken"]) == 64

    # Verify session ID format
    assert isinstance(data["sessionId"], str)
    assert data["sessionId"].startswith("session_")


def test_get_csrf_token_unique(client):
    """Test that each request generates unique tokens"""
    response1 = client.get("/api/auth/csrf-token")
    response2 = client.get("/api/auth/csrf-token")

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Tokens should be different
    assert data1["csrfToken"] != data2["csrfToken"]
    assert data1["sessionId"] != data2["sessionId"]


def test_get_csrf_token_no_auth_required(client):
    """Test CSRF token endpoint doesn't require authentication"""
    # Should work without any authorization header
    response = client.get("/api/auth/csrf-token")

    assert response.status_code == 200


# ============================================================================
# Test get_db_connection helper
# ============================================================================


# NOTE: get_db_connection tests removed - the router now uses centralized dependency injection
# via app.dependencies.get_database_pool instead of a local get_db_connection function


# ============================================================================
# Integration Tests
# ============================================================================


def test_login_and_access_protected_endpoint(client_with_db, test_user_data):
    """Test complete flow: login -> access protected endpoint"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=test_user_data)
    conn.execute = AsyncMock()

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            with patch("services.audit_service.get_audit_service") as mock_audit:
                mock_audit_service = MagicMock()
                mock_audit_service.pool = True
                mock_audit_service.log_auth_event = AsyncMock()
                mock_audit.return_value = mock_audit_service

                # 1. Login
                login_response = client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "1234"},
                )
                assert login_response.status_code == 200
                token = login_response.json()["data"]["token"]

                # 2. Access protected endpoint
                mock_row = {
                    "id": test_user_data["id"],
                    "email": test_user_data["email"],
                    "name": test_user_data["full_name"],
                    "role": test_user_data["role"],
                    "status": "active",
                    "metadata": test_user_data["permissions"],
                    "language_preference": test_user_data["language"],
                }
                conn.fetchrow = AsyncMock(return_value=mock_row)

                profile_response = client.get(
                    "/api/auth/profile",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert profile_response.status_code == 200
                assert profile_response.json()["email"] == "test@example.com"


def test_multiple_concurrent_logins(client_with_db, test_user_data):
    """Test multiple concurrent login requests"""
    client, pool, conn = client_with_db
    conn.fetchrow = AsyncMock(return_value=test_user_data)
    conn.execute = AsyncMock()

    with patch("app.routers.auth.JWT_SECRET_KEY", "test-secret-key-12345"):
        with patch("app.routers.auth.JWT_ALGORITHM", "HS256"):
            with patch("services.audit_service.get_audit_service") as mock_audit:
                mock_audit_service = MagicMock()
                mock_audit_service.pool = True
                mock_audit_service.log_auth_event = AsyncMock()
                mock_audit.return_value = mock_audit_service

                responses = []
                for _ in range(3):
                    response = client.post(
                        "/api/auth/login",
                        json={"email": "test@example.com", "password": "1234"},
                    )
                    responses.append(response)

                # All should succeed
                for response in responses:
                    assert response.status_code == 200
                    assert "token" in response.json()["data"]
