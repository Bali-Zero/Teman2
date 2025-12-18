"""
API Tests for Auth Validation - Coverage 95% Target
Tests authentication validation functions

Coverage:
- validate_api_key
- validate_auth_token
- validate_auth_mixed
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from jose import jwt

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestValidateAPIKey:
    """Test suite for validate_api_key"""

    @pytest.mark.asyncio
    async def test_validate_api_key_valid(self):
        """Test validate_api_key with valid API key"""
        from app.auth.validation import validate_api_key

        with patch("app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key.return_value = {
                "id": "user123",
                "email": "test@example.com",
                "role": "admin",
            }

            result = await validate_api_key("valid_api_key")

            assert result is not None
            assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self):
        """Test validate_api_key with invalid API key"""
        from app.auth.validation import validate_api_key

        with patch("app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key.return_value = None

            result = await validate_api_key("invalid_api_key")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key_none(self):
        """Test validate_api_key with None"""
        from app.auth.validation import validate_api_key

        result = await validate_api_key(None)

        assert result is None


class TestValidateAuthToken:
    """Test suite for validate_auth_token"""

    @pytest.mark.asyncio
    async def test_validate_auth_token_valid(self):
        """Test validate_auth_token with valid JWT"""
        from app.auth.validation import validate_auth_token
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "user123", "email": "test@example.com", "role": "member"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        result = await validate_auth_token(token)

        assert result is not None
        assert result["id"] == "user123"
        assert result["email"] == "test@example.com"
        assert result["auth_method"] == "jwt_local"

    @pytest.mark.asyncio
    async def test_validate_auth_token_with_userId(self):
        """Test validate_auth_token with userId field instead of sub"""
        from app.auth.validation import validate_auth_token
        from app.core.config import settings

        token = jwt.encode(
            {"userId": "user456", "email": "test2@example.com", "role": "admin"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        result = await validate_auth_token(token)

        assert result is not None
        assert result["id"] == "user456"
        assert result["email"] == "test2@example.com"

    @pytest.mark.asyncio
    async def test_validate_auth_token_invalid(self):
        """Test validate_auth_token with invalid JWT"""
        from app.auth.validation import validate_auth_token

        result = await validate_auth_token("invalid_token")

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_none(self):
        """Test validate_auth_token with None"""
        from app.auth.validation import validate_auth_token

        result = await validate_auth_token(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_missing_fields(self):
        """Test validate_auth_token with missing required fields"""
        from app.auth.validation import validate_auth_token
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "user123"},  # Missing email
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        result = await validate_auth_token(token)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_default_role(self):
        """Test validate_auth_token uses default role when missing"""
        from app.auth.validation import validate_auth_token
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "user123", "email": "test@example.com"},  # No role
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        result = await validate_auth_token(token)

        assert result is not None
        assert result["role"] == "member"  # Default role

    @pytest.mark.asyncio
    async def test_validate_auth_token_default_name(self):
        """Test validate_auth_token generates name from email when missing"""
        from app.auth.validation import validate_auth_token
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "user123", "email": "john.doe@example.com"},  # No name
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        result = await validate_auth_token(token)

        assert result is not None
        assert result["name"] == "john.doe"  # Extracted from email


class TestValidateAuthMixed:
    """Test suite for validate_auth_mixed"""

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_bearer_token(self):
        """Test validate_auth_mixed with Bearer token in Authorization header"""
        from app.auth.validation import validate_auth_mixed
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "user123", "email": "test@example.com"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        result = await validate_auth_mixed(authorization=f"Bearer {token}")

        assert result is not None
        assert result["auth_method"] == "jwt"

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_auth_token_param(self):
        """Test validate_auth_mixed with auth_token parameter"""
        from app.auth.validation import validate_auth_mixed
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "user123", "email": "test@example.com"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        result = await validate_auth_mixed(auth_token=token)

        assert result is not None
        assert result["auth_method"] == "jwt"

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_api_key(self):
        """Test validate_auth_mixed with X-API-Key header"""
        from app.auth.validation import validate_auth_mixed

        with patch("app.auth.validation.validate_api_key") as mock_validate:
            mock_validate.return_value = {
                "id": "user123",
                "email": "test@example.com",
            }

            result = await validate_auth_mixed(x_api_key="valid_api_key")

            assert result is not None
            mock_validate.assert_called_once_with("valid_api_key")

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_priority_jwt_first(self):
        """Test validate_auth_mixed prioritizes JWT over API key"""
        from app.auth.validation import validate_auth_mixed
        from app.core.config import settings

        token = jwt.encode(
            {"sub": "user123", "email": "test@example.com"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        with patch("app.auth.validation.validate_api_key") as mock_validate:
            result = await validate_auth_mixed(authorization=f"Bearer {token}", x_api_key="api_key")

            assert result is not None
            assert result["auth_method"] == "jwt"
            # API key should not be called if JWT succeeds
            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_fallback_to_api_key(self):
        """Test validate_auth_mixed falls back to API key when JWT fails"""
        from app.auth.validation import validate_auth_mixed

        with patch("app.auth.validation.validate_api_key") as mock_validate:
            mock_validate.return_value = {
                "id": "user123",
                "email": "test@example.com",
            }

            result = await validate_auth_mixed(
                authorization="Bearer invalid_token", x_api_key="valid_api_key"
            )

            assert result is not None
            mock_validate.assert_called_once_with("valid_api_key")

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_invalid_bearer_format(self):
        """Test validate_auth_mixed handles invalid Bearer format"""
        from app.auth.validation import validate_auth_mixed

        with patch("app.auth.validation.validate_api_key") as mock_validate:
            mock_validate.return_value = {
                "id": "user123",
                "email": "test@example.com",
            }

            # Invalid format (no "Bearer " prefix)
            result = await validate_auth_mixed(
                authorization="invalid_format", x_api_key="valid_api_key"
            )

            # Should fall back to API key
            assert result is not None
            mock_validate.assert_called_once_with("valid_api_key")

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_no_auth(self):
        """Test validate_auth_mixed with no authentication"""
        from app.auth.validation import validate_auth_mixed

        result = await validate_auth_mixed()

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_all_fail(self):
        """Test validate_auth_mixed when all auth methods fail"""
        from app.auth.validation import validate_auth_mixed

        with patch("app.auth.validation.validate_api_key") as mock_validate:
            mock_validate.return_value = None

            result = await validate_auth_mixed(
                authorization="Bearer invalid", x_api_key="invalid_key"
            )

            assert result is None
