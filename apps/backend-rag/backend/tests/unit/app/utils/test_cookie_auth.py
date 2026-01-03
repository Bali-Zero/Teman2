"""
Unit tests for cookie authentication utilities
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.utils.cookie_auth import (
    CSRF_COOKIE_NAME,
    JWT_COOKIE_NAME,
    clear_auth_cookies,
    get_cookie_domain,
    get_cookie_secure,
    get_csrf_from_cookie,
    get_jwt_from_cookie,
    get_samesite_policy,
    is_csrf_exempt,
    set_auth_cookies,
    validate_csrf,
)


@pytest.fixture
def mock_response():
    """Mock FastAPI Response"""
    response = MagicMock()
    response.set_cookie = MagicMock()
    response.delete_cookie = MagicMock()
    return response


@pytest.fixture
def mock_request():
    """Mock FastAPI Request"""
    request = MagicMock()
    request.cookies = {}
    return request


class TestCookieAuth:
    """Tests for cookie authentication utilities"""

    def test_get_cookie_domain_with_setting(self):
        """Test getting cookie domain from settings"""
        with patch("app.utils.cookie_auth.settings") as mock_settings:
            mock_settings.cookie_domain = ".example.com"
            domain = get_cookie_domain()
            assert domain == ".example.com"

    def test_get_cookie_domain_without_setting(self):
        """Test getting cookie domain without setting"""
        with patch("app.utils.cookie_auth.settings") as mock_settings:
            if hasattr(mock_settings, "cookie_domain"):
                delattr(mock_settings, "cookie_domain")
            domain = get_cookie_domain()
            assert domain is None

    def test_get_cookie_secure_production(self):
        """Test getting secure flag in production"""
        with patch("app.utils.cookie_auth.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.cookie_secure = True
            secure = get_cookie_secure()
            assert secure is True

    def test_get_cookie_secure_development(self):
        """Test getting secure flag in development"""
        with patch("app.utils.cookie_auth.settings") as mock_settings:
            mock_settings.environment = "development"
            secure = get_cookie_secure()
            assert secure is False

    def test_get_samesite_policy_production(self):
        """Test getting SameSite policy in production"""
        with patch("app.utils.cookie_auth.settings") as mock_settings:
            mock_settings.environment = "production"
            policy = get_samesite_policy()
            assert policy == "none"

    def test_get_samesite_policy_development(self):
        """Test getting SameSite policy in development"""
        with patch("app.utils.cookie_auth.settings") as mock_settings:
            mock_settings.environment = "development"
            policy = get_samesite_policy()
            assert policy == "lax"

    def test_set_auth_cookies(self, mock_response):
        """Test setting auth cookies"""
        with patch("app.utils.cookie_auth.get_cookie_domain") as mock_domain, \
             patch("app.utils.cookie_auth.get_cookie_secure") as mock_secure, \
             patch("app.utils.cookie_auth.get_samesite_policy") as mock_samesite, \
             patch("app.utils.cookie_auth.settings") as mock_settings:
            mock_domain.return_value = None
            mock_secure.return_value = False
            mock_samesite.return_value = "lax"
            mock_settings.jwt_expiry_hours = 24

            csrf_token = set_auth_cookies(mock_response, "jwt-token-123")

            assert csrf_token is not None
            assert mock_response.set_cookie.call_count == 2  # JWT + CSRF

    def test_clear_auth_cookies(self, mock_response):
        """Test clearing auth cookies"""
        with patch("app.utils.cookie_auth.get_cookie_domain") as mock_domain:
            mock_domain.return_value = None

            clear_auth_cookies(mock_response)

            assert mock_response.delete_cookie.call_count == 2  # JWT + CSRF

    def test_get_csrf_from_cookie(self, mock_request):
        """Test getting CSRF token from cookie"""
        mock_request.cookies = {CSRF_COOKIE_NAME: "csrf-token-123"}

        token = get_csrf_from_cookie(mock_request)
        assert token == "csrf-token-123"

    def test_get_csrf_from_cookie_not_found(self, mock_request):
        """Test getting CSRF token when not in cookie"""
        mock_request.cookies = {}

        token = get_csrf_from_cookie(mock_request)
        assert token is None

    def test_get_jwt_from_cookie(self, mock_request):
        """Test getting JWT token from cookie"""
        mock_request.cookies = {JWT_COOKIE_NAME: "jwt-token-123"}

        token = get_jwt_from_cookie(mock_request)
        assert token == "jwt-token-123"

    def test_validate_csrf_valid(self, mock_request):
        """Test validating CSRF token"""
        mock_request.cookies = {CSRF_COOKIE_NAME: "csrf-token-123"}
        mock_request.headers = {"X-CSRF-Token": "csrf-token-123"}

        result = validate_csrf(mock_request)
        assert result is True

    def test_validate_csrf_invalid(self, mock_request):
        """Test validating invalid CSRF token"""
        mock_request.cookies = {CSRF_COOKIE_NAME: "csrf-token-123"}
        mock_request.headers = {"X-CSRF-Token": "different-token"}

        result = validate_csrf(mock_request)
        assert result is False

    def test_is_csrf_exempt_get(self, mock_request):
        """Test CSRF exemption for GET request"""
        mock_request.method = "GET"
        assert is_csrf_exempt(mock_request) is True

    def test_is_csrf_exempt_post(self, mock_request):
        """Test CSRF exemption for POST request"""
        mock_request.method = "POST"
        assert is_csrf_exempt(mock_request) is False

