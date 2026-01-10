"""
Comprehensive Unit Tests for app/services/api_key_auth.py
Target: 90%+ coverage

Tests APIKeyAuth service including:
- Initialization with various key configurations
- API key validation
- Key management operations
- Usage statistics tracking
- Service monitoring
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2,admin_key_secret"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test APIKeyAuth Initialization
# ============================================================================


class TestAPIKeyAuthInit:
    """Test suite for APIKeyAuth initialization"""

    def test_init_with_single_key(self):
        """Test initialization with single API key"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "single_test_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert len(service.valid_keys) == 1
            assert "single_test_key" in service.valid_keys
            assert service.valid_keys["single_test_key"]["role"] == "user"
            assert service.valid_keys["single_test_key"]["permissions"] == ["read"]

    def test_init_with_multiple_keys(self):
        """Test initialization with multiple API keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2,key3"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert len(service.valid_keys) == 3
            assert "key1" in service.valid_keys
            assert "key2" in service.valid_keys
            assert "key3" in service.valid_keys

    def test_init_with_admin_key(self):
        """Test initialization with admin key (contains 'admin' in name)"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "admin_key_test"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert service.valid_keys["admin_key_test"]["role"] == "admin"
            assert service.valid_keys["admin_key_test"]["permissions"] == ["*"]

    def test_init_with_secret_key(self):
        """Test initialization with secret key (contains 'secret' in name)"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "my_secret_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert service.valid_keys["my_secret_key"]["role"] == "admin"
            assert service.valid_keys["my_secret_key"]["permissions"] == ["*"]

    def test_init_with_whitespace_keys(self):
        """Test initialization handles whitespace in key list"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = " key1 , key2 ,  key3  "

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert len(service.valid_keys) == 3
            assert "key1" in service.valid_keys
            assert "key2" in service.valid_keys
            assert "key3" in service.valid_keys

    def test_init_with_empty_keys(self):
        """Test initialization with empty API keys string"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = ""

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert len(service.valid_keys) == 0
            assert len(service.key_stats) == 0

    def test_init_with_mixed_empty_keys(self):
        """Test initialization filters out empty strings from key list"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,,key2,  ,key3"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert len(service.valid_keys) == 3
            assert "" not in service.valid_keys

    def test_init_creates_key_stats(self):
        """Test initialization creates usage statistics for all keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            assert len(service.key_stats) == 2
            assert service.key_stats["key1"]["usage_count"] == 0
            assert service.key_stats["key1"]["last_used"] is None
            assert service.key_stats["key2"]["usage_count"] == 0
            assert service.key_stats["key2"]["last_used"] is None

    def test_init_sets_created_at_timestamp(self):
        """Test initialization sets created_at timestamp for keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "test_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            created_at = service.valid_keys["test_key"]["created_at"]
            assert created_at is not None
            assert isinstance(created_at, str)
            assert created_at.endswith("Z")

    def test_init_sets_description(self):
        """Test initialization sets description for keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "test_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            description = service.valid_keys["test_key"]["description"]
            assert description == "API key loaded from environment variable"

    @patch("backend.app.services.api_key_auth.logger")
    def test_init_logs_key_count(self, mock_logger):
        """Test initialization logs the number of loaded keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2,key3"

            from backend.app.services.api_key_auth import APIKeyAuth

            APIKeyAuth()

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "3 valid keys" in call_args


# ============================================================================
# Test validate_api_key Method
# ============================================================================


class TestValidateAPIKey:
    """Test suite for validate_api_key method"""

    @pytest.fixture
    def service(self):
        """Create APIKeyAuth service for testing"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "valid_key,admin_key_test"

            from backend.app.services.api_key_auth import APIKeyAuth

            return APIKeyAuth()

    def test_validate_valid_api_key(self, service):
        """Test validation of a valid API key returns user context"""
        result = service.validate_api_key("valid_key")

        assert result is not None
        assert isinstance(result, dict)
        assert result["id"] == "api_key_valid_ke"
        assert result["email"] == "user@zantara.dev"
        assert result["name"] == "API User (user)"
        assert result["role"] == "user"
        assert result["status"] == "active"
        assert result["auth_method"] == "api_key"
        assert result["permissions"] == ["read"]

    def test_validate_admin_api_key(self, service):
        """Test validation of an admin API key"""
        result = service.validate_api_key("admin_key_test")

        assert result is not None
        assert result["role"] == "admin"
        assert result["email"] == "admin@zantara.dev"
        assert result["permissions"] == ["*"]

    def test_validate_invalid_api_key(self, service):
        """Test validation of an invalid API key returns None"""
        result = service.validate_api_key("invalid_key")

        assert result is None

    def test_validate_empty_api_key(self, service):
        """Test validation of empty API key returns None"""
        result = service.validate_api_key("")

        assert result is None

    def test_validate_none_api_key(self, service):
        """Test validation of None API key returns None"""
        result = service.validate_api_key(None)

        assert result is None

    def test_validate_increments_usage_count(self, service):
        """Test validation increments usage count"""
        initial_count = service.key_stats["valid_key"]["usage_count"]

        service.validate_api_key("valid_key")

        assert service.key_stats["valid_key"]["usage_count"] == initial_count + 1

    def test_validate_updates_last_used(self, service):
        """Test validation updates last_used timestamp"""
        assert service.key_stats["valid_key"]["last_used"] is None

        service.validate_api_key("valid_key")

        last_used = service.key_stats["valid_key"]["last_used"]
        assert last_used is not None
        assert isinstance(last_used, str)

    def test_validate_multiple_calls_increment_count(self, service):
        """Test multiple validations increment count correctly"""
        service.validate_api_key("valid_key")
        service.validate_api_key("valid_key")
        service.validate_api_key("valid_key")

        assert service.key_stats["valid_key"]["usage_count"] == 3

    def test_validate_returns_metadata(self, service):
        """Test validation returns metadata with usage stats"""
        result = service.validate_api_key("valid_key")

        assert "metadata" in result
        assert "key_created_at" in result["metadata"]
        assert "key_description" in result["metadata"]
        assert "usage_count" in result["metadata"]
        assert "last_used" in result["metadata"]
        assert result["metadata"]["usage_count"] == 1

    def test_validate_id_truncates_key(self, service):
        """Test validation creates ID with truncated key (first 8 chars)"""
        result = service.validate_api_key("valid_key")

        assert result["id"] == "api_key_valid_ke"

    @patch("backend.app.services.api_key_auth.logger")
    def test_validate_logs_warning_for_no_key(self, mock_logger, service):
        """Test validation logs warning when no key provided"""
        service.validate_api_key("")

        mock_logger.warning.assert_called_once_with("No API key provided")

    @patch("backend.app.services.api_key_auth.logger")
    def test_validate_logs_warning_for_invalid_key(self, mock_logger, service):
        """Test validation logs warning for invalid key"""
        service.validate_api_key("invalid_key_test")

        call_args = mock_logger.warning.call_args[0][0]
        assert "Invalid API key provided" in call_args
        assert "invalid_ke" in call_args  # First 10 chars

    @patch("backend.app.services.api_key_auth.logger")
    def test_validate_logs_debug_for_valid_key(self, mock_logger, service):
        """Test validation logs debug info for valid key"""
        service.validate_api_key("valid_key")

        call_args = mock_logger.debug.call_args[0][0]
        assert "Valid API key used" in call_args
        assert "user" in call_args


# ============================================================================
# Test is_valid_key Method
# ============================================================================


class TestIsValidKey:
    """Test suite for is_valid_key method"""

    @pytest.fixture
    def service(self):
        """Create APIKeyAuth service for testing"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "valid_key,another_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            return APIKeyAuth()

    def test_is_valid_key_returns_true(self, service):
        """Test is_valid_key returns True for valid key"""
        assert service.is_valid_key("valid_key") is True

    def test_is_valid_key_returns_false(self, service):
        """Test is_valid_key returns False for invalid key"""
        assert service.is_valid_key("invalid_key") is False

    def test_is_valid_key_with_empty_string(self, service):
        """Test is_valid_key returns False for empty string"""
        assert service.is_valid_key("") is False

    def test_is_valid_key_multiple_keys(self, service):
        """Test is_valid_key works for all valid keys"""
        assert service.is_valid_key("valid_key") is True
        assert service.is_valid_key("another_key") is True


# ============================================================================
# Test get_key_info Method
# ============================================================================


class TestGetKeyInfo:
    """Test suite for get_key_info method"""

    @pytest.fixture
    def service(self):
        """Create APIKeyAuth service for testing"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "test_key,admin_secret"

            from backend.app.services.api_key_auth import APIKeyAuth

            return APIKeyAuth()

    def test_get_key_info_returns_info(self, service):
        """Test get_key_info returns key information"""
        info = service.get_key_info("test_key")

        assert info is not None
        assert info["role"] == "user"
        assert info["permissions"] == ["read"]
        assert "created_at" in info
        assert "description" in info

    def test_get_key_info_returns_none_for_invalid(self, service):
        """Test get_key_info returns None for invalid key"""
        info = service.get_key_info("invalid_key")

        assert info is None

    def test_get_key_info_does_not_increment_usage(self, service):
        """Test get_key_info does not increment usage statistics"""
        initial_count = service.key_stats["test_key"]["usage_count"]

        service.get_key_info("test_key")

        assert service.key_stats["test_key"]["usage_count"] == initial_count

    def test_get_key_info_admin_key(self, service):
        """Test get_key_info returns admin info for admin key"""
        info = service.get_key_info("admin_secret")

        assert info["role"] == "admin"
        assert info["permissions"] == ["*"]


# ============================================================================
# Test get_service_stats Method
# ============================================================================


class TestGetServiceStats:
    """Test suite for get_service_stats method"""

    @pytest.fixture
    def service(self):
        """Create APIKeyAuth service for testing"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2,key3"

            from backend.app.services.api_key_auth import APIKeyAuth

            return APIKeyAuth()

    def test_get_service_stats_structure(self, service):
        """Test get_service_stats returns correct structure"""
        stats = service.get_service_stats()

        assert "total_keys" in stats
        assert "total_usage" in stats
        assert "key_usage" in stats
        assert "service_up" in stats
        assert "service_type" in stats

    def test_get_service_stats_total_keys(self, service):
        """Test get_service_stats reports correct total keys"""
        stats = service.get_service_stats()

        assert stats["total_keys"] == 3

    def test_get_service_stats_initial_usage(self, service):
        """Test get_service_stats shows zero usage initially"""
        stats = service.get_service_stats()

        assert stats["total_usage"] == 0

    def test_get_service_stats_after_usage(self, service):
        """Test get_service_stats tracks usage correctly"""
        service.validate_api_key("key1")
        service.validate_api_key("key2")
        service.validate_api_key("key1")

        stats = service.get_service_stats()

        assert stats["total_usage"] == 3

    def test_get_service_stats_service_up(self, service):
        """Test get_service_stats indicates service is up"""
        stats = service.get_service_stats()

        assert stats["service_up"] is True

    def test_get_service_stats_service_type(self, service):
        """Test get_service_stats reports correct service type"""
        stats = service.get_service_stats()

        assert stats["service_type"] == "static_api_key"

    def test_get_service_stats_includes_key_usage(self, service):
        """Test get_service_stats includes detailed key usage"""
        service.validate_api_key("key1")

        stats = service.get_service_stats()

        assert "key1" in stats["key_usage"]
        assert stats["key_usage"]["key1"]["usage_count"] == 1


# ============================================================================
# Test add_key Method
# ============================================================================


class TestAddKey:
    """Test suite for add_key method"""

    @pytest.fixture
    def service(self):
        """Create APIKeyAuth service for testing"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "existing_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            return APIKeyAuth()

    def test_add_key_success(self, service):
        """Test adding a new key successfully"""
        result = service.add_key("new_key", role="user", permissions=["read", "write"])

        assert result is True
        assert "new_key" in service.valid_keys
        assert service.valid_keys["new_key"]["role"] == "user"
        assert service.valid_keys["new_key"]["permissions"] == ["read", "write"]

    def test_add_key_default_role(self, service):
        """Test adding a key with default role"""
        result = service.add_key("new_key")

        assert result is True
        assert service.valid_keys["new_key"]["role"] == "test"

    def test_add_key_default_permissions(self, service):
        """Test adding a key with default permissions"""
        result = service.add_key("new_key")

        assert result is True
        assert service.valid_keys["new_key"]["permissions"] == ["read"]

    def test_add_key_creates_stats_entry(self, service):
        """Test adding a key creates stats entry"""
        service.add_key("new_key")

        assert "new_key" in service.key_stats
        assert service.key_stats["new_key"]["usage_count"] == 0
        assert service.key_stats["new_key"]["last_used"] is None

    def test_add_key_sets_created_at(self, service):
        """Test adding a key sets created_at timestamp"""
        service.add_key("new_key")

        created_at = service.valid_keys["new_key"]["created_at"]
        assert created_at is not None
        assert isinstance(created_at, str)

    def test_add_key_sets_description(self, service):
        """Test adding a key sets description"""
        service.add_key("new_key", role="admin")

        description = service.valid_keys["new_key"]["description"]
        assert description == "Programmatically added key (admin)"

    def test_add_existing_key_fails(self, service):
        """Test adding an existing key returns False"""
        result = service.add_key("existing_key")

        assert result is False

    def test_add_existing_key_logs_warning(self, service):
        """Test adding an existing key logs warning"""
        with patch("backend.app.services.api_key_auth.logger") as mock_logger:
            service.add_key("existing_key")

            call_args = mock_logger.warning.call_args[0][0]
            assert "Attempt to add existing API key" in call_args

    def test_add_key_logs_success(self, service):
        """Test adding a key logs success"""
        with patch("backend.app.services.api_key_auth.logger") as mock_logger:
            service.add_key("new_key", role="developer")

            call_args = mock_logger.info.call_args[0][0]
            assert "Added new API key" in call_args
            assert "developer" in call_args

    def test_add_key_with_custom_permissions(self, service):
        """Test adding a key with custom permissions"""
        service.add_key("custom_key", permissions=["read", "write", "delete"])

        assert service.valid_keys["custom_key"]["permissions"] == ["read", "write", "delete"]

    def test_add_key_with_none_permissions(self, service):
        """Test adding a key with None permissions uses default"""
        service.add_key("new_key", permissions=None)

        assert service.valid_keys["new_key"]["permissions"] == ["read"]


# ============================================================================
# Test remove_key Method
# ============================================================================


class TestRemoveKey:
    """Test suite for remove_key method"""

    @pytest.fixture
    def service(self):
        """Create APIKeyAuth service for testing"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key_to_remove,key_to_keep"

            from backend.app.services.api_key_auth import APIKeyAuth

            return APIKeyAuth()

    def test_remove_key_success(self, service):
        """Test removing an existing key successfully"""
        result = service.remove_key("key_to_remove")

        assert result is True
        assert "key_to_remove" not in service.valid_keys
        assert "key_to_remove" not in service.key_stats

    def test_remove_key_preserves_other_keys(self, service):
        """Test removing a key preserves other keys"""
        service.remove_key("key_to_remove")

        assert "key_to_keep" in service.valid_keys
        assert "key_to_keep" in service.key_stats

    def test_remove_nonexistent_key_fails(self, service):
        """Test removing a non-existent key returns False"""
        result = service.remove_key("nonexistent_key")

        assert result is False

    def test_remove_nonexistent_key_logs_warning(self, service):
        """Test removing a non-existent key logs warning"""
        with patch("backend.app.services.api_key_auth.logger") as mock_logger:
            service.remove_key("nonexistent_key")

            call_args = mock_logger.warning.call_args[0][0]
            assert "Attempt to remove non-existent API key" in call_args

    def test_remove_key_logs_success(self, service):
        """Test removing a key logs success"""
        with patch("backend.app.services.api_key_auth.logger") as mock_logger:
            service.remove_key("key_to_remove")

            call_args = mock_logger.info.call_args[0][0]
            assert "Removed API key" in call_args

    def test_remove_key_after_usage(self, service):
        """Test removing a key that has been used"""
        service.validate_api_key("key_to_remove")
        result = service.remove_key("key_to_remove")

        assert result is True
        assert "key_to_remove" not in service.valid_keys


# ============================================================================
# Test Edge Cases and Integration
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases and integration scenarios"""

    def test_add_and_validate_new_key(self):
        """Test adding a key and then validating it"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "initial_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()
            service.add_key("dynamic_key", role="dynamic", permissions=["all"])

            result = service.validate_api_key("dynamic_key")

            assert result is not None
            assert result["role"] == "dynamic"
            assert result["permissions"] == ["all"]

    def test_remove_and_validate_key(self):
        """Test validating a removed key fails"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "temp_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()
            service.remove_key("temp_key")

            result = service.validate_api_key("temp_key")

            assert result is None

    def test_stats_after_add_remove_operations(self):
        """Test service stats reflect add/remove operations"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            # Initial stats
            stats = service.get_service_stats()
            assert stats["total_keys"] == 2

            # Add key
            service.add_key("key3")
            stats = service.get_service_stats()
            assert stats["total_keys"] == 3

            # Remove key
            service.remove_key("key1")
            stats = service.get_service_stats()
            assert stats["total_keys"] == 2

    def test_usage_tracking_across_operations(self):
        """Test usage tracking works correctly across operations"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "tracked_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            # Use key multiple times
            service.validate_api_key("tracked_key")
            service.validate_api_key("tracked_key")

            stats = service.get_service_stats()
            assert stats["total_usage"] == 2
            assert stats["key_usage"]["tracked_key"]["usage_count"] == 2

    def test_concurrent_key_operations(self):
        """Test multiple operations on different keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2,key3"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            # Validate different keys
            service.validate_api_key("key1")
            service.validate_api_key("key2")
            service.validate_api_key("key1")

            assert service.key_stats["key1"]["usage_count"] == 2
            assert service.key_stats["key2"]["usage_count"] == 1
            assert service.key_stats["key3"]["usage_count"] == 0

    def test_case_sensitivity_in_admin_detection(self):
        """Test admin role detection is case-insensitive"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "ADMIN_key,Secret_KEY,AdMiN_test"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            # All should be detected as admin due to case-insensitive check
            assert service.valid_keys["ADMIN_key"]["role"] == "admin"
            assert service.valid_keys["Secret_KEY"]["role"] == "admin"
            assert service.valid_keys["AdMiN_test"]["role"] == "admin"

    def test_long_api_key(self):
        """Test handling of very long API keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            long_key = "a" * 100
            mock_settings.api_keys = long_key

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()
            result = service.validate_api_key(long_key)

            assert result is not None
            assert result["id"] == f"api_key_{long_key[:8]}"

    def test_special_characters_in_key(self):
        """Test handling of special characters in API keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            special_key = "test-key_123!@#"
            mock_settings.api_keys = special_key

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()
            result = service.validate_api_key(special_key)

            assert result is not None

    def test_get_key_info_vs_validate(self):
        """Test get_key_info returns same info as validate but without side effects"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "test_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()

            # Get info (should not increment)
            info = service.get_key_info("test_key")
            assert service.key_stats["test_key"]["usage_count"] == 0

            # Validate (should increment)
            result = service.validate_api_key("test_key")
            assert service.key_stats["test_key"]["usage_count"] == 1

            # Verify info matches
            assert info["role"] == result["role"]
            assert info["permissions"] == result["permissions"]

    def test_empty_service_stats(self):
        """Test service stats with no keys"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = ""

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()
            stats = service.get_service_stats()

            assert stats["total_keys"] == 0
            assert stats["total_usage"] == 0
            assert stats["key_usage"] == {}

    def test_metadata_structure_completeness(self):
        """Test that metadata includes all expected fields"""
        with patch("backend.app.services.api_key_auth.settings") as mock_settings:
            mock_settings.api_keys = "metadata_test_key"

            from backend.app.services.api_key_auth import APIKeyAuth

            service = APIKeyAuth()
            result = service.validate_api_key("metadata_test_key")

            metadata = result["metadata"]
            assert "key_created_at" in metadata
            assert "key_description" in metadata
            assert "usage_count" in metadata
            assert "last_used" in metadata
            assert metadata["key_created_at"].endswith("Z")
            assert metadata["usage_count"] > 0
            assert metadata["last_used"] is not None
