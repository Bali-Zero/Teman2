"""
Article Composer Services Package

Best Practices 2026 Implementation:
- Retry logic with exponential backoff
- Circuit breaker
- Caching
- Structured error handling
- Input validation
"""

from backend.services.article_composer.cache import cache_service
from backend.services.article_composer.claude_client import (
    call_claude_with_retry,
    get_anthropic_client,
)
from backend.services.article_composer.error_handler import (
    APIError,
    ErrorCode,
    handle_anthropic_error,
    handle_json_error,
    handle_validation_error,
    log_error_with_context,
)
from backend.services.article_composer.validators import (
    ComposeRequestValidator,
    sanitize_content,
    validate_category,
)

__all__ = [
    # Client
    "get_anthropic_client",
    "call_claude_with_retry",
    # Cache
    "cache_service",
    # Error handling
    "APIError",
    "ErrorCode",
    "handle_anthropic_error",
    "handle_json_error",
    "handle_validation_error",
    "log_error_with_context",
    # Validation
    "ComposeRequestValidator",
    "sanitize_content",
    "validate_category",
]
