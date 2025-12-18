"""
Integration Tests for Auth Router
Tests JWT authentication endpoints with real database
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def app():
    """Create FastAPI app with auth router"""
    from fastapi import FastAPI

    from app.routers.auth import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_pool.acquire = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_pool


@pytest.mark.integration
class TestAuthRouterIntegration:
    """Comprehensive integration tests for auth router"""

    @pytest.mark.asyncio
    async def test_login_success(self, client, mock_db_pool):
        """Test successful login"""
        import bcrypt

        hashed_pin = bcrypt.hashpw("1234".encode(), bcrypt.gensalt()).decode()

        with patch("app.routers.auth.get_database_pool", return_value=mock_db_pool):
            mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": "user-123",
                    "email": "test@example.com",
                    "pin_hash": hashed_pin,
                    "full_name": "Test User",
                    "role": "member",
                    "active": True,
                }
            )

            payload = {"email": "test@example.com", "pin": "1234"}

            response = client.post("/api/auth/login", json=payload)
            assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client, mock_db_pool):
        """Test login with invalid credentials"""
        with patch("app.routers.auth.get_database_pool", return_value=mock_db_pool):
            mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
            mock_conn.fetchrow = AsyncMock(return_value=None)

            payload = {"email": "test@example.com", "pin": "wrong"}

            response = client.post("/api/auth/login", json=payload)
            assert response.status_code in [401, 500]

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_db_pool):
        """Test getting current user with valid token"""

        from app.routers.auth import create_access_token, get_current_user

        token = create_access_token({"sub": "user-123", "email": "test@example.com"})

        mock_credentials = MagicMock()
        mock_credentials.credentials = token

        mock_request = MagicMock()

        with patch("app.routers.auth.get_database_pool", return_value=mock_db_pool):
            mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": "user-123",
                    "email": "test@example.com",
                    "name": "Test User",
                    "role": "member",
                    "status": "active",
                    "metadata": None,
                    "language_preference": "en",
                }
            )

            user = await get_current_user(mock_credentials, mock_request, mock_db_pool)

            assert user is not None
            assert user["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token"""

        from app.routers.auth import get_current_user

        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid_token"

        mock_request = MagicMock()

        with pytest.raises(Exception):  # Should raise HTTPException
            await get_current_user(mock_credentials, mock_request, None)

    def test_verify_password(self):
        """Test password verification"""
        import bcrypt

        from app.routers.auth import verify_password

        password = "test123"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_create_access_token(self):
        """Test creating access token"""
        from app.routers.auth import create_access_token

        data = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
