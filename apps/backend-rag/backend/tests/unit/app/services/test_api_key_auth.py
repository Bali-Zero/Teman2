"""
Unit tests for API key authentication service
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.api_key_auth import APIKeyAuth


@pytest.fixture
def api_key_auth():
    """Create APIKeyAuth instance"""
    with patch("app.services.api_key_auth.settings") as mock_settings:
        mock_settings.api_keys = "test-key-123,admin-key-456"
        return APIKeyAuth()


class TestAPIKeyAuth:
    """Tests for APIKeyAuth"""

    def test_init(self):
        """Test initialization"""
        with patch("app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2"
            auth = APIKeyAuth()
            assert len(auth.valid_keys) == 2

    def test_validate_api_key_valid(self, api_key_auth):
        """Test validating valid API key"""
        result = api_key_auth.validate_api_key("test-key-123")
        assert result is not None
        assert result["role"] == "user"
        assert result["auth_method"] == "api_key"

    def test_validate_api_key_admin(self, api_key_auth):
        """Test validating admin API key"""
        result = api_key_auth.validate_api_key("admin-key-456")
        assert result is not None
        assert result["role"] == "admin"
        assert "*" in result["permissions"]

    def test_validate_api_key_invalid(self, api_key_auth):
        """Test validating invalid API key"""
        result = api_key_auth.validate_api_key("invalid-key")
        assert result is None

    def test_validate_api_key_empty(self, api_key_auth):
        """Test validating empty API key"""
        result = api_key_auth.validate_api_key("")
        assert result is None

    def test_is_valid_key(self, api_key_auth):
        """Test checking if key is valid"""
        assert api_key_auth.is_valid_key("test-key-123") is True
        assert api_key_auth.is_valid_key("invalid-key") is False

    def test_get_key_info(self, api_key_auth):
        """Test getting key info"""
        info = api_key_auth.get_key_info("test-key-123")
        assert info is not None
        assert "role" in info

    def test_get_key_info_invalid(self, api_key_auth):
        """Test getting info for invalid key"""
        info = api_key_auth.get_key_info("invalid-key")
        assert info is None

    def test_get_service_stats(self, api_key_auth):
        """Test getting service stats"""
        stats = api_key_auth.get_service_stats()
        assert stats["total_keys"] == 2
        assert stats["service_up"] is True

    def test_add_key(self, api_key_auth):
        """Test adding new key"""
        result = api_key_auth.add_key("new-key", role="test", permissions=["read", "write"])
        assert result is True
        assert "new-key" in api_key_auth.valid_keys

    def test_add_key_existing(self, api_key_auth):
        """Test adding existing key"""
        result = api_key_auth.add_key("test-key-123")
        assert result is False

    def test_remove_key(self, api_key_auth):
        """Test removing key"""
        result = api_key_auth.remove_key("test-key-123")
        assert result is True
        assert "test-key-123" not in api_key_auth.valid_keys

    def test_remove_key_nonexistent(self, api_key_auth):
        """Test removing nonexistent key"""
        result = api_key_auth.remove_key("nonexistent-key")
        assert result is False

