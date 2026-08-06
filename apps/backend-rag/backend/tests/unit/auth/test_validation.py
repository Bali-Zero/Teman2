"""
Unit tests for auth validation
Target: >95% coverage
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.auth.validation import validate_api_key, validate_auth_mixed, validate_auth_token
from backend.app.core.config import settings


def _future_exp() -> int:
    return int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())


@pytest.fixture(autouse=True)
def available_revocation_store():
    """Successful JWT validation requires an available revocation store."""
    async_client = MagicMock()
    async_client.exists = AsyncMock(return_value=0)
    manager = MagicMock()
    manager.get_async_client.return_value = async_client

    with patch(
        "backend.core.redis_manager.RedisManager.get_instance",
        return_value=manager,
    ):
        yield


class TestAuthValidation:
    """Tests for auth validation"""

    @pytest.mark.asyncio
    async def test_validate_api_key_none(self):
        """Test validating None API key"""
        result = await validate_api_key(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key_empty(self):
        """Test validating empty API key"""
        result = await validate_api_key("")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self):
        """Test validating invalid API key"""
        with patch("backend.app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key_enhanced = AsyncMock(return_value=None)
            result = await validate_api_key("invalid_key")
            assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key_valid(self):
        """Test validating valid API key"""
        with patch("backend.app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key_enhanced = AsyncMock(
                return_value={"id": "user123", "email": "test@example.com"},
            )
            result = await validate_api_key("valid_key")
            assert result is not None
            assert result["id"] == "user123"

    @pytest.mark.asyncio
    async def test_validate_auth_token_none(self):
        """Test validating None token"""
        result = await validate_auth_token(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_empty(self):
        """Test validating empty token"""
        result = await validate_auth_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_invalid(self):
        """Test validating invalid token"""
        result = await validate_auth_token("invalid_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_valid(self):
        """Test validating valid token"""
        payload = {
            "sub": "user123",
            "email": "test@example.com",
            "role": "admin",
            "exp": _future_exp(),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        result = await validate_auth_token(token)
        assert result is not None
        assert result["id"] == "user123"
        assert result["email"] == "test@example.com"
        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_validate_auth_token_with_userid(self):
        """Test validating token with userId instead of sub"""
        payload = {
            "userId": "user456",
            "email": "test2@example.com",
            "exp": _future_exp(),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        result = await validate_auth_token(token)
        assert result is not None
        assert result["id"] == "user456"

    @pytest.mark.asyncio
    async def test_validate_auth_token_missing_fields(self):
        """Test validating token with missing required fields"""
        payload = {"sub": "user123", "exp": _future_exp()}  # Missing email
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        result = await validate_auth_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_none(self):
        """Test validating mixed auth with None values"""
        result = await validate_auth_mixed()
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_bearer_token(self):
        """Test validating mixed auth with Bearer token"""
        payload = {
            "sub": "user123",
            "email": "test@example.com",
            "exp": _future_exp(),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        result = await validate_auth_mixed(authorization=f"Bearer {token}")
        assert result is not None
        assert result["id"] == "user123"

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_auth_token(self):
        """Test validating mixed auth with auth_token parameter"""
        payload = {
            "sub": "user123",
            "email": "test@example.com",
            "exp": _future_exp(),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        result = await validate_auth_mixed(auth_token=token)
        assert result is not None
        assert result["id"] == "user123"

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_api_key(self):
        """Test validating mixed auth with API key"""
        with patch("backend.app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key_enhanced = AsyncMock(
                return_value={"id": "user123", "email": "test@example.com"},
            )
            result = await validate_auth_mixed(x_api_key="valid_key")
            assert result is not None
            assert result["id"] == "user123"

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_priority(self):
        """Test that Bearer token has priority over API key"""
        payload = {
            "sub": "user123",
            "email": "test@example.com",
            "exp": _future_exp(),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        with patch("backend.app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key.return_value = {
                "id": "user456",
                "email": "other@example.com",
            }
            result = await validate_auth_mixed(
                authorization=f"Bearer {token}",
                x_api_key="valid_key",
            )
            assert result is not None
            assert result["id"] == "user123"  # Bearer token takes priority
