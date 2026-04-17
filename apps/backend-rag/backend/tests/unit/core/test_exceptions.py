"""
Unit tests for backend/core/exceptions.py — Custom Exception Hierarchy.

Tests all exception classes: construction, inheritance, str representation,
and attribute storage for domain-specific exceptions.
"""

import pytest

from backend.core.exceptions import (
    AuthError,
    BusinessError,
    CollectionNotFoundError,
    ConfigurationError,
    ConnectionError,
    DatabaseError,
    DuplicateResourceError,
    EmbeddingError,
    ForbiddenError,
    GeminiError,
    GoogleDriveError,
    IntegrationError,
    LLMContextLengthError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    NuzantaraBaseError,
    OpenAIError,
    QdrantClientError,
    QdrantConnectionError,
    QdrantError,
    QdrantServerError,
    QdrantTimeoutError,
    QueryError,
    QuotaExceededError,
    RAGError,
    ResourceNotFoundError,
    RetryableError,
    ServiceUnavailableError,
    TelegramError,
    TokenExpiredError,
    TokenInvalidError,
    TransactionError,
    UnauthorizedError,
    ValidationError,
    ZohoError,
)

# =============================================================================
# NuzantaraBaseError
# =============================================================================


class TestNuzantaraBaseError:
    """Tests for the base exception class."""

    def test_message_only(self) -> None:
        err = NuzantaraBaseError("something went wrong")
        assert err.message == "something went wrong"
        assert err.details == {}
        assert str(err) == "something went wrong"

    def test_message_with_details(self) -> None:
        details = {"key": "value", "count": 42}
        err = NuzantaraBaseError("failure", details=details)
        assert err.message == "failure"
        assert err.details == details
        assert "Details:" in str(err)
        assert "key" in str(err)

    def test_empty_details_not_shown_in_str(self) -> None:
        err = NuzantaraBaseError("clean message", details={})
        assert str(err) == "clean message"

    def test_inherits_from_exception(self) -> None:
        err = NuzantaraBaseError("test")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(NuzantaraBaseError, match="boom"):
            raise NuzantaraBaseError("boom")

    def test_details_default_none_becomes_empty_dict(self) -> None:
        err = NuzantaraBaseError("msg", details=None)
        assert err.details == {}


# =============================================================================
# Database & Storage Exceptions
# =============================================================================


class TestDatabaseExceptions:
    """Tests for database exception hierarchy."""

    def test_database_error_inherits_base(self) -> None:
        err = DatabaseError("db fail")
        assert isinstance(err, NuzantaraBaseError)
        assert err.message == "db fail"

    def test_connection_error_inherits_database(self) -> None:
        err = ConnectionError("cannot connect")
        assert isinstance(err, DatabaseError)
        assert isinstance(err, NuzantaraBaseError)

    def test_query_error_inherits_database(self) -> None:
        err = QueryError("bad query", details={"query": "SELECT *"})
        assert isinstance(err, DatabaseError)
        assert err.details["query"] == "SELECT *"

    def test_transaction_error_inherits_database(self) -> None:
        err = TransactionError("rollback")
        assert isinstance(err, DatabaseError)


# =============================================================================
# Qdrant Exceptions
# =============================================================================


class TestQdrantExceptions:
    """Tests for Qdrant exception hierarchy."""

    def test_qdrant_error_inherits_base(self) -> None:
        err = QdrantError("qdrant fail")
        assert isinstance(err, NuzantaraBaseError)

    def test_qdrant_connection_error(self) -> None:
        err = QdrantConnectionError("refused")
        assert isinstance(err, QdrantError)

    def test_qdrant_timeout_error(self) -> None:
        err = QdrantTimeoutError("30s exceeded")
        assert isinstance(err, QdrantError)

    def test_qdrant_server_error_with_status(self) -> None:
        err = QdrantServerError("internal error", status_code=500, response_text="panic")
        assert isinstance(err, QdrantError)
        assert err.status_code == 500
        assert err.response_text == "panic"
        assert err.details["status_code"] == 500
        assert err.details["response_text"] == "panic"

    def test_qdrant_server_error_no_response_text(self) -> None:
        err = QdrantServerError("err", status_code=503)
        assert err.response_text is None
        assert err.details["response_text"] is None

    def test_qdrant_client_error_with_status(self) -> None:
        err = QdrantClientError("bad request", status_code=400, response_text="invalid filter")
        assert isinstance(err, QdrantError)
        assert err.status_code == 400
        assert err.response_text == "invalid filter"

    def test_qdrant_client_error_no_response_text(self) -> None:
        err = QdrantClientError("err", status_code=422)
        assert err.response_text is None

    def test_collection_not_found_error(self) -> None:
        err = CollectionNotFoundError("my_collection")
        assert isinstance(err, QdrantError)
        assert err.collection_name == "my_collection"
        assert "my_collection" in str(err)
        assert err.details["collection_name"] == "my_collection"


# =============================================================================
# RAG & LLM Exceptions
# =============================================================================


class TestRAGAndLLMExceptions:
    """Tests for RAG and LLM exception hierarchy."""

    def test_rag_error_inherits_base(self) -> None:
        err = RAGError("pipeline broken")
        assert isinstance(err, NuzantaraBaseError)

    def test_embedding_error_inherits_rag(self) -> None:
        err = EmbeddingError("embedding generation failed")
        assert isinstance(err, RAGError)

    def test_llm_error_inherits_base(self) -> None:
        err = LLMError("llm down")
        assert isinstance(err, NuzantaraBaseError)

    def test_llm_rate_limit_error(self) -> None:
        err = LLMRateLimitError(provider="openai", retry_after=60)
        assert isinstance(err, LLMError)
        assert err.provider == "openai"
        assert err.retry_after == 60
        assert "openai" in str(err)
        assert err.details["provider"] == "openai"
        assert err.details["retry_after"] == 60

    def test_llm_rate_limit_no_retry_after(self) -> None:
        err = LLMRateLimitError(provider="gemini")
        assert err.retry_after is None
        assert err.details["retry_after"] is None

    def test_llm_context_length_error(self) -> None:
        err = LLMContextLengthError(provider="anthropic", max_tokens=200000, actual_tokens=250000)
        assert isinstance(err, LLMError)
        assert "anthropic" in str(err)
        assert err.details["provider"] == "anthropic"
        assert err.details["max_tokens"] == 200000
        assert err.details["actual_tokens"] == 250000

    def test_llm_response_error(self) -> None:
        err = LLMResponseError("unexpected JSON")
        assert isinstance(err, LLMError)


# =============================================================================
# Authentication & Authorization Exceptions
# =============================================================================


class TestAuthExceptions:
    """Tests for auth exception hierarchy."""

    def test_auth_error_inherits_base(self) -> None:
        assert isinstance(AuthError("fail"), NuzantaraBaseError)

    def test_token_expired_error(self) -> None:
        err = TokenExpiredError("JWT expired at 2026-01-01")
        assert isinstance(err, AuthError)

    def test_token_invalid_error(self) -> None:
        err = TokenInvalidError("malformed header")
        assert isinstance(err, AuthError)

    def test_unauthorized_error(self) -> None:
        err = UnauthorizedError("not logged in")
        assert isinstance(err, AuthError)

    def test_forbidden_error(self) -> None:
        err = ForbiddenError("admin only")
        assert isinstance(err, AuthError)


# =============================================================================
# Integration Exceptions
# =============================================================================


class TestIntegrationExceptions:
    """Tests for integration exception hierarchy."""

    def test_integration_error_inherits_base(self) -> None:
        assert isinstance(IntegrationError("api fail"), NuzantaraBaseError)

    def test_zoho_error(self) -> None:
        assert isinstance(ZohoError("zoho 429"), IntegrationError)

    def test_google_drive_error(self) -> None:
        assert isinstance(GoogleDriveError("quota exceeded"), IntegrationError)

    def test_telegram_error(self) -> None:
        assert isinstance(TelegramError("bot blocked"), IntegrationError)

    def test_openai_error(self) -> None:
        assert isinstance(OpenAIError("rate limited"), IntegrationError)

    def test_gemini_error(self) -> None:
        assert isinstance(GeminiError("safety filter"), IntegrationError)


# =============================================================================
# Validation Exceptions
# =============================================================================


class TestValidationExceptions:
    """Tests for validation exception classes."""

    def test_validation_error_with_all_fields(self) -> None:
        err = ValidationError(field="email", message="invalid format", value="notanemail")
        assert isinstance(err, NuzantaraBaseError)
        assert err.field == "email"
        assert err.details["field"] == "email"
        assert err.details["value"] == "notanemail"
        assert "email" in str(err)
        assert "invalid format" in str(err)

    def test_validation_error_without_value(self) -> None:
        err = ValidationError(field="phone", message="required")
        assert err.details["value"] is None

    def test_configuration_error_default_message(self) -> None:
        err = ConfigurationError(config_key="REDIS_URL")
        assert isinstance(err, NuzantaraBaseError)
        assert err.config_key == "REDIS_URL"
        assert "REDIS_URL" in str(err)
        assert err.details["config_key"] == "REDIS_URL"

    def test_configuration_error_custom_message(self) -> None:
        err = ConfigurationError(config_key="API_KEY", message="API_KEY must be at least 32 chars")
        assert "API_KEY must be at least 32 chars" in str(err)
        assert err.config_key == "API_KEY"


# =============================================================================
# Business Logic Exceptions
# =============================================================================


class TestBusinessExceptions:
    """Tests for business logic exceptions."""

    def test_business_error_inherits_base(self) -> None:
        assert isinstance(BusinessError("logic fail"), NuzantaraBaseError)

    def test_resource_not_found_error(self) -> None:
        err = ResourceNotFoundError(resource_type="Client", resource_id="abc-123")
        assert isinstance(err, BusinessError)
        assert "Client" in str(err)
        assert "abc-123" in str(err)
        assert err.details["resource_type"] == "Client"
        assert err.details["resource_id"] == "abc-123"

    def test_duplicate_resource_error(self) -> None:
        err = DuplicateResourceError(resource_type="User", identifier="john@example.com")
        assert isinstance(err, BusinessError)
        assert "User" in str(err)
        assert "john@example.com" in str(err)
        assert err.details["resource_type"] == "User"
        assert err.details["identifier"] == "john@example.com"

    def test_quota_exceeded_error(self) -> None:
        err = QuotaExceededError(resource="api_calls", limit=1000, current=1001)
        assert isinstance(err, BusinessError)
        assert "1001/1000" in str(err)
        assert err.details["resource"] == "api_calls"
        assert err.details["limit"] == 1000
        assert err.details["current"] == 1001


# =============================================================================
# Service Exceptions
# =============================================================================


class TestServiceExceptions:
    """Tests for service-level exceptions."""

    def test_service_unavailable_without_reason(self) -> None:
        err = ServiceUnavailableError(service_name="Qdrant")
        assert isinstance(err, NuzantaraBaseError)
        assert "Qdrant" in str(err)
        assert "unavailable" in str(err)
        assert err.details["service_name"] == "Qdrant"
        assert err.details["reason"] is None

    def test_service_unavailable_with_reason(self) -> None:
        err = ServiceUnavailableError(service_name="Redis", reason="connection refused")
        assert "Redis" in str(err)
        assert "connection refused" in str(err)
        assert err.details["reason"] == "connection refused"

    def test_retryable_error_with_retry_after(self) -> None:
        err = RetryableError("temporary failure", retry_after=30)
        assert isinstance(err, NuzantaraBaseError)
        assert err.retry_after == 30
        assert err.details["retry_after"] == 30

    def test_retryable_error_without_retry_after(self) -> None:
        err = RetryableError("temp")
        assert err.retry_after is None


# =============================================================================
# Cross-cutting: exception hierarchy chains
# =============================================================================


class TestExceptionHierarchyChains:
    """Verify full inheritance chains are correct for catch blocks."""

    def test_catch_all_nuzantara_errors(self) -> None:
        """All domain exceptions should be catchable via NuzantaraBaseError."""
        exceptions_to_test = [
            DatabaseError("db"),
            ConnectionError("conn"),
            QueryError("q"),
            TransactionError("tx"),
            QdrantError("qd"),
            QdrantConnectionError("qdc"),
            QdrantTimeoutError("qdt"),
            QdrantServerError("qds", status_code=500),
            QdrantClientError("qdc", status_code=400),
            CollectionNotFoundError("col"),
            RAGError("rag"),
            EmbeddingError("emb"),
            LLMError("llm"),
            LLMRateLimitError(provider="p"),
            LLMContextLengthError(provider="p", max_tokens=1, actual_tokens=2),
            LLMResponseError("resp"),
            AuthError("auth"),
            TokenExpiredError("exp"),
            TokenInvalidError("inv"),
            UnauthorizedError("unauth"),
            ForbiddenError("forb"),
            IntegrationError("int"),
            ZohoError("z"),
            GoogleDriveError("gd"),
            TelegramError("tg"),
            OpenAIError("oai"),
            GeminiError("gem"),
            ValidationError(field="f", message="m"),
            ConfigurationError(config_key="k"),
            BusinessError("biz"),
            ResourceNotFoundError(resource_type="R", resource_id="1"),
            DuplicateResourceError(resource_type="R", identifier="x"),
            QuotaExceededError(resource="r", limit=1, current=2),
            ServiceUnavailableError(service_name="s"),
            RetryableError("retry"),
        ]
        for exc in exceptions_to_test:
            assert isinstance(exc, NuzantaraBaseError), f"{type(exc).__name__} not a NuzantaraBaseError"

    def test_qdrant_errors_catchable_by_qdrant_error(self) -> None:
        qdrant_exceptions = [
            QdrantConnectionError("c"),
            QdrantTimeoutError("t"),
            QdrantServerError("s", status_code=500),
            QdrantClientError("c", status_code=400),
            CollectionNotFoundError("col"),
        ]
        for exc in qdrant_exceptions:
            assert isinstance(exc, QdrantError), f"{type(exc).__name__} not a QdrantError"

    def test_llm_errors_catchable_by_llm_error(self) -> None:
        llm_exceptions = [
            LLMRateLimitError(provider="p"),
            LLMContextLengthError(provider="p", max_tokens=1, actual_tokens=2),
            LLMResponseError("r"),
        ]
        for exc in llm_exceptions:
            assert isinstance(exc, LLMError), f"{type(exc).__name__} not an LLMError"

    def test_auth_errors_catchable_by_auth_error(self) -> None:
        auth_exceptions = [
            TokenExpiredError("e"),
            TokenInvalidError("i"),
            UnauthorizedError("u"),
            ForbiddenError("f"),
        ]
        for exc in auth_exceptions:
            assert isinstance(exc, AuthError), f"{type(exc).__name__} not an AuthError"


# =============================================================================
# UU PDP Exceptions
# =============================================================================

from backend.core.exceptions import (  # noqa: E402 — co-located to keep diff local
    ConsentMissing,
    CrossBorderTransferError,
    DataRetentionViolation,
    DataSubjectRequestError,
    PDPAuditRequired,
    PDPError,
    PIIAccessDenied,
)


class TestPDPError:
    def test_pdp_error_is_nuzantara_base(self) -> None:
        err = PDPError("oops")
        assert isinstance(err, NuzantaraBaseError)
        assert err.details["pdp_category"] == "generic"

    def test_pdp_error_with_subject_and_category(self) -> None:
        err = PDPError(
            "failure",
            data_subject_id="client_42",
            pdp_category=PDPError.CATEGORY_PII_ACCESS,
            details={"extra": True},
        )
        assert err.data_subject_id == "client_42"
        assert err.pdp_category == PDPError.CATEGORY_PII_ACCESS
        assert err.details["data_subject_id"] == "client_42"
        assert err.details["pdp_category"] == PDPError.CATEGORY_PII_ACCESS
        assert err.details["extra"] is True

    def test_pdp_error_does_not_leak_none_subject(self) -> None:
        err = PDPError("x")
        assert "data_subject_id" not in err.details


class TestPDPAuditRequired:
    def test_construction(self) -> None:
        err = PDPAuditRequired(
            "client_update",
            "redis audit stream unavailable",
            data_subject_id="client_7",
        )
        assert isinstance(err, PDPError)
        assert err.operation == "client_update"
        assert err.reason == "redis audit stream unavailable"
        assert err.details["operation"] == "client_update"
        assert err.details["reason"] == "redis audit stream unavailable"
        assert err.pdp_category == PDPError.CATEGORY_AUDIT_REQUIRED

    def test_merges_extra_details(self) -> None:
        err = PDPAuditRequired("op", "why", details={"trace_id": "t-1"})
        assert err.details["trace_id"] == "t-1"


class TestPIIAccessDenied:
    def test_construction(self) -> None:
        err = PIIAccessDenied(
            "passport_number",
            "actor lacks pii_read permission",
            data_subject_id="client_9",
            actor="user:42",
        )
        assert err.field == "passport_number"
        assert err.actor == "user:42"
        assert err.pdp_category == PDPError.CATEGORY_PII_ACCESS
        assert "passport_number" in str(err)

    def test_is_pdp_error_not_auth_error(self) -> None:
        # PII denial is a PDP event, not a generic auth failure.
        err = PIIAccessDenied("email", "policy")
        assert isinstance(err, PDPError)
        assert not isinstance(err, AuthError)


class TestConsentMissing:
    def test_construction(self) -> None:
        err = ConsentMissing(
            "marketing_email",
            data_subject_id="client_3",
            channel="email",
        )
        assert err.purpose == "marketing_email"
        assert err.channel == "email"
        assert err.pdp_category == PDPError.CATEGORY_CONSENT
        assert err.details["purpose"] == "marketing_email"


class TestDataRetentionViolation:
    def test_construction(self) -> None:
        err = DataRetentionViolation(
            resource_type="passport_scan",
            max_retention_days=180,
            age_days=220,
            data_subject_id="client_1",
        )
        assert err.resource_type == "passport_scan"
        assert err.max_retention_days == 180
        assert err.age_days == 220
        assert err.pdp_category == PDPError.CATEGORY_RETENTION
        assert "220d > 180d" in str(err)


class TestCrossBorderTransferError:
    def test_construction(self) -> None:
        err = CrossBorderTransferError(
            destination="us",
            data_subject_id="client_5",
            reason="no SCC in place",
        )
        assert err.destination == "us"
        assert err.reason == "no SCC in place"
        assert err.pdp_category == PDPError.CATEGORY_TRANSFER


class TestDataSubjectRequestError:
    def test_valid_request_type(self) -> None:
        err = DataSubjectRequestError(
            "erase",
            "client still has active practice",
            data_subject_id="client_2",
        )
        assert err.request_type == "erase"
        assert err.pdp_category == PDPError.CATEGORY_SUBJECT_REQUEST

    def test_unknown_request_type_normalised(self) -> None:
        err = DataSubjectRequestError("teleport", "nope")
        assert err.request_type == "unknown"


class TestPDPHierarchyCatchable:
    def test_all_pdp_errors_catchable_by_pdp_error(self) -> None:
        pdp_exceptions = [
            PDPAuditRequired("op", "r"),
            PIIAccessDenied("f", "r"),
            ConsentMissing("purpose"),
            DataRetentionViolation("t", 1, 2),
            CrossBorderTransferError("us"),
            DataSubjectRequestError("erase", "r"),
        ]
        for exc in pdp_exceptions:
            assert isinstance(exc, PDPError), f"{type(exc).__name__} not a PDPError"
            assert isinstance(exc, NuzantaraBaseError)
            # Every PDP error carries a stable machine-readable tag.
            assert exc.details["pdp_category"] == exc.pdp_category
