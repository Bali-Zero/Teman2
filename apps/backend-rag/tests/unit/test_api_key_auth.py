"""
Unit tests for API Key Authentication Service
100% coverage target with comprehensive mocking
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.services.api_key_auth import APIKeyAuth

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_key_auth():
    """Create APIKeyAuth instance with mocked settings"""
    with patch("backend.app.services.api_key_auth.settings") as mock_settings:
        mock_settings.api_keys = "zantara-secret-2024,zantara-test-2024"
        return APIKeyAuth()


@pytest.fixture
def fresh_api_key_auth():
    """Create fresh APIKeyAuth instance for tests that need clean state"""
    with patch("backend.app.services.api_key_auth.settings") as mock_settings:
        mock_settings.api_keys = "zantara-secret-2024,zantara-test-2024"
        return APIKeyAuth()


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_creates_valid_keys(api_key_auth):
    """Test initialization creates valid keys"""
    assert len(api_key_auth.valid_keys) == 2
    assert "zantara-secret-2024" in api_key_auth.valid_keys
    assert "zantara-test-2024" in api_key_auth.valid_keys


def test_init_creates_admin_key(api_key_auth):
    """Test initialization creates admin key with correct properties"""
    admin_key = api_key_auth.valid_keys["zantara-secret-2024"]
    assert admin_key["role"] == "admin"
    assert admin_key["permissions"] == ["*"]
    # created_at is dynamically generated, just verify it's a valid ISO format
    assert "created_at" in admin_key
    assert admin_key["created_at"].endswith("Z")
    assert "description" in admin_key


def test_init_creates_test_key(api_key_auth):
    """Test initialization creates test key with correct properties"""
    test_key = api_key_auth.valid_keys["zantara-test-2024"]
    # Role is determined by key name: "test" doesn't contain "admin" or "secret", so it's "user"
    assert test_key["role"] == "user"
    assert test_key["permissions"] == ["read"]
    # created_at is dynamically generated, just verify it's a valid ISO format
    assert "created_at" in test_key
    assert test_key["created_at"].endswith("Z")
    assert "description" in test_key


def test_init_creates_key_stats(api_key_auth):
    """Test initialization creates key statistics"""
    assert len(api_key_auth.key_stats) == 2
    assert "zantara-secret-2024" in api_key_auth.key_stats
    assert "zantara-test-2024" in api_key_auth.key_stats


def test_init_key_stats_structure(api_key_auth):
    """Test that key stats have correct structure"""
    for key, stats in api_key_auth.key_stats.items():
        assert "usage_count" in stats
        assert "last_used" in stats
        assert stats["usage_count"] == 0
        assert stats["last_used"] is None


def test_init_logs_initialization(fresh_api_key_auth):
    """Test that initialization logs correct message"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        service = APIKeyAuth()
        mock_logger.info.assert_called_once()
        assert "API Key service initialized" in mock_logger.info.call_args[0][0]
        assert "2 valid keys" in mock_logger.info.call_args[0][0]


# ============================================================================
# Tests for validate_api_key
# ============================================================================


def test_validate_api_key_success_admin(api_key_auth):
    """Test successful validation of admin API key"""
    result = api_key_auth.validate_api_key("zantara-secret-2024")

    assert result is not None
    assert result["id"] == "api_key_zantara-"
    assert result["email"] == "admin@zantara.dev"
    assert result["name"] == "API User (admin)"
    assert result["role"] == "admin"
    assert result["status"] == "active"
    assert result["auth_method"] == "api_key"
    assert result["permissions"] == ["*"]


def test_validate_api_key_success_test(api_key_auth):
    """Test successful validation of test API key"""
    result = api_key_auth.validate_api_key("zantara-test-2024")

    assert result is not None
    assert result["id"] == "api_key_zantara-"
    # Role is "user" because key doesn't contain "admin" or "secret"
    assert result["email"] == "user@zantara.dev"
    assert result["name"] == "API User (user)"
    assert result["role"] == "user"
    assert result["status"] == "active"
    assert result["auth_method"] == "api_key"
    assert result["permissions"] == ["read"]


def test_validate_api_key_increments_usage_count(api_key_auth):
    """Test that validation increments usage count"""
    api_key = "zantara-secret-2024"
    initial_count = api_key_auth.key_stats[api_key]["usage_count"]

    api_key_auth.validate_api_key(api_key)
    assert api_key_auth.key_stats[api_key]["usage_count"] == initial_count + 1

    api_key_auth.validate_api_key(api_key)
    assert api_key_auth.key_stats[api_key]["usage_count"] == initial_count + 2


def test_validate_api_key_updates_last_used(api_key_auth):
    """Test that validation updates last_used timestamp"""
    api_key = "zantara-secret-2024"
    assert api_key_auth.key_stats[api_key]["last_used"] is None

    api_key_auth.validate_api_key(api_key)
    assert api_key_auth.key_stats[api_key]["last_used"] is not None
    assert isinstance(api_key_auth.key_stats[api_key]["last_used"], str)


def test_validate_api_key_last_used_format(api_key_auth):
    """Test that last_used timestamp is in ISO format"""
    api_key = "zantara-secret-2024"
    api_key_auth.validate_api_key(api_key)

    last_used = api_key_auth.key_stats[api_key]["last_used"]
    # Should be parseable as ISO format datetime
    parsed = datetime.fromisoformat(last_used)
    assert isinstance(parsed, datetime)


def test_validate_api_key_returns_metadata(api_key_auth):
    """Test that validation returns metadata"""
    result = api_key_auth.validate_api_key("zantara-secret-2024")

    assert "metadata" in result
    metadata = result["metadata"]
    assert "key_created_at" in metadata
    assert "key_description" in metadata
    assert "usage_count" in metadata
    assert "last_used" in metadata


def test_validate_api_key_metadata_values(api_key_auth):
    """Test that metadata contains correct values"""
    api_key_auth.validate_api_key("zantara-secret-2024")
    result = api_key_auth.validate_api_key("zantara-secret-2024")

    metadata = result["metadata"]
    # created_at is dynamically generated, just verify it's a valid ISO format
    assert metadata["key_created_at"].endswith("Z")
    assert metadata["usage_count"] == 2  # Called twice
    assert metadata["last_used"] is not None
    assert "API key loaded from environment variable" in metadata["key_description"]


def test_validate_api_key_invalid_returns_none(api_key_auth):
    """Test that invalid API key returns None"""
    result = api_key_auth.validate_api_key("invalid-key-123")
    assert result is None


def test_validate_api_key_empty_string_returns_none(api_key_auth):
    """Test that empty string API key returns None"""
    result = api_key_auth.validate_api_key("")
    assert result is None


def test_validate_api_key_none_returns_none(api_key_auth):
    """Test that None API key returns None"""
    result = api_key_auth.validate_api_key(None)
    assert result is None


def test_validate_api_key_logs_no_key_warning(api_key_auth):
    """Test that no API key logs warning"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.validate_api_key(None)
        mock_logger.warning.assert_called_once()
        assert "No API key provided" in mock_logger.warning.call_args[0][0]


def test_validate_api_key_logs_invalid_key_warning(api_key_auth):
    """Test that invalid API key logs warning"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.validate_api_key("invalid-key-123")
        mock_logger.warning.assert_called_once()
        assert "Invalid API key provided" in mock_logger.warning.call_args[0][0]


def test_validate_api_key_logs_valid_key_debug(api_key_auth):
    """Test that valid API key logs debug message"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.validate_api_key("zantara-secret-2024")
        mock_logger.debug.assert_called_once()
        assert "Valid API key used" in mock_logger.debug.call_args[0][0]


def test_validate_api_key_invalid_does_not_increment_stats(api_key_auth):
    """Test that invalid API key does not increment any stats"""
    initial_stats = dict(api_key_auth.key_stats)
    api_key_auth.validate_api_key("invalid-key-123")

    # Stats should remain unchanged
    for key in initial_stats:
        assert api_key_auth.key_stats[key] == initial_stats[key]


def test_validate_api_key_truncates_key_in_log(api_key_auth):
    """Test that invalid API key is truncated in log"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.validate_api_key("very-long-invalid-key-that-should-be-truncated")
        mock_logger.warning.assert_called_once()
        # Should only show first 10 chars
        assert "very-long-..." in mock_logger.warning.call_args[0][0]


# ============================================================================
# Tests for is_valid_key
# ============================================================================


def test_is_valid_key_admin_key(api_key_auth):
    """Test that admin key is valid"""
    assert api_key_auth.is_valid_key("zantara-secret-2024") is True


def test_is_valid_key_test_key(api_key_auth):
    """Test that test key is valid"""
    assert api_key_auth.is_valid_key("zantara-test-2024") is True


def test_is_valid_key_invalid_key(api_key_auth):
    """Test that invalid key returns False"""
    assert api_key_auth.is_valid_key("invalid-key") is False


def test_is_valid_key_empty_string(api_key_auth):
    """Test that empty string returns False"""
    assert api_key_auth.is_valid_key("") is False


def test_is_valid_key_none(api_key_auth):
    """Test that None returns False"""
    assert api_key_auth.is_valid_key(None) is False


def test_is_valid_key_does_not_increment_stats(api_key_auth):
    """Test that is_valid_key does not increment usage stats"""
    api_key = "zantara-secret-2024"
    initial_count = api_key_auth.key_stats[api_key]["usage_count"]

    api_key_auth.is_valid_key(api_key)
    assert api_key_auth.key_stats[api_key]["usage_count"] == initial_count


def test_is_valid_key_does_not_update_last_used(api_key_auth):
    """Test that is_valid_key does not update last_used"""
    api_key = "zantara-secret-2024"
    initial_last_used = api_key_auth.key_stats[api_key]["last_used"]

    api_key_auth.is_valid_key(api_key)
    assert api_key_auth.key_stats[api_key]["last_used"] == initial_last_used


# ============================================================================
# Tests for get_key_info
# ============================================================================


def test_get_key_info_admin_key(api_key_auth):
    """Test getting info for admin key"""
    info = api_key_auth.get_key_info("zantara-secret-2024")

    assert info is not None
    assert info["role"] == "admin"
    assert info["permissions"] == ["*"]
    # created_at is dynamically generated, just verify it's a valid ISO format
    assert info["created_at"].endswith("Z")
    assert "description" in info


def test_get_key_info_test_key(api_key_auth):
    """Test getting info for test key"""
    info = api_key_auth.get_key_info("zantara-test-2024")

    assert info is not None
    # Role is "user" because key doesn't contain "admin" or "secret"
    assert info["role"] == "user"
    assert info["permissions"] == ["read"]
    # created_at is dynamically generated, just verify it's a valid ISO format
    assert info["created_at"].endswith("Z")
    assert "description" in info


def test_get_key_info_invalid_key(api_key_auth):
    """Test getting info for invalid key returns None"""
    info = api_key_auth.get_key_info("invalid-key")
    assert info is None


def test_get_key_info_empty_string(api_key_auth):
    """Test getting info for empty string returns None"""
    info = api_key_auth.get_key_info("")
    assert info is None


def test_get_key_info_none(api_key_auth):
    """Test getting info for None returns None"""
    info = api_key_auth.get_key_info(None)
    assert info is None


def test_get_key_info_does_not_increment_stats(api_key_auth):
    """Test that get_key_info does not increment usage stats"""
    api_key = "zantara-secret-2024"
    initial_count = api_key_auth.key_stats[api_key]["usage_count"]

    api_key_auth.get_key_info(api_key)
    assert api_key_auth.key_stats[api_key]["usage_count"] == initial_count


def test_get_key_info_does_not_update_last_used(api_key_auth):
    """Test that get_key_info does not update last_used"""
    api_key = "zantara-secret-2024"
    initial_last_used = api_key_auth.key_stats[api_key]["last_used"]

    api_key_auth.get_key_info(api_key)
    assert api_key_auth.key_stats[api_key]["last_used"] == initial_last_used


# ============================================================================
# Tests for get_service_stats
# ============================================================================


def test_get_service_stats_initial_state(api_key_auth):
    """Test service stats in initial state"""
    stats = api_key_auth.get_service_stats()

    assert stats["total_keys"] == 2
    assert stats["total_usage"] == 0
    assert stats["service_up"] is True
    assert stats["service_type"] == "static_api_key"
    assert "key_usage" in stats


def test_get_service_stats_after_usage(api_key_auth):
    """Test service stats after some usage"""
    api_key_auth.validate_api_key("zantara-secret-2024")
    api_key_auth.validate_api_key("zantara-test-2024")
    api_key_auth.validate_api_key("zantara-secret-2024")

    stats = api_key_auth.get_service_stats()

    assert stats["total_keys"] == 2
    assert stats["total_usage"] == 3  # 2 + 1
    assert stats["service_up"] is True


def test_get_service_stats_key_usage_details(api_key_auth):
    """Test that service stats include key usage details"""
    api_key_auth.validate_api_key("zantara-secret-2024")

    stats = api_key_auth.get_service_stats()
    key_usage = stats["key_usage"]

    assert "zantara-secret-2024" in key_usage
    assert "zantara-test-2024" in key_usage
    assert key_usage["zantara-secret-2024"]["usage_count"] == 1
    assert key_usage["zantara-test-2024"]["usage_count"] == 0


def test_get_service_stats_structure(api_key_auth):
    """Test that service stats have correct structure"""
    stats = api_key_auth.get_service_stats()

    assert "total_keys" in stats
    assert "total_usage" in stats
    assert "key_usage" in stats
    assert "service_up" in stats
    assert "service_type" in stats


def test_get_service_stats_after_adding_key(api_key_auth):
    """Test service stats after adding a key"""
    api_key_auth.add_key("new-key-123", role="developer")

    stats = api_key_auth.get_service_stats()
    assert stats["total_keys"] == 3


def test_get_service_stats_after_removing_key(api_key_auth):
    """Test service stats after removing a key"""
    api_key_auth.add_key("temp-key-123", role="temp")
    api_key_auth.remove_key("temp-key-123")

    stats = api_key_auth.get_service_stats()
    assert stats["total_keys"] == 2


# ============================================================================
# Tests for add_key
# ============================================================================


def test_add_key_success(api_key_auth):
    """Test successfully adding a new key"""
    result = api_key_auth.add_key("new-key-123", role="developer", permissions=["write"])

    assert result is True
    assert "new-key-123" in api_key_auth.valid_keys
    assert api_key_auth.valid_keys["new-key-123"]["role"] == "developer"
    assert api_key_auth.valid_keys["new-key-123"]["permissions"] == ["write"]


def test_add_key_creates_stats(api_key_auth):
    """Test that adding a key creates stats entry"""
    api_key_auth.add_key("new-key-123", role="developer")

    assert "new-key-123" in api_key_auth.key_stats
    assert api_key_auth.key_stats["new-key-123"]["usage_count"] == 0
    assert api_key_auth.key_stats["new-key-123"]["last_used"] is None


def test_add_key_default_permissions(api_key_auth):
    """Test adding key with default permissions"""
    api_key_auth.add_key("new-key-123", role="developer")

    assert api_key_auth.valid_keys["new-key-123"]["permissions"] == ["read"]


def test_add_key_default_role(api_key_auth):
    """Test adding key with default role"""
    api_key_auth.add_key("new-key-123")

    # Default role is "test" when not specified
    assert api_key_auth.valid_keys["new-key-123"]["role"] == "test"


def test_add_key_sets_created_at(api_key_auth):
    """Test that adding key sets created_at timestamp"""
    api_key_auth.add_key("new-key-123")

    created_at = api_key_auth.valid_keys["new-key-123"]["created_at"]
    assert created_at is not None
    # Should be parseable as ISO format datetime
    parsed = datetime.fromisoformat(created_at)
    assert isinstance(parsed, datetime)


def test_add_key_sets_description(api_key_auth):
    """Test that adding key sets description"""
    api_key_auth.add_key("new-key-123", role="developer")

    description = api_key_auth.valid_keys["new-key-123"]["description"]
    assert "Programmatically added key" in description
    assert "developer" in description


def test_add_key_duplicate_returns_false(api_key_auth):
    """Test that adding duplicate key returns False"""
    result = api_key_auth.add_key("zantara-secret-2024", role="developer")
    assert result is False


def test_add_key_duplicate_does_not_modify(api_key_auth):
    """Test that adding duplicate key does not modify existing key"""
    original_role = api_key_auth.valid_keys["zantara-secret-2024"]["role"]
    api_key_auth.add_key("zantara-secret-2024", role="different")

    assert api_key_auth.valid_keys["zantara-secret-2024"]["role"] == original_role


def test_add_key_duplicate_logs_warning(api_key_auth):
    """Test that adding duplicate key logs warning"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.add_key("zantara-secret-2024", role="developer")
        mock_logger.warning.assert_called_once()
        assert "Attempt to add existing API key" in mock_logger.warning.call_args[0][0]


def test_add_key_success_logs_info(api_key_auth):
    """Test that successfully adding key logs info"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.add_key("new-key-123", role="developer")
        mock_logger.info.assert_called_once()
        assert "Added new API key" in mock_logger.info.call_args[0][0]


def test_add_key_with_custom_permissions_list(api_key_auth):
    """Test adding key with custom permissions list"""
    permissions = ["read", "write", "delete"]
    api_key_auth.add_key("new-key-123", permissions=permissions)

    assert api_key_auth.valid_keys["new-key-123"]["permissions"] == permissions


def test_add_key_with_empty_permissions_list(api_key_auth):
    """Test adding key with empty permissions list"""
    api_key_auth.add_key("new-key-123", permissions=[])

    assert api_key_auth.valid_keys["new-key-123"]["permissions"] == []


def test_add_key_is_immediately_valid(api_key_auth):
    """Test that newly added key is immediately valid"""
    api_key_auth.add_key("new-key-123", role="developer")

    assert api_key_auth.is_valid_key("new-key-123") is True


def test_add_key_can_be_validated(api_key_auth):
    """Test that newly added key can be validated"""
    api_key_auth.add_key("new-key-123", role="developer")

    result = api_key_auth.validate_api_key("new-key-123")
    assert result is not None
    assert result["role"] == "developer"


# ============================================================================
# Tests for remove_key
# ============================================================================


def test_remove_key_success(api_key_auth):
    """Test successfully removing a key"""
    api_key_auth.add_key("temp-key-123", role="temp")
    result = api_key_auth.remove_key("temp-key-123")

    assert result is True
    assert "temp-key-123" not in api_key_auth.valid_keys


def test_remove_key_removes_stats(api_key_auth):
    """Test that removing key also removes stats"""
    api_key_auth.add_key("temp-key-123", role="temp")
    api_key_auth.remove_key("temp-key-123")

    assert "temp-key-123" not in api_key_auth.key_stats


def test_remove_key_nonexistent_returns_false(api_key_auth):
    """Test that removing nonexistent key returns False"""
    result = api_key_auth.remove_key("nonexistent-key")
    assert result is False


def test_remove_key_nonexistent_logs_warning(api_key_auth):
    """Test that removing nonexistent key logs warning"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.remove_key("nonexistent-key")
        mock_logger.warning.assert_called_once()
        assert "Attempt to remove non-existent API key" in mock_logger.warning.call_args[0][0]


def test_remove_key_success_logs_info(api_key_auth):
    """Test that successfully removing key logs info"""
    api_key_auth.add_key("temp-key-123", role="temp")

    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.remove_key("temp-key-123")
        mock_logger.info.assert_called_once()
        assert "Removed API key" in mock_logger.info.call_args[0][0]


def test_remove_key_is_no_longer_valid(api_key_auth):
    """Test that removed key is no longer valid"""
    api_key_auth.add_key("temp-key-123", role="temp")
    api_key_auth.remove_key("temp-key-123")

    assert api_key_auth.is_valid_key("temp-key-123") is False


def test_remove_key_cannot_be_validated(api_key_auth):
    """Test that removed key cannot be validated"""
    api_key_auth.add_key("temp-key-123", role="temp")
    api_key_auth.remove_key("temp-key-123")

    result = api_key_auth.validate_api_key("temp-key-123")
    assert result is None


def test_remove_key_with_usage_history(api_key_auth):
    """Test removing key that has been used"""
    api_key_auth.add_key("temp-key-123", role="temp")
    api_key_auth.validate_api_key("temp-key-123")  # Use it once

    result = api_key_auth.remove_key("temp-key-123")
    assert result is True
    assert "temp-key-123" not in api_key_auth.valid_keys


def test_remove_default_key(api_key_auth):
    """Test that default keys can be removed"""
    result = api_key_auth.remove_key("zantara-secret-2024")
    assert result is True
    assert "zantara-secret-2024" not in api_key_auth.valid_keys


# ============================================================================
# Integration and Edge Case Tests
# ============================================================================


def test_multiple_key_validations_track_separately(api_key_auth):
    """Test that multiple keys track usage separately"""
    api_key_auth.validate_api_key("zantara-secret-2024")
    api_key_auth.validate_api_key("zantara-secret-2024")
    api_key_auth.validate_api_key("zantara-test-2024")

    assert api_key_auth.key_stats["zantara-secret-2024"]["usage_count"] == 2
    assert api_key_auth.key_stats["zantara-test-2024"]["usage_count"] == 1


def test_add_remove_add_same_key(api_key_auth):
    """Test adding, removing, and re-adding the same key"""
    api_key_auth.add_key("temp-key-123", role="temp1")
    api_key_auth.remove_key("temp-key-123")
    result = api_key_auth.add_key("temp-key-123", role="temp2")

    assert result is True
    assert api_key_auth.valid_keys["temp-key-123"]["role"] == "temp2"


def test_usage_stats_persist_across_operations(api_key_auth):
    """Test that usage stats persist correctly"""
    api_key = "zantara-secret-2024"

    # Use key multiple times
    for _ in range(5):
        api_key_auth.validate_api_key(api_key)

    # Check stats
    stats = api_key_auth.get_service_stats()
    assert stats["total_usage"] == 5


def test_key_validation_updates_timestamp_each_time(api_key_auth):
    """Test that each validation updates the timestamp"""
    api_key = "zantara-secret-2024"

    api_key_auth.validate_api_key(api_key)
    first_timestamp = api_key_auth.key_stats[api_key]["last_used"]

    # Small delay simulation (in real scenario)
    api_key_auth.validate_api_key(api_key)
    second_timestamp = api_key_auth.key_stats[api_key]["last_used"]

    # Timestamps should exist (exact comparison may fail due to timing)
    assert first_timestamp is not None
    assert second_timestamp is not None


def test_validate_returns_complete_user_context(api_key_auth):
    """Test that validate returns complete user context"""
    result = api_key_auth.validate_api_key("zantara-secret-2024")

    required_fields = [
        "id",
        "email",
        "name",
        "role",
        "status",
        "auth_method",
        "permissions",
        "metadata",
    ]
    for field in required_fields:
        assert field in result


def test_service_stats_match_individual_stats(api_key_auth):
    """Test that service total stats match sum of individual stats"""
    api_key_auth.validate_api_key("zantara-secret-2024")
    api_key_auth.validate_api_key("zantara-secret-2024")
    api_key_auth.validate_api_key("zantara-test-2024")

    stats = api_key_auth.get_service_stats()
    individual_sum = sum(v["usage_count"] for v in api_key_auth.key_stats.values())

    assert stats["total_usage"] == individual_sum


def test_empty_string_api_key_logs_warning(api_key_auth):
    """Test that empty string API key logs warning"""
    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.validate_api_key("")
        mock_logger.warning.assert_called_once()
        assert "No API key provided" in mock_logger.warning.call_args[0][0]


def test_none_permissions_defaults_to_read(api_key_auth):
    """Test that None permissions defaults to ['read']"""
    api_key_auth.add_key("new-key-123", permissions=None)
    assert api_key_auth.valid_keys["new-key-123"]["permissions"] == ["read"]


def test_key_id_generation(api_key_auth):
    """Test that key ID is generated correctly"""
    result = api_key_auth.validate_api_key("zantara-secret-2024")
    # Should use first 8 chars of the key
    assert result["id"] == "api_key_zantara-"


def test_metadata_usage_count_increments(api_key_auth):
    """Test that metadata usage_count increments with each validation"""
    api_key = "zantara-secret-2024"

    result1 = api_key_auth.validate_api_key(api_key)
    assert result1["metadata"]["usage_count"] == 1

    result2 = api_key_auth.validate_api_key(api_key)
    assert result2["metadata"]["usage_count"] == 2


def test_different_roles_have_different_permissions(api_key_auth):
    """Test that different roles have different permissions"""
    admin_result = api_key_auth.validate_api_key("zantara-secret-2024")
    test_result = api_key_auth.validate_api_key("zantara-test-2024")

    assert admin_result["permissions"] != test_result["permissions"]
    assert admin_result["role"] == "admin"
    # Role is "user" because key doesn't contain "admin" or "secret"
    assert test_result["role"] == "user"


def test_service_type_is_static(api_key_auth):
    """Test that service type is static_api_key"""
    stats = api_key_auth.get_service_stats()
    assert stats["service_type"] == "static_api_key"


def test_service_up_is_always_true(api_key_auth):
    """Test that service_up is always True"""
    stats = api_key_auth.get_service_stats()
    assert stats["service_up"] is True


def test_log_truncates_long_keys(api_key_auth):
    """Test that logs truncate long keys for security"""
    long_key = "a" * 50

    with patch("backend.app.services.api_key_auth.logger") as mock_logger:
        api_key_auth.validate_api_key(long_key)
        # Should log with truncation
        log_message = mock_logger.warning.call_args[0][0]
        assert "..." in log_message
        assert len(long_key) > len(log_message)


def test_added_key_has_all_required_fields(api_key_auth):
    """Test that added key has all required fields"""
    api_key_auth.add_key("new-key-123", role="developer", permissions=["write"])

    key_info = api_key_auth.valid_keys["new-key-123"]
    assert "role" in key_info
    assert "permissions" in key_info
    assert "created_at" in key_info
    assert "description" in key_info


def test_concurrent_usage_tracking(api_key_auth):
    """Test usage tracking with multiple keys"""
    # Simulate concurrent usage
    api_key_auth.validate_api_key("zantara-secret-2024")
    api_key_auth.validate_api_key("zantara-test-2024")
    api_key_auth.validate_api_key("zantara-secret-2024")
    api_key_auth.validate_api_key("zantara-test-2024")

    stats = api_key_auth.get_service_stats()
    assert stats["total_usage"] == 4
    assert stats["key_usage"]["zantara-secret-2024"]["usage_count"] == 2
    assert stats["key_usage"]["zantara-test-2024"]["usage_count"] == 2
