"""
Application utilities package.

Provides common utilities for:
- Path validation and sanitization
- Error sanitization for safe logging/responses
- JSON utilities
- Internal API authentication
"""

from typing import TYPE_CHECKING

from backend.app.utils.error_sanitizer import (
    create_safe_error_response,
    safe_log_message,
    sanitize_error_message,
    truncate_for_logging,
)
from backend.app.utils.json_utils import to_jsonb
from backend.app.utils.path_validator import (
    sanitize_filename,
    validate_path,
)

if TYPE_CHECKING:
    from backend.app.utils.internal_api_auth import verify_internal_api_key

__all__ = [
    "create_safe_error_response",
    "safe_log_message",
    # Error sanitization
    "sanitize_error_message",
    "sanitize_filename",
    # JSON
    "to_jsonb",
    "truncate_for_logging",
    # Path validation
    "validate_path",
    # Auth
    "verify_internal_api_key",
]


def __getattr__(name: str):
    """Lazily resolve ``verify_internal_api_key`` (PEP 562).

    This package's ``__init__`` is a tollbooth: importing ANY leaf module
    under ``backend.app.utils`` (e.g. ``backend.app.utils.service_accounts``)
    first runs this file top-to-bottom. ``internal_api_auth`` reaches all the
    way to ``backend.app.core.config.Settings()`` at import time, which is
    validated eagerly and requires production secrets (JWT_SECRET_KEY,
    API_KEYS). Eagerly re-exporting it here would make every unrelated leaf
    util — including plain, secret-free modules like ``service_accounts`` —
    require those production secrets just to import. Deferring the import to
    first attribute access keeps the package importable without secrets,
    while ``from backend.app.utils import verify_internal_api_key`` still
    works for callers that do have them configured.
    """
    if name == "verify_internal_api_key":
        from backend.app.utils.internal_api_auth import verify_internal_api_key

        globals()["verify_internal_api_key"] = verify_internal_api_key
        return verify_internal_api_key
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
