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

from backend.app.services.api_key_auth import APIKeyAuth


@pytest.fixture
def api_key_auth():
    """Create APIKeyAuth instance"""
    with patch("backend.app.services.api_key_auth.settings") as mock_settings:
        mock_settings.api_keys = "test-key-123,admin-key-456"
        # Role is granted by identity now, not by the "admin" substring in the
        # key's name — declare it explicitly.
        mock_settings.api_key_roles = "admin-key-456:admin"
        return APIKeyAuth()


class TestAPIKeyAuth:
    """Tests for APIKeyAuth"""

    def test_init(self):
        """Test initialization"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
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


class TestRoleByIdentityNotSpelling:
    """Regression suite for the P0 fixed 2026-07-12: a key was granted
    role=admin merely because its NAME contained "admin"/"secret". The
    documented (public-repo) key `zantara-secret-2024` was therefore a live
    admin master-key. Role must come from identity, never from spelling.
    """

    @staticmethod
    def _auth(api_keys: str, role_map: str | None = None) -> APIKeyAuth:
        with patch("backend.app.services.api_key_auth.settings") as s:
            s.api_keys = api_keys
            s.api_key_roles = role_map
            return APIKeyAuth()

    def test_new_secret_named_key_is_NOT_admin(self):
        """GUILT (the bug): a brand-new key whose name contains 'secret' or
        'admin' is a plain user — the substring no longer confers privilege."""
        auth = self._auth("evil-secret-backdoor,i-am-admin-haha")
        assert auth.valid_keys["evil-secret-backdoor"]["role"] == "user"
        assert auth.valid_keys["i-am-admin-haha"]["role"] == "user"
        assert auth.valid_keys["evil-secret-backdoor"]["permissions"] == ["read"]

    def test_unknown_key_defaults_to_user(self):
        """INNOCENCE/fail-safe: an undeclared key gets read, never write."""
        auth = self._auth("just-some-key")
        assert auth.valid_keys["just-some-key"]["role"] == "user"

    def test_explicit_map_grants_admin_by_identity(self):
        """INNOCENCE: the sanctioned way to make a key admin is to declare it."""
        auth = self._auth("ci-deploy-key", role_map="ci-deploy-key:admin")
        assert auth.valid_keys["ci-deploy-key"]["role"] == "admin"
        assert auth.valid_keys["ci-deploy-key"]["permissions"] == ["*"]

    def test_rotated_legacy_keys_are_plain_user_now(self):
        """GUILT (post-rotation regression): `zantara-secret-2024` and
        `admin-key-2024` were rotated + revoked in prod 2026-07-12 (#2296) —
        the exit-ramp allowlist is now empty, so if either string is ever
        resubmitted (e.g. an old client retrying a cached header) it must
        resolve to plain user, never admin by leftover identity."""
        auth = self._auth("zantara-secret-2024,admin-key-2024")
        assert auth.valid_keys["zantara-secret-2024"]["role"] == "user"
        assert auth.valid_keys["admin-key-2024"]["role"] == "user"

    def test_explicit_map_still_grants_admin_post_rotation(self):
        """INNOCENCE: the sanctioned replacement key is still declarable via
        the map even with the legacy allowlist empty."""
        auth = self._auth(
            "zantara-secret-2024,new-admin",
            role_map="new-admin:admin",
        )
        assert auth.valid_keys["new-admin"]["role"] == "admin"
        assert auth.valid_keys["zantara-secret-2024"]["role"] == "user"

    def test_malformed_role_map_fails_safe(self):
        """A garbage map entry never accidentally grants admin."""
        auth = self._auth("k1", role_map="k1:superuser,,:admin,junk")
        assert auth.valid_keys["k1"]["role"] == "user"
