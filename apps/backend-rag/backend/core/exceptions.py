"""
Nuzantara Backend - Custom Exception Hierarchy

Domain-specific exceptions for better error handling, logging, and debugging.
All exceptions inherit from NuzantaraBaseError for consistent behavior.
"""

from typing import Any


class NuzantaraBaseError(Exception):
    """Base exception for all Nuzantara backend errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# =============================================================================
# Database & Storage Exceptions
# =============================================================================


class DatabaseError(NuzantaraBaseError):
    """Base exception for database operations."""

    pass


class ConnectionError(DatabaseError):
    """Failed to connect to database."""

    pass


class QueryError(DatabaseError):
    """Database query failed."""

    pass


class TransactionError(DatabaseError):
    """Transaction failed."""

    pass


# =============================================================================
# Vector Database (Qdrant) Exceptions
# =============================================================================


class QdrantError(NuzantaraBaseError):
    """Base exception for Qdrant operations."""

    pass


class QdrantConnectionError(QdrantError):
    """Failed to connect to Qdrant server."""

    pass


class QdrantTimeoutError(QdrantError):
    """Qdrant request timed out."""

    pass


class QdrantServerError(QdrantError):
    """Qdrant server returned an error (5xx)."""

    def __init__(self, message: str, status_code: int, response_text: str | None = None):
        super().__init__(
            message, details={"status_code": status_code, "response_text": response_text}
        )
        self.status_code = status_code
        self.response_text = response_text


class QdrantClientError(QdrantError):
    """Qdrant client error (4xx) - bad request."""

    def __init__(self, message: str, status_code: int, response_text: str | None = None):
        super().__init__(
            message, details={"status_code": status_code, "response_text": response_text}
        )
        self.status_code = status_code
        self.response_text = response_text


class CollectionNotFoundError(QdrantError):
    """Qdrant collection does not exist."""

    def __init__(self, collection_name: str):
        super().__init__(
            f"Collection '{collection_name}' not found",
            details={"collection_name": collection_name},
        )
        self.collection_name = collection_name


# =============================================================================
# RAG & LLM Exceptions
# =============================================================================


class RAGError(NuzantaraBaseError):
    """Base exception for RAG pipeline errors."""

    pass


class EmbeddingError(RAGError):
    """Failed to generate embeddings."""

    pass


class LLMError(NuzantaraBaseError):
    """Base exception for LLM operations."""

    pass


class LLMRateLimitError(LLMError):
    """LLM API rate limit exceeded."""

    def __init__(self, provider: str, retry_after: int | None = None):
        super().__init__(
            f"Rate limit exceeded for {provider}",
            details={"provider": provider, "retry_after": retry_after},
        )
        self.provider = provider
        self.retry_after = retry_after


class LLMContextLengthError(LLMError):
    """Input exceeds LLM context length."""

    def __init__(self, provider: str, max_tokens: int, actual_tokens: int):
        super().__init__(
            f"Context length exceeded for {provider}",
            details={
                "provider": provider,
                "max_tokens": max_tokens,
                "actual_tokens": actual_tokens,
            },
        )


class LLMResponseError(LLMError):
    """LLM returned invalid or unexpected response."""

    pass


# =============================================================================
# Authentication & Authorization Exceptions
# =============================================================================


class AuthError(NuzantaraBaseError):
    """Base exception for authentication errors."""

    pass


class TokenExpiredError(AuthError):
    """JWT or OAuth token has expired."""

    pass


class TokenInvalidError(AuthError):
    """Token is invalid or malformed."""

    pass


class UnauthorizedError(AuthError):
    """User is not authorized to perform this action."""

    pass


class ForbiddenError(AuthError):
    """User does not have permission for this resource."""

    pass


# =============================================================================
# Integration Exceptions
# =============================================================================


class IntegrationError(NuzantaraBaseError):
    """Base exception for third-party integrations."""

    pass


class ZohoError(IntegrationError):
    """Zoho API error."""

    pass


class GoogleDriveError(IntegrationError):
    """Google Drive API error."""

    pass


class TelegramError(IntegrationError):
    """Telegram API error."""

    pass


class OpenAIError(IntegrationError):
    """OpenAI API error."""

    pass


class GeminiError(IntegrationError):
    """Google Gemini API error."""

    pass


# =============================================================================
# Validation Exceptions
# =============================================================================


class ValidationError(NuzantaraBaseError):
    """Input validation failed."""

    def __init__(self, field: str, message: str, value: Any = None):
        super().__init__(
            f"Validation failed for '{field}': {message}",
            details={"field": field, "value": value},
        )
        self.field = field


class ConfigurationError(NuzantaraBaseError):
    """Configuration is missing or invalid."""

    def __init__(self, config_key: str, message: str | None = None):
        msg = message or f"Configuration missing or invalid: {config_key}"
        super().__init__(msg, details={"config_key": config_key})
        self.config_key = config_key


# =============================================================================
# Business Logic Exceptions
# =============================================================================


class BusinessError(NuzantaraBaseError):
    """Base exception for business logic errors."""

    pass


class ResourceNotFoundError(BusinessError):
    """Requested resource does not exist."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} with ID '{resource_id}' not found",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class DuplicateResourceError(BusinessError):
    """Resource already exists."""

    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            f"{resource_type} '{identifier}' already exists",
            details={"resource_type": resource_type, "identifier": identifier},
        )


class QuotaExceededError(BusinessError):
    """Usage quota exceeded."""

    def __init__(self, resource: str, limit: int, current: int):
        super().__init__(
            f"Quota exceeded for {resource}: {current}/{limit}",
            details={"resource": resource, "limit": limit, "current": current},
        )


# =============================================================================
# Service Exceptions
# =============================================================================


class ServiceUnavailableError(NuzantaraBaseError):
    """External service is unavailable."""

    def __init__(self, service_name: str, reason: str | None = None):
        msg = f"Service '{service_name}' is unavailable"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, details={"service_name": service_name, "reason": reason})


class RetryableError(NuzantaraBaseError):
    """Error that can be retried."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message, details={"retry_after": retry_after})
        self.retry_after = retry_after
