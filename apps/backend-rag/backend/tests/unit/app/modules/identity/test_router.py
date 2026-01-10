"""
Unit tests for identity router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def mock_response():
    """Mock FastAPI response"""
    response = MagicMock()
    response.set_cookie = MagicMock()
    return response


class TestIdentityRouter:
    """Tests for identity router"""

    def test_get_identity_service(self):
        """Test getting identity service singleton"""
        from backend.app.modules.identity.router import get_identity_service

        service = get_identity_service()
        assert service is not None

        # Should return same instance
        service2 = get_identity_service()
        assert service is service2

    @pytest.mark.asyncio
    async def test_team_login_success(self, mock_response):
        """Test successful team login"""
        with patch("backend.app.modules.identity.router.get_identity_service") as mock_get_service:
            # Mock user object
            mock_user = MagicMock()
            mock_user.id = "user_123"
            mock_user.name = "Test User"
            mock_user.role = "consultant"
            mock_user.department = "legal"
            mock_user.language = "en"
            mock_user.email = "test@example.com"
            mock_user.personalized_response = True

            # Mock service
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(return_value=mock_user)
            mock_service.create_access_token = MagicMock(return_value="mock_jwt_token")
            mock_service.get_permissions_for_role = MagicMock(
                return_value=["chat:read", "chat:write"]
            )
            mock_get_service.return_value = mock_service

            # Mock cookie setter
            with patch("backend.app.modules.identity.router.set_auth_cookies") as mock_set_cookies:
                mock_set_cookies.return_value = "csrf_token_123"

                from backend.app.modules.identity.router import LoginRequest, team_login

                request = LoginRequest(email="test@example.com", pin="1234")
                result = await team_login(request, mock_response)

                assert result.success is True
                assert result.token == "mock_jwt_token"
                assert result.user["email"] == "test@example.com"
                assert result.csrfToken == "csrf_token_123"

    @pytest.mark.asyncio
    async def test_team_login_invalid_pin_format(self, mock_response):
        """Test login with invalid PIN format (non-digit)"""
        from fastapi import HTTPException

        from backend.app.modules.identity.router import LoginRequest, team_login

        request = LoginRequest(email="test@example.com", pin="abcd")

        with pytest.raises(HTTPException) as exc_info:
            await team_login(request, mock_response)

        assert exc_info.value.status_code == 400
        assert "PIN" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_team_login_auth_failed(self, mock_response):
        """Test login with wrong credentials"""
        with patch("backend.app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            from fastapi import HTTPException

            from backend.app.modules.identity.router import LoginRequest, team_login

            request = LoginRequest(email="test@example.com", pin="1234")

            with pytest.raises(HTTPException) as exc_info:
                await team_login(request, mock_response)

            assert exc_info.value.status_code == 401
            assert "Invalid" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_team_login_service_error(self, mock_response):
        """Test login when service throws error"""
        with patch("backend.app.modules.identity.router.get_identity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.authenticate_user = AsyncMock(side_effect=Exception("DB error"))
            mock_get_service.return_value = mock_service

            from fastapi import HTTPException

            from backend.app.modules.identity.router import LoginRequest, team_login

            request = LoginRequest(email="test@example.com", pin="1234")

            with pytest.raises(HTTPException) as exc_info:
                await team_login(request, mock_response)

            assert exc_info.value.status_code == 500


class TestLoginModels:
    """Tests for login request/response models"""

    def test_login_request_valid(self):
        """Test valid login request"""
        from backend.app.modules.identity.router import LoginRequest

        request = LoginRequest(email="test@example.com", pin="1234")
        assert request.email == "test@example.com"
        assert request.pin == "1234"

    def test_login_response_fields(self):
        """Test login response model fields"""
        from backend.app.modules.identity.router import LoginResponse

        response = LoginResponse(
            success=True,
            sessionId="session_123",
            token="jwt_token",
            user={"id": "1", "name": "Test"},
            permissions=["read"],
            personalizedResponse=True,
            loginTime="2024-01-01T00:00:00Z",
        )
        assert response.success is True
        assert response.sessionId == "session_123"
