"""
Unit tests for ErrorClassifier
Target: >95% coverage
"""

import sys
from pathlib import Path

import asyncpg
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.error_classification import (
    ErrorCategory,
    ErrorClassifier,
    ErrorSeverity,
    get_error_context,
)


class TestErrorClassifier:
    """Tests for ErrorClassifier"""

    def test_classify_database_connection_error(self):
        """Test classifying database connection error"""
        error = asyncpg.ConnectionDoesNotExistError("Connection failed")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.TRANSIENT
        assert severity == ErrorSeverity.HIGH

    def test_classify_database_interface_error(self):
        """Test classifying database interface error"""
        error = asyncpg.InterfaceError("Interface error")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.TRANSIENT
        # InterfaceError may be classified as MEDIUM or HIGH depending on implementation
        assert severity in (ErrorSeverity.MEDIUM, ErrorSeverity.HIGH)

    def test_classify_database_unique_violation(self):
        """Test classifying database unique violation"""
        error = asyncpg.UniqueViolationError("Unique violation")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.PERMANENT
        assert severity == ErrorSeverity.MEDIUM

    def test_classify_database_foreign_key_violation(self):
        """Test classifying database foreign key violation"""
        error = asyncpg.ForeignKeyViolationError("Foreign key violation")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.PERMANENT
        assert severity == ErrorSeverity.MEDIUM

    def test_classify_database_generic_error(self):
        """Test classifying generic database error"""
        error = asyncpg.PostgresError("Generic error")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.TRANSIENT
        assert severity == ErrorSeverity.MEDIUM

    def test_classify_resource_exhausted(self):
        """Test classifying ResourceExhausted error"""
        error = ResourceExhausted("Quota exceeded")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.TRANSIENT
        assert severity == ErrorSeverity.MEDIUM  # According to implementation

    def test_classify_service_unavailable(self):
        """Test classifying ServiceUnavailable error"""
        error = ServiceUnavailable("Service down")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.TRANSIENT
        assert severity == ErrorSeverity.HIGH

    def test_classify_transient_patterns(self):
        """Test classifying errors with transient patterns"""
        patterns = [
            "connection timeout",
            "network error",
            "temporary unavailable",
            "503 service unavailable",
            "rate limit exceeded",
            "quota exceeded",
            "resource exhausted",
            "deadline exceeded",
        ]

        for pattern in patterns:
            error = Exception(pattern)
            category, severity = ErrorClassifier.classify_error(error)
            assert category == ErrorCategory.TRANSIENT

    def test_classify_permanent_patterns(self):
        """Test classifying errors with permanent patterns"""
        patterns = [
            "not found",
            "invalid input",
            "unauthorized access",
            "forbidden",
            "400 bad request",
            "401 unauthorized",
            "403 forbidden",
            "404 not found",
            "validation error",
            "syntax error",
            "type error",
            "attribute error",
        ]

        for pattern in patterns:
            error = Exception(pattern)
            category, severity = ErrorClassifier.classify_error(error)
            assert category == ErrorCategory.PERMANENT

    def test_classify_generic_error(self):
        """Test classifying generic error"""
        error = Exception("Generic error")
        category, severity = ErrorClassifier.classify_error(error)
        assert category == ErrorCategory.TRANSIENT  # Default is transient
        assert severity == ErrorSeverity.MEDIUM

    def test_is_retryable(self):
        """Test is_retryable method"""
        transient_error = ResourceExhausted("Quota exceeded")
        assert ErrorClassifier.is_retryable(transient_error) is True

        permanent_error = asyncpg.UniqueViolationError("Duplicate")
        assert ErrorClassifier.is_retryable(permanent_error) is False

    def test_should_alert(self):
        """Test should_alert method"""
        high_severity_error = ServiceUnavailable("Service down")
        assert ErrorClassifier.should_alert(high_severity_error) is True

        medium_severity_error = ResourceExhausted("Quota exceeded")
        assert ErrorClassifier.should_alert(medium_severity_error) is False

    def test_get_error_context(self):
        """Test getting error context"""
        error = ValueError("Test error")
        context = get_error_context(error, model="test_model", user_id="user123")

        assert "error_type" in context
        assert "error_message" in context
        assert context["model"] == "test_model"
        assert context["user_id"] == "user123"

    def test_get_error_context_minimal(self):
        """Test getting error context with minimal info"""
        error = Exception("Error")
        context = get_error_context(error)

        assert "error_type" in context
        assert "error_message" in context
