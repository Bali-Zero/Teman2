"""
Custom exceptions for the Zantara backend.

Provides a hierarchy of domain-specific exceptions for better error handling
and more informative API responses.
"""

from typing import Any


class ZantaraError(Exception):
    """Base exception for all Zantara errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}


# Authentication & Authorization Errors
class AuthenticationError(ZantaraError):
    """Raised when authentication fails."""

    def __init__(
        self, message: str = "Authentication failed", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message, "AUTHENTICATION_ERROR", details)


class AuthorizationError(ZantaraError):
    """Raised when user lacks required permissions."""

    def __init__(
        self, message: str = "Access denied", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message, "AUTHORIZATION_ERROR", details)


class TokenExpiredError(AuthenticationError):
    """Raised when authentication token has expired."""

    def __init__(self, message: str = "Token expired") -> None:
        super().__init__(message, {"token_status": "expired"})


# Resource Errors
class ResourceNotFoundError(ZantaraError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str | None = None) -> None:
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} '{resource_id}' not found"
        super().__init__(message, "RESOURCE_NOT_FOUND", {"resource_type": resource_type})


class ResourceConflictError(ZantaraError):
    """Raised when there's a conflict with existing resource."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, "RESOURCE_CONFLICT", details)


# Validation Errors
class ValidationError(ZantaraError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        details = {"field": field} if field else {}
        super().__init__(message, "VALIDATION_ERROR", details)


class RateLimitError(ZantaraError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: int | None = None
    ) -> None:
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, "RATE_LIMIT_EXCEEDED", details)


# External Service Errors
class ExternalServiceError(ZantaraError):
    """Raised when an external service call fails."""

    def __init__(self, service: str, message: str | None = None) -> None:
        msg = message or f"{service} service error"
        super().__init__(msg, "EXTERNAL_SERVICE_ERROR", {"service": service})


class LLMServiceError(ExternalServiceError):
    """Raised when LLM service call fails."""

    def __init__(self, message: str = "LLM service error", provider: str | None = None) -> None:
        details = {"provider": provider} if provider else {}
        super().__init__("LLM", message)
        self.details.update(details)


class DatabaseError(ZantaraError):
    """Raised when database operation fails."""

    def __init__(self, message: str = "Database error", operation: str | None = None) -> None:
        details = {"operation": operation} if operation else {}
        super().__init__(message, "DATABASE_ERROR", details)


# Business Logic Errors
class IngestionError(ZantaraError):
    """Raised when document ingestion fails."""

    def __init__(self, message: str, document_id: str | None = None) -> None:
        details = {"document_id": document_id} if document_id else {}
        super().__init__(message, "INGESTION_ERROR", details)


class SearchError(ZantaraError):
    """Raised when search operation fails."""

    def __init__(self, message: str = "Search failed") -> None:
        super().__init__(message, "SEARCH_ERROR")


# Memory/Context Errors
class MemoryError(ZantaraError):
    """Raised when memory operation fails."""

    def __init__(self, message: str = "Memory operation failed") -> None:
        super().__init__(message, "MEMORY_ERROR")


class ContextWindowError(ZantaraError):
    """Raised when context window is exceeded."""

    def __init__(self, message: str = "Context window exceeded") -> None:
        super().__init__(message, "CONTEXT_WINDOW_EXCEEDED")


# Configuration Errors
class ConfigurationError(ZantaraError):
    """Raised when there's a configuration problem."""

    def __init__(self, message: str, config_key: str | None = None) -> None:
        details = {"config_key": config_key} if config_key else {}
        super().__init__(message, "CONFIGURATION_ERROR", details)
