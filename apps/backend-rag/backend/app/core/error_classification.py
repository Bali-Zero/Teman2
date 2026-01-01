"""
Error Classification System

Provides standardized error classification (transient vs permanent) and
error handling utilities for the NUZANTARA platform.
"""

import logging
from enum import Enum
from typing import Any

import asyncpg
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for classification."""

    TRANSIENT = "transient"  # Temporary errors that may resolve
    PERMANENT = "permanent"  # Errors that won't resolve without intervention
    CLIENT_ERROR = "client_error"  # Client-side errors (4xx)
    SERVER_ERROR = "server_error"  # Server-side errors (5xx)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"  # Non-critical, can continue
    MEDIUM = "medium"  # Degraded functionality
    HIGH = "high"  # Critical, requires attention
    CRITICAL = "critical"  # System failure


class ErrorClassifier:
    """
    Classifies errors into categories for appropriate handling.

    Transient errors should be retried.
    Permanent errors should fail fast.
    """

    # Transient error patterns
    TRANSIENT_ERROR_PATTERNS = [
        "connection",
        "timeout",
        "network",
        "temporary",
        "unavailable",
        "503",
        "502",
        "429",
        "rate limit",
        "quota",
        "resource exhausted",
        "service unavailable",
        "deadline exceeded",
    ]

    # Permanent error patterns
    PERMANENT_ERROR_PATTERNS = [
        "not found",
        "invalid",
        "unauthorized",
        "forbidden",
        "400",
        "401",
        "403",
        "404",
        "validation",
        "syntax",
        "type error",
        "attribute error",
    ]

    @classmethod
    def classify_error(cls, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """
        Classify an error into category and severity.

        Args:
            error: Exception to classify

        Returns:
            Tuple of (ErrorCategory, ErrorSeverity)
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # Database errors
        if isinstance(error, asyncpg.PostgresError):
            if isinstance(error, (asyncpg.ConnectionDoesNotExistError, asyncpg.InterfaceError)):
                return (ErrorCategory.TRANSIENT, ErrorSeverity.HIGH)
            elif isinstance(error, (asyncpg.UniqueViolationError, asyncpg.ForeignKeyViolationError)):
                return (ErrorCategory.PERMANENT, ErrorSeverity.MEDIUM)
            else:
                return (ErrorCategory.TRANSIENT, ErrorSeverity.MEDIUM)

        # Google API errors
        if isinstance(error, ResourceExhausted):
            return (ErrorCategory.TRANSIENT, ErrorSeverity.MEDIUM)
        if isinstance(error, ServiceUnavailable):
            return (ErrorCategory.TRANSIENT, ErrorSeverity.HIGH)

        # HTTP errors (from httpx or similar)
        if hasattr(error, "status_code"):
            status = error.status_code
            if 400 <= status < 500:
                return (ErrorCategory.CLIENT_ERROR, ErrorSeverity.MEDIUM)
            elif status >= 500:
                return (ErrorCategory.TRANSIENT, ErrorSeverity.HIGH)

        # Pattern-based classification
        if any(pattern in error_msg for pattern in cls.TRANSIENT_ERROR_PATTERNS):
            return (ErrorCategory.TRANSIENT, ErrorSeverity.MEDIUM)

        if any(pattern in error_msg for pattern in cls.PERMANENT_ERROR_PATTERNS):
            return (ErrorCategory.PERMANENT, ErrorSeverity.MEDIUM)

        # Default: treat unknown errors as transient (safer for retry)
        return (ErrorCategory.TRANSIENT, ErrorSeverity.MEDIUM)

    @classmethod
    def is_retryable(cls, error: Exception) -> bool:
        """
        Determine if an error should be retried.

        Args:
            error: Exception to check

        Returns:
            True if error is retryable (transient), False otherwise
        """
        category, _ = cls.classify_error(error)
        return category == ErrorCategory.TRANSIENT

    @classmethod
    def should_alert(cls, error: Exception) -> bool:
        """
        Determine if an error should trigger an alert.

        Args:
            error: Exception to check

        Returns:
            True if error should trigger alert
        """
        _, severity = cls.classify_error(error)
        return severity in (ErrorSeverity.HIGH, ErrorSeverity.CRITICAL)


def get_error_context(error: Exception, **kwargs: Any) -> dict[str, Any]:
    """
    Extract structured context from an error.

    Args:
        error: Exception to extract context from
        **kwargs: Additional context to include

    Returns:
        Dictionary with error context
    """
    context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "error_module": getattr(type(error), "__module__", "unknown"),
    }

    # Add classification
    category, severity = ErrorClassifier.classify_error(error)
    context["error_category"] = category.value
    context["error_severity"] = severity.value
    context["is_retryable"] = ErrorClassifier.is_retryable(error)

    # Add additional context
    context.update(kwargs)

    return context

