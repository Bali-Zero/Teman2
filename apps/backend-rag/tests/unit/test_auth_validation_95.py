"""
Unit Tests for app/auth/validation.py - 95% Coverage Target
Tests the authentication validation module
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

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
# Test validate_api_key
# ============================================================================


class TestValidateApiKey:
    """Test suite for validate_api_key function"""

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self):
        """Test valid API key returns user context"""
        with patch("app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key.return_value = {
                "id": "service_user",
                "email": "service@example.com",
                "role": "service",
            }

            from app.auth.validation import validate_api_key

            result = await validate_api_key("valid_api_key")

            assert result is not None
            assert result["id"] == "service_user"

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self):
        """Test invalid API key returns None"""
        with patch("app.auth.validation._api_key_auth") as mock_auth:
            mock_auth.validate_api_key.return_value = None

            from app.auth.validation import validate_api_key

            result = await validate_api_key("invalid_api_key")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key_none(self):
        """Test None API key returns None"""
        from app.auth.validation import validate_api_key

        result = await validate_api_key(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key_empty_string(self):
        """Test empty string API key returns None"""
        from app.auth.validation import validate_api_key

        result = await validate_api_key("")

        assert result is None


# ============================================================================
# Test validate_auth_token
# ============================================================================


class TestValidateAuthToken:
    """Test suite for validate_auth_token function"""

    @pytest.mark.asyncio
    async def test_validate_auth_token_success(self):
        """Test valid JWT token returns user context"""
        with patch("app.auth.validation.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user123",
                "email": "test@example.com",
                "role": "admin",
                "name": "Test User",
            }

            from app.auth.validation import validate_auth_token

            result = await validate_auth_token("valid_jwt_token")

            assert result is not None
            assert result["id"] == "user123"
            assert result["email"] == "test@example.com"
            assert result["role"] == "admin"
            assert result["auth_method"] == "jwt_local"

    @pytest.mark.asyncio
    async def test_validate_auth_token_with_userId(self):
        """Test JWT token with userId field"""
        with patch("app.auth.validation.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "userId": "user456",
                "email": "test2@example.com",
            }

            from app.auth.validation import validate_auth_token

            result = await validate_auth_token("valid_jwt_token")

            assert result is not None
            assert result["id"] == "user456"

    @pytest.mark.asyncio
    async def test_validate_auth_token_missing_user_id(self):
        """Test JWT token without user_id returns None"""
        with patch("app.auth.validation.jwt.decode") as mock_decode:
            mock_decode.return_value = {"email": "test@example.com"}

            from app.auth.validation import validate_auth_token

            result = await validate_auth_token("token_without_user_id")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_missing_email(self):
        """Test JWT token without email returns None"""
        with patch("app.auth.validation.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user123"}

            from app.auth.validation import validate_auth_token

            result = await validate_auth_token("token_without_email")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_jwt_error(self):
        """Test JWT decode error returns None"""
        from jose import JWTError

        with patch("app.auth.validation.jwt.decode") as mock_decode:
            mock_decode.side_effect = JWTError("Invalid token")

            from app.auth.validation import validate_auth_token

            result = await validate_auth_token("invalid_jwt")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_unexpected_error(self):
        """Test unexpected error returns None"""
        with patch("app.auth.validation.jwt.decode") as mock_decode:
            mock_decode.side_effect = Exception("Unexpected error")

            from app.auth.validation import validate_auth_token

            result = await validate_auth_token("problematic_token")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_none(self):
        """Test None token returns None"""
        from app.auth.validation import validate_auth_token

        result = await validate_auth_token(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_token_default_role_and_name(self):
        """Test default role and name when not provided"""
        with patch("app.auth.validation.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user789",
                "email": "user@example.com",
                # No role or name provided
            }

            from app.auth.validation import validate_auth_token

            result = await validate_auth_token("token_minimal")

            assert result is not None
            assert result["role"] == "member"  # Default role
            assert result["name"] == "user"  # Derived from email


# ============================================================================
# Test validate_auth_mixed
# ============================================================================


class TestValidateAuthMixed:
    """Test suite for validate_auth_mixed function"""

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_bearer_token(self):
        """Test Bearer token authentication"""
        with patch("app.auth.validation.validate_auth_token") as mock_validate:
            mock_validate.return_value = {
                "id": "user123",
                "email": "test@example.com",
                "role": "member",
            }

            from app.auth.validation import validate_auth_mixed

            result = await validate_auth_mixed(authorization="Bearer valid_token")

            assert result is not None
            assert result["auth_method"] == "jwt"
            mock_validate.assert_called_once_with("valid_token")

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_auth_token_param(self):
        """Test auth_token parameter authentication"""
        with patch("app.auth.validation.validate_auth_token") as mock_validate:
            mock_validate.return_value = {
                "id": "user123",
                "email": "test@example.com",
            }

            from app.auth.validation import validate_auth_mixed

            result = await validate_auth_mixed(auth_token="token_param")

            assert result is not None
            mock_validate.assert_called_once_with("token_param")

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_api_key(self):
        """Test X-API-Key header authentication"""
        with patch("app.auth.validation.validate_auth_token") as mock_jwt:
            with patch("app.auth.validation.validate_api_key") as mock_api:
                mock_jwt.return_value = None  # JWT fails
                mock_api.return_value = {
                    "id": "service_user",
                    "email": "service@example.com",
                }

                from app.auth.validation import validate_auth_mixed

                result = await validate_auth_mixed(x_api_key="api_key_123")

                assert result is not None
                mock_api.assert_called_once_with("api_key_123")

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_jwt_priority_over_api_key(self):
        """Test JWT takes priority over API key"""
        with patch("app.auth.validation.validate_auth_token") as mock_jwt:
            with patch("app.auth.validation.validate_api_key") as mock_api:
                mock_jwt.return_value = {
                    "id": "jwt_user",
                    "email": "jwt@example.com",
                }
                mock_api.return_value = {
                    "id": "api_user",
                    "email": "api@example.com",
                }

                from app.auth.validation import validate_auth_mixed

                result = await validate_auth_mixed(
                    authorization="Bearer jwt_token",
                    x_api_key="api_key",
                )

                assert result["id"] == "jwt_user"
                mock_api.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_invalid_bearer_format(self):
        """Test invalid Bearer header format"""
        with patch("app.auth.validation.validate_auth_token") as mock_jwt:
            mock_jwt.return_value = None

            from app.auth.validation import validate_auth_mixed

            result = await validate_auth_mixed(authorization="InvalidFormat token")

            assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_all_fail(self):
        """Test all authentication methods fail"""
        with patch("app.auth.validation.validate_auth_token") as mock_jwt:
            with patch("app.auth.validation.validate_api_key") as mock_api:
                mock_jwt.return_value = None
                mock_api.return_value = None

                from app.auth.validation import validate_auth_mixed

                result = await validate_auth_mixed(
                    authorization="Bearer invalid_token",
                    x_api_key="invalid_key",
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_no_auth_provided(self):
        """Test no authentication provided"""
        from app.auth.validation import validate_auth_mixed

        result = await validate_auth_mixed()

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_auth_token_with_spaces(self):
        """Test auth_token parameter with spaces is trimmed"""
        with patch("app.auth.validation.validate_auth_token") as mock_validate:
            mock_validate.return_value = {
                "id": "user123",
                "email": "test@example.com",
            }

            from app.auth.validation import validate_auth_mixed

            result = await validate_auth_mixed(auth_token="  token_with_spaces  ")

            assert result is not None
            mock_validate.assert_called_once_with("token_with_spaces")

    @pytest.mark.asyncio
    async def test_validate_auth_mixed_bearer_token_with_extra_spaces(self):
        """Test Bearer token with extra spaces"""
        with patch("app.auth.validation.validate_auth_token") as mock_validate:
            mock_validate.return_value = {
                "id": "user123",
                "email": "test@example.com",
            }

            from app.auth.validation import validate_auth_mixed

            result = await validate_auth_mixed(authorization="Bearer   token_extra_spaces  ")

            assert result is not None
            mock_validate.assert_called_once_with("token_extra_spaces")
