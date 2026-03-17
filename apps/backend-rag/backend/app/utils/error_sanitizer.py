"""
Error sanitization utilities to prevent information leakage.

Ensures that sensitive information doesn't leak through error messages or logs.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Patterns that might indicate sensitive data (bearer before token - more specific first)
SENSITIVE_PATTERNS = [
    re.compile(r"password[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"passwd[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"pwd[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"secret[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"bearer\s+\S+", re.IGNORECASE),  # Before token - matches "bearer abc123"
    re.compile(r"token[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"api[_-]?key[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"auth[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"basic\s+[a-zA-Z0-9+/=]+", re.IGNORECASE),
    re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key ID pattern
    re.compile(r"[0-9a-f]{32}"),  # Generic 32-char hex (API keys)
    re.compile(r"[0-9a-f]{40}"),  # Generic 40-char hex (tokens)
]

# Database-related patterns to hide internal details
DB_ERROR_PATTERNS = [
    "Pool",
    "asyncpg",
    "connection pool",
    "database connection",
    "postgresql",
    "sqlite",
    "mysql",
]


def sanitize_error_message(
    error: Exception | str,
    max_length: int = 200,
    allow_type: bool = True,
) -> str:
    """
    Sanitize an error message to remove sensitive information.

    Args:
        error: The exception or error string to sanitize
        max_length: Maximum length of the sanitized message
        allow_type: Whether to include the exception type

    Returns:
        Sanitized error message safe for external display
    """
    if isinstance(error, Exception):
        error_type = type(error).__name__ if allow_type else "Error"
        try:
            message = str(error)
        except Exception:
            message = "An error occurred"
    else:
        error_type = "Error"
        message = str(error)

    # Check for database-related errors
    message_lower = message.lower()
    for pattern in DB_ERROR_PATTERNS:
        if pattern.lower() in message_lower:
            return f"{error_type}: Database service temporarily unavailable"

    # Remove sensitive patterns
    for pattern in SENSITIVE_PATTERNS:
        message = pattern.sub("[REDACTED]", message)

    # Truncate if too long
    if len(message) > max_length:
        message = message[: max_length - 3] + "..."

    return f"{error_type}: {message}" if allow_type else message


def safe_log_message(
    message: str,
    _level: int = logging.INFO,
    **kwargs: Any,
) -> str:
    """
    Create a sanitized version of a message safe for logging.

    Args:
        message: Original message
        level: Log level (determines sanitization strictness)
        **kwargs: Additional context to include (will be sanitized)

    Returns:
        Sanitized message
    """
    # Sanitize the main message
    sanitized = message
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)

    # Sanitize kwargs
    safe_kwargs = {}
    for key, value in kwargs.items():
        value_str = str(value)
        for pattern in SENSITIVE_PATTERNS:
            value_str = pattern.sub("[REDACTED]", value_str)
        safe_kwargs[key] = value_str

    return sanitized


def create_safe_error_response(
    error: Exception,
    correlation_id: str | None = None,
    include_type: bool = True,
    generic_message: str | None = None,
) -> dict[str, Any]:
    """
    Create a safe error response dictionary for API responses.

    Args:
        error: The exception that occurred
        correlation_id: Optional correlation ID for tracking
        include_type: Whether to include error type
        generic_message: Override with a generic message

    Returns:
        Dictionary safe for JSON serialization
    """
    error_type = type(error).__name__ if include_type else "Error"

    detail = generic_message or sanitize_error_message(error, allow_type=False)

    response: dict[str, Any] = {
        "detail": detail,
        "error_type": error_type,
    }

    if correlation_id:
        response["correlation_id"] = correlation_id

    return response


def truncate_for_logging(
    value: Any,
    max_length: int = 500,
    suffix: str = "...",
) -> str:
    """
    Truncate a value for safe logging.

    Args:
        value: Value to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string representation
    """
    try:
        str_value = repr(value)
    except Exception:
        str_value = str(value)

    if len(str_value) > max_length:
        return str_value[: max_length - len(suffix)] + suffix

    return str_value
