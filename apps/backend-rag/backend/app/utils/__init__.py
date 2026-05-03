"""
Application utilities package.

Provides common utilities for:
- Path validation and sanitization
- Error sanitization for safe logging/responses
- JSON utilities
- Internal API authentication
"""

from backend.app.utils.error_sanitizer import (
    create_safe_error_response,
    safe_log_message,
    sanitize_error_message,
    truncate_for_logging,
)
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.app.utils.json_utils import to_jsonb
from backend.app.utils.path_validator import (
    sanitize_filename,
    validate_path,
)

__all__ = [
    # Path validation
    "validate_path",
    "sanitize_filename",
    # Error sanitization
    "sanitize_error_message",
    "safe_log_message",
    "create_safe_error_response",
    "truncate_for_logging",
    # Auth
    "verify_internal_api_key",
    # JSON
    "to_jsonb",
]
