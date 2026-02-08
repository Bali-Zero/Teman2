"""
Tests for error_sanitizer utility module.
"""

from backend.app.utils.error_sanitizer import (
    create_safe_error_response,
    sanitize_error_message,
    truncate_for_logging,
)


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message function."""

    def test_sanitizes_database_errors(self):
        """Test that database-related errors are sanitized."""
        error = Exception("Pool timeout asyncpg connection failed")
        result = sanitize_error_message(error)
        assert "Pool" not in result
        assert "asyncpg" not in result
        assert "Database service temporarily unavailable" in result

    def test_sanitizes_password_in_message(self):
        """Test that passwords are redacted."""
        error = Exception("Login failed: password=secret123")
        result = sanitize_error_message(error)
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_sanitizes_token_in_message(self):
        """Test that tokens are redacted."""
        error = Exception("Invalid token: bearer abc123xyz")
        result = sanitize_error_message(error)
        assert "abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_truncates_long_messages(self):
        """Test that long messages are truncated."""
        error = Exception("x" * 500)
        result = sanitize_error_message(error, max_length=100)
        assert len(result) <= 150  # Allow for "Error: " prefix and "..."
        assert "..." in result

    def test_includes_error_type_by_default(self):
        """Test that error type is included by default."""
        error = ValueError("Something went wrong")
        result = sanitize_error_message(error)
        assert "ValueError" in result

    def test_omits_error_type_when_disabled(self):
        """Test that error type can be omitted."""
        error = ValueError("Something went wrong")
        result = sanitize_error_message(error, allow_type=False)
        assert "ValueError" not in result

    def test_handles_string_input(self):
        """Test that string input is handled."""
        result = sanitize_error_message("Raw error message")
        assert "Raw error message" in result


class TestCreateSafeErrorResponse:
    """Tests for create_safe_error_response function."""

    def test_includes_error_type(self):
        """Test that error type is included."""
        error = ValueError("Test error")
        response = create_safe_error_response(error)
        assert response["error_type"] == "ValueError"

    def test_includes_correlation_id(self):
        """Test that correlation ID is included when provided."""
        error = Exception("Test")
        response = create_safe_error_response(error, correlation_id="abc-123")
        assert response["correlation_id"] == "abc-123"

    def test_uses_generic_message_when_provided(self):
        """Test that generic message can override error message."""
        error = Exception("Sensitive details")
        response = create_safe_error_response(error, generic_message="An error occurred")
        assert response["detail"] == "An error occurred"

    def test_omits_correlation_id_when_not_provided(self):
        """Test that correlation ID is omitted when not provided."""
        error = Exception("Test")
        response = create_safe_error_response(error)
        assert "correlation_id" not in response


class TestTruncateForLogging:
    """Tests for truncate_for_logging function."""

    def test_truncates_long_values(self):
        """Test that long values are truncated."""
        value = "x" * 1000
        result = truncate_for_logging(value, max_length=100)
        assert len(result) <= 103  # 100 + len("...")
        assert "..." in result

    def test_does_not_truncate_short_values(self):
        """Test that short values are not truncated."""
        value = "Short message"
        result = truncate_for_logging(value, max_length=100)
        assert result == "'Short message'"

    def test_uses_custom_suffix(self):
        """Test that custom suffix can be used."""
        value = "x" * 200
        result = truncate_for_logging(value, max_length=50, suffix="[more]")
        assert "[more]" in result
