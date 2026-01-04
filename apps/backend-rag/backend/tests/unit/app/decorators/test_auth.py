"""
Unit tests for app/decorators/auth.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.decorators.auth import (
    AuthException,
    SecurityLevel,
    api_key_required,
    apply_security_by_endpoint,
    classify_endpoint,
    handle_auth_error,
    jwt_required,
    optional_auth,
    public_endpoint,
    require_auth,
    role_required,
)


class TestAuthDecorators:
    """Tests for auth decorators"""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request"""
        request = MagicMock()
        request.state = MagicMock()
        request.url.path = "/api/test"
        return request

    @pytest.mark.asyncio
    async def test_require_auth_no_user(self, mock_request):
        """Test require_auth when user is not authenticated"""
        mock_request.state.user = None

        @require_auth()
        async def test_endpoint(request):
            return {"message": "success"}

        with pytest.raises(Exception):  # Should raise HTTPException
            await test_endpoint(mock_request)

    @pytest.mark.asyncio
    async def test_require_auth_with_user(self, mock_request):
        """Test require_auth when user is authenticated"""
        mock_request.state.user = MagicMock()
        mock_request.state.user.auth_method = "jwt"

        @require_auth()
        async def test_endpoint(request):
            return {"message": "success"}

        result = await test_endpoint(mock_request)
        assert result == {"message": "success"}

    @pytest.mark.asyncio
    async def test_require_auth_api_key_required(self, mock_request):
        """Test require_auth with API key requirement"""
        mock_request.state.user = MagicMock()
        mock_request.state.user.auth_method = "jwt"  # Wrong auth method

        @require_auth(auth_type="api_key")
        async def test_endpoint(request):
            return {"message": "success"}

        with pytest.raises(Exception):  # Should raise HTTPException
            await test_endpoint(mock_request)

    @pytest.mark.asyncio
    async def test_require_auth_jwt_required(self, mock_request):
        """Test require_auth with JWT requirement"""
        mock_request.state.user = MagicMock()
        mock_request.state.user.auth_method = "api_key"  # Wrong auth method

        @require_auth(auth_type="jwt")
        async def test_endpoint(request):
            return {"message": "success"}

        with pytest.raises(Exception):  # Should raise HTTPException
            await test_endpoint(mock_request)

    @pytest.mark.asyncio
    async def test_require_auth_with_permissions(self, mock_request):
        """Test require_auth with permissions check"""
        mock_request.state.user = MagicMock()
        mock_request.state.user.auth_method = "api_key"
        mock_request.state.user.permissions = ["read"]

        @require_auth(auth_type="api_key", permissions=["read", "write"])
        async def test_endpoint(request):
            return {"message": "success"}

        with pytest.raises(Exception):  # Should raise HTTPException for insufficient permissions
            await test_endpoint(mock_request)

    @pytest.mark.asyncio
    async def test_require_auth_with_wildcard_permission(self, mock_request):
        """Test require_auth with wildcard permission"""
        mock_request.state.user = MagicMock()
        mock_request.state.user.auth_method = "api_key"
        mock_request.state.user.permissions = ["*"]

        @require_auth(auth_type="api_key", permissions=["read", "write"])
        async def test_endpoint(request):
            return {"message": "success"}

        result = await test_endpoint(mock_request)
        assert result == {"message": "success"}

    @pytest.mark.asyncio
    async def test_public_endpoint(self, mock_request):
        """Test public_endpoint decorator"""

        @public_endpoint
        async def test_endpoint(request):
            return {"message": "public"}

        result = await test_endpoint(mock_request)
        assert result == {"message": "public"}

    @pytest.mark.asyncio
    async def test_optional_auth_with_user(self, mock_request):
        """Test optional_auth with authenticated user"""
        mock_request.state.user = MagicMock()
        mock_request.state.user.auth_method = "jwt"

        @optional_auth
        async def test_endpoint(request):
            return {"message": "success"}

        result = await test_endpoint(mock_request)
        assert result == {"message": "success"}

    @pytest.mark.asyncio
    async def test_optional_auth_without_user(self, mock_request):
        """Test optional_auth without user"""
        mock_request.state.user = None

        @optional_auth
        async def test_endpoint(request):
            return {"message": "anonymous"}

        result = await test_endpoint(mock_request)
        assert result == {"message": "anonymous"}

    @pytest.mark.asyncio
    async def test_role_required_success(self, mock_request):
        """Test role_required with correct role"""
        mock_request.state.user = {"role": "admin"}

        @role_required(["admin", "user"])
        async def test_endpoint(request):
            return {"message": "success"}

        result = await test_endpoint(mock_request)
        assert result == {"message": "success"}

    @pytest.mark.asyncio
    async def test_role_required_failure(self, mock_request):
        """Test role_required with incorrect role"""
        mock_request.state.user = {"role": "guest"}

        @role_required(["admin", "user"])
        async def test_endpoint(request):
            return {"message": "success"}

        with pytest.raises(Exception):  # Should raise HTTPException
            await test_endpoint(mock_request)

    @pytest.mark.asyncio
    async def test_role_required_no_user(self, mock_request):
        """Test role_required without user"""
        mock_request.state.user = None

        @role_required(["admin"])
        async def test_endpoint(request):
            return {"message": "success"}

        with pytest.raises(Exception):  # Should raise HTTPException
            await test_endpoint(mock_request)

    def test_api_key_required(self):
        """Test api_key_required decorator factory"""
        decorator = api_key_required(permissions=["read"])
        assert callable(decorator)

    def test_jwt_required(self):
        """Test jwt_required decorator"""
        assert callable(jwt_required)

    def test_classify_endpoint_public(self):
        """Test endpoint classification for public endpoints"""
        assert classify_endpoint("/health") == SecurityLevel.PUBLIC
        assert classify_endpoint("/docs") == SecurityLevel.PUBLIC

    def test_classify_endpoint_api_key(self):
        """Test endpoint classification for API key endpoints"""
        assert classify_endpoint("/api/dashboard/stats") == SecurityLevel.API_KEY

    def test_classify_endpoint_jwt(self):
        """Test endpoint classification for JWT endpoints"""
        assert classify_endpoint("/api/auth/login") == SecurityLevel.JWT

    def test_classify_endpoint_hybrid(self):
        """Test endpoint classification for hybrid endpoints"""
        assert classify_endpoint("/api/search") == SecurityLevel.HYBRID

    def test_classify_endpoint_default(self):
        """Test endpoint classification defaults to hybrid"""
        assert classify_endpoint("/unknown/path") == SecurityLevel.HYBRID

    def test_apply_security_by_endpoint_public(self):
        """Test apply_security_by_endpoint for public endpoints"""
        decorator = apply_security_by_endpoint("/health")
        assert decorator == public_endpoint

    def test_apply_security_by_endpoint_api_key(self):
        """Test apply_security_by_endpoint for API key endpoints"""
        decorator = apply_security_by_endpoint("/api/dashboard/stats")
        assert callable(decorator)

    def test_apply_security_by_endpoint_admin(self):
        """Test apply_security_by_endpoint for admin endpoints"""
        decorator = apply_security_by_endpoint("/api/admin/test")
        assert callable(decorator)

    @pytest.mark.asyncio
    async def test_handle_auth_error_auth_exception(self):
        """Test handle_auth_error with AuthException"""
        mock_request = MagicMock()
        mock_request.url = MagicMock()
        mock_request.url.__str__ = MagicMock(return_value="/api/test")

        exc = AuthException(status_code=401, detail="Unauthorized")
        response = await handle_auth_error(mock_request, exc)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_handle_auth_error_generic(self):
        """Test handle_auth_error with generic exception"""
        mock_request = MagicMock()
        mock_request.url = MagicMock()
        mock_request.url.__str__ = MagicMock(return_value="/api/test")

        exc = ValueError("Generic error")
        response = await handle_auth_error(mock_request, exc)

        assert response.status_code == 500

    def test_auth_exception(self):
        """Test AuthException class"""
        exc = AuthException(status_code=403, detail="Forbidden")
        assert exc.status_code == 403
        assert exc.detail == "Forbidden"
        assert str(exc) == "Forbidden"
