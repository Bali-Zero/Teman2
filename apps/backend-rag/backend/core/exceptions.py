"""
Nuzantara Backend - Custom Exception Hierarchy

Domain-specific exceptions for better error handling, logging, and debugging.
All exceptions inherit from NuzantaraBaseError for consistent behavior.
"""

from typing import Any


class NuzantaraBaseError(Exception):
    """Base exception for all Nuzantara backend errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
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

    def __init__(self, message: str, status_code: int, response_text: str | None = None) -> None:
        super().__init__(
            message, details={"status_code": status_code, "response_text": response_text},
        )
        self.status_code = status_code
        self.response_text = response_text


class QdrantClientError(QdrantError):
    """Qdrant client error (4xx) - bad request."""

    def __init__(self, message: str, status_code: int, response_text: str | None = None) -> None:
        super().__init__(
            message, details={"status_code": status_code, "response_text": response_text},
        )
        self.status_code = status_code
        self.response_text = response_text


class CollectionNotFoundError(QdrantError):
    """Qdrant collection does not exist."""

    def __init__(self, collection_name: str) -> None:
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

    def __init__(self, provider: str, retry_after: int | None = None) -> None:
        super().__init__(
            f"Rate limit exceeded for {provider}",
            details={"provider": provider, "retry_after": retry_after},
        )
        self.provider = provider
        self.retry_after = retry_after


class LLMContextLengthError(LLMError):
    """Input exceeds LLM context length."""

    def __init__(self, provider: str, max_tokens: int, actual_tokens: int) -> None:
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


class PortalAccessDenied(ForbiddenError):
    """
    Raised when a Portal service method is called with a client_id that the
    requester is not authorised to access.

    This is the "defence in depth" boundary: the router layer is still the
    primary gate (resolves client_id from the JWT via get_current_client),
    but services re-validate so that a future router regression cannot
    silently expose one client's data to another.

    Audit 2026-04-18 HIGH-6.
    """

    def __init__(
        self,
        client_id: int,
        actor_email: str | None = None,
        actor_client_id: int | None = None,
        *,
        method: str | None = None,
    ) -> None:
        details: dict[str, Any] = {"client_id": client_id}
        if actor_email:
            details["actor_email"] = actor_email
        if actor_client_id is not None:
            details["actor_client_id"] = actor_client_id
        if method:
            details["method"] = method
        super().__init__(
            f"Portal access denied for client_id={client_id}",
            details=details,
        )
        self.client_id = client_id
        self.actor_email = actor_email
        self.actor_client_id = actor_client_id
        self.method = method


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

    def __init__(self, field: str, message: str, value: Any = None) -> None:
        super().__init__(
            f"Validation failed for '{field}': {message}",
            details={"field": field, "value": value},
        )
        self.field = field


class ConfigurationError(NuzantaraBaseError):
    """Configuration is missing or invalid."""

    def __init__(self, config_key: str, message: str | None = None) -> None:
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

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(
            f"{resource_type} with ID '{resource_id}' not found",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class DuplicateResourceError(BusinessError):
    """Resource already exists."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        super().__init__(
            f"{resource_type} '{identifier}' already exists",
            details={"resource_type": resource_type, "identifier": identifier},
        )


class QuotaExceededError(BusinessError):
    """Usage quota exceeded."""

    def __init__(self, resource: str, limit: int, current: int) -> None:
        super().__init__(
            f"Quota exceeded for {resource}: {current}/{limit}",
            details={"resource": resource, "limit": limit, "current": current},
        )


# =============================================================================
# Service Exceptions
# =============================================================================


class ServiceUnavailableError(NuzantaraBaseError):
    """External service is unavailable."""

    def __init__(self, service_name: str, reason: str | None = None) -> None:
        msg = f"Service '{service_name}' is unavailable"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, details={"service_name": service_name, "reason": reason})


class RetryableError(NuzantaraBaseError):
    """Error that can be retried."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message, details={"retry_after": retry_after})
        self.retry_after = retry_after


# =============================================================================
# UU PDP (Indonesian Personal Data Protection) Exceptions
# =============================================================================
#
# Indonesia's Undang-Undang Perlindungan Data Pribadi (UU PDP, Law 27/2022)
# imposes a duty of care on any "data controller" (pengendali data pribadi)
# processing personal data of Indonesian data subjects. The classes below make
# PDP-relevant error paths explicit so the control-flow can emit audit trails
# instead of swallowing the exception silently.
#
# All PDP errors expose `pdp_category` (short machine-readable tag) so that
# log pipelines and middleware can filter/forward them to the PDP audit sink.
# The `data_subject_id` attribute is *optional* — it should carry the opaque
# internal identifier (client_id, user_id) of the affected subject, NEVER raw
# PII like email or NIK. Redaction is the caller's responsibility.


class PDPError(NuzantaraBaseError):
    """Base exception for UU PDP compliance events.

    Sub-classes MUST set ``pdp_category`` to one of the stable tags defined
    as class attributes on :class:`PDPError` (``AUDIT_REQUIRED``,
    ``PII_ACCESS``, ``CONSENT``, ``RETENTION``, ``TRANSFER``, ``SUBJECT_REQUEST``).
    """

    # Stable tags — consumed by audit pipelines / metrics.
    CATEGORY_AUDIT_REQUIRED = "audit_required"
    CATEGORY_PII_ACCESS = "pii_access"
    CATEGORY_CONSENT = "consent"
    CATEGORY_RETENTION = "retention"
    CATEGORY_TRANSFER = "transfer"
    CATEGORY_SUBJECT_REQUEST = "subject_request"

    pdp_category: str = "generic"

    def __init__(
        self,
        message: str,
        *,
        data_subject_id: str | None = None,
        pdp_category: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {"pdp_category": pdp_category or self.pdp_category}
        if data_subject_id is not None:
            merged["data_subject_id"] = data_subject_id
        if details:
            merged.update(details)
        super().__init__(message, details=merged)
        self.data_subject_id = data_subject_id
        if pdp_category is not None:
            self.pdp_category = pdp_category


class PDPAuditRequired(PDPError):
    """A PDP-relevant step completed without producing the required audit event.

    Raise this when a write to personal data succeeds but the downstream audit
    sink (DB row, Redis stream, Telegram broadcast) cannot be persisted, so the
    caller can decide whether to roll back or enqueue a retry.
    """

    pdp_category = PDPError.CATEGORY_AUDIT_REQUIRED

    def __init__(
        self,
        operation: str,
        reason: str,
        *,
        data_subject_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged = {"operation": operation, "reason": reason}
        if details:
            merged.update(details)
        super().__init__(
            f"PDP audit missing for operation '{operation}': {reason}",
            data_subject_id=data_subject_id,
            details=merged,
        )
        self.operation = operation
        self.reason = reason


class PIIAccessDenied(PDPError):
    """Access to a field classified as personal data was refused by policy.

    Distinct from :class:`ForbiddenError` (generic RBAC): this records that the
    denial is rooted in a PDP classification (Art. 16 — lawful basis), not in
    the actor's role alone.
    """

    pdp_category = PDPError.CATEGORY_PII_ACCESS

    def __init__(
        self,
        field: str,
        reason: str,
        *,
        data_subject_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        super().__init__(
            f"Access to PII field '{field}' denied: {reason}",
            data_subject_id=data_subject_id,
            details={"field": field, "reason": reason, "actor": actor},
        )
        self.field = field
        self.reason = reason
        self.actor = actor


class ConsentMissing(PDPError):
    """A data-processing step was invoked without a recorded consent basis.

    Applies both to initial consent (Art. 20) and to purpose-limitation breaches
    (processing outside the consented purpose, Art. 14).
    """

    pdp_category = PDPError.CATEGORY_CONSENT

    def __init__(
        self,
        purpose: str,
        *,
        data_subject_id: str | None = None,
        channel: str | None = None,
    ) -> None:
        super().__init__(
            f"No valid consent for purpose '{purpose}'",
            data_subject_id=data_subject_id,
            details={"purpose": purpose, "channel": channel},
        )
        self.purpose = purpose
        self.channel = channel


class DataRetentionViolation(PDPError):
    """Personal data was found stored past its retention ceiling (Art. 45).

    ``max_retention_days`` documents the configured ceiling; ``age_days`` the
    observed age. Callers SHOULD either purge or escalate.
    """

    pdp_category = PDPError.CATEGORY_RETENTION

    def __init__(
        self,
        resource_type: str,
        max_retention_days: int,
        age_days: int,
        *,
        data_subject_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Retention exceeded for {resource_type}: {age_days}d > {max_retention_days}d",
            data_subject_id=data_subject_id,
            details={
                "resource_type": resource_type,
                "max_retention_days": max_retention_days,
                "age_days": age_days,
            },
        )
        self.resource_type = resource_type
        self.max_retention_days = max_retention_days
        self.age_days = age_days


class CrossBorderTransferError(PDPError):
    """An outbound personal-data transfer lacks the safeguards of UU PDP Art. 56.

    Raised by egress guards when destination country is not adequacy-listed and
    no alternative lawful basis (SCC / binding corporate rules) is declared.
    """

    pdp_category = PDPError.CATEGORY_TRANSFER

    def __init__(
        self,
        destination: str,
        *,
        data_subject_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(
            f"Cross-border PDP transfer to '{destination}' not permitted"
            + (f": {reason}" if reason else ""),
            data_subject_id=data_subject_id,
            details={"destination": destination, "reason": reason},
        )
        self.destination = destination
        self.reason = reason


class DataSubjectRequestError(PDPError):
    """A data-subject request (Art. 5–10: access, rectify, erase, portability)
    failed before it could be fulfilled.

    ``request_type`` is one of ``access`` / ``rectify`` / ``erase`` /
    ``portability`` / ``restrict`` / ``object``.
    """

    pdp_category = PDPError.CATEGORY_SUBJECT_REQUEST

    _ALLOWED = frozenset({"access", "rectify", "erase", "portability", "restrict", "object"})

    def __init__(
        self,
        request_type: str,
        reason: str,
        *,
        data_subject_id: str | None = None,
    ) -> None:
        if request_type not in self._ALLOWED:
            request_type = "unknown"
        super().__init__(
            f"Data subject request '{request_type}' failed: {reason}",
            data_subject_id=data_subject_id,
            details={"request_type": request_type, "reason": reason},
        )
        self.request_type = request_type
        self.reason = reason
