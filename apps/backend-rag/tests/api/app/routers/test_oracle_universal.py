from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from backend.app.routers import oracle_universal as oracle_module
from backend.app.routers.oracle_universal import (
    ConversationMessage,
    FeedbackRequest,
    OracleQueryRequest,
    OracleQueryResponse,
    hybrid_oracle_query,
    oracle_health_check,
    submit_user_feedback,
)


class FakeOracleService:
    def __init__(
        self,
        *,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
        feedback_success: bool = True,
    ) -> None:
        self.response = response
        self.error = error
        self.feedback_success = feedback_success
        self.process_calls: list[dict[str, Any]] = []
        self.feedback_calls: list[dict[str, Any]] = []

    async def process_query(self, **kwargs: Any) -> dict[str, Any]:
        self.process_calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response or {
            "success": True,
            "query": kwargs["request_query"],
            "answer": "Answer",
            "execution_time_ms": 12.5,
            "document_count": 1,
            "sources": [{"id": "doc-1"}],
        }

    async def submit_feedback(self, payload: dict[str, Any]) -> bool:
        self.feedback_calls.append(payload)
        if self.error:
            raise self.error
        return self.feedback_success


def test_request_model_defaults_and_conversation_history() -> None:
    request = OracleQueryRequest(
        query="How much is KITAS?",
        conversation_history=[
            ConversationMessage(role="user", content="Hi"),
            ConversationMessage(role="assistant", content="Hello"),
        ],
    )

    assert request.limit == 10
    assert request.use_ai is True
    assert request.include_sources is True
    assert request.response_format == "structured"
    assert request.conversation_history[0].role == "user"


def test_request_model_validates_query_length_and_limit() -> None:
    with pytest.raises(ValidationError):
        OracleQueryRequest(query="hi")

    with pytest.raises(ValidationError):
        OracleQueryRequest(query="Valid query", limit=51)


def test_response_model_defaults_optional_enhanced_fields() -> None:
    response = OracleQueryResponse(
        success=True,
        query="Valid query",
        execution_time_ms=1.2,
    )

    assert response.answer_language == "en"
    assert response.sources == []
    assert response.followup_questions == []
    assert response.citations == []
    assert response.clarification_needed is False
    assert response.golden_answer_used is False


def test_feedback_request_validates_rating_bounds() -> None:
    request = FeedbackRequest(
        user_email="zero@example.com",
        query_text="Question",
        original_answer="Answer",
        feedback_type="correction",
        rating=5,
    )
    assert request.rating == 5

    with pytest.raises(ValidationError):
        FeedbackRequest(
            user_email="zero@example.com",
            query_text="Question",
            original_answer="Answer",
            feedback_type="correction",
            rating=6,
        )


@pytest.mark.asyncio
async def test_hybrid_oracle_query_forwards_contract_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeOracleService()
    monkeypatch.setattr(oracle_module, "oracle_service", fake_service)
    search_service = object()
    request = OracleQueryRequest(
        query="Explain E33G",
        user_email="zero@example.com",
        language_override="it",
        include_sources=False,
        use_ai=False,
        limit=3,
        session_id="session-1",
        conversation_history=[ConversationMessage(role="user", content="Ciao")],
    )

    response = await hybrid_oracle_query(
        request=request,
        service=search_service,  # type: ignore[arg-type]
        current_user={"id": "user-1"},
    )

    assert response.success is True
    assert response.query == "Explain E33G"
    assert response.sources == [{"id": "doc-1"}]
    assert fake_service.process_calls == [
        {
            "request_query": "Explain E33G",
            "request_user_email": "zero@example.com",
            "request_limit": 3,
            "request_session_id": "session-1",
            "request_include_sources": False,
            "request_use_ai": False,
            "request_language_override": "it",
            "request_conversation_history": request.conversation_history,
            "search_service": search_service,
        },
    ]


@pytest.mark.asyncio
async def test_hybrid_oracle_query_logs_unwired_fields_and_tags_sentry(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_service = FakeOracleService()
    tags: dict[str, str] = {}
    monkeypatch.setattr(oracle_module, "oracle_service", fake_service)
    monkeypatch.setattr(oracle_module.sentry_sdk, "set_tag", tags.__setitem__)

    await hybrid_oracle_query(
        request=OracleQueryRequest(
            query="Explain E33G",
            domain_hint="visa",
            context_docs=["doc-1"],
            response_format="conversational",
        ),
        service=object(),  # type: ignore[arg-type]
        current_user={},
    )

    assert "domain_hint" in caplog.text
    assert tags == {"oracle.dropped_fields": "domain_hint,context_docs,response_format"}


@pytest.mark.asyncio
async def test_hybrid_oracle_query_returns_validation_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeOracleService(response={"success": True, "query": "Question"})
    monkeypatch.setattr(oracle_module, "oracle_service", fake_service)

    response = await hybrid_oracle_query(
        request=OracleQueryRequest(query="Question"),
        service=object(),  # type: ignore[arg-type]
        current_user={},
    )

    assert response.success is False
    assert response.error is not None
    assert response.error.startswith("response_validation_error:")
    assert response.execution_time_ms == 0


@pytest.mark.asyncio
async def test_hybrid_oracle_query_returns_runtime_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        oracle_module,
        "oracle_service",
        FakeOracleService(error=RuntimeError("service offline")),
    )

    response = await hybrid_oracle_query(
        request=OracleQueryRequest(query="Question"),
        service=object(),  # type: ignore[arg-type]
        current_user={},
    )

    assert response.success is False
    assert response.error == "service offline"
    assert response.document_count == 0


@pytest.mark.asyncio
async def test_submit_user_feedback_returns_service_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeOracleService(feedback_success=True)
    monkeypatch.setattr(oracle_module, "oracle_service", fake_service)
    feedback = FeedbackRequest(
        user_email="zero@example.com",
        query_text="Question",
        original_answer="Answer",
        feedback_type="rating",
        rating=4,
        session_id="session-1",
    )

    response = await submit_user_feedback(feedback)

    assert response == {"success": True}
    assert fake_service.feedback_calls[0]["session_id"] == "session-1"


@pytest.mark.asyncio
async def test_submit_user_feedback_handles_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        oracle_module,
        "oracle_service",
        FakeOracleService(error=RuntimeError("feedback failed")),
    )
    feedback = FeedbackRequest(
        user_email="zero@example.com",
        query_text="Question",
        original_answer="Answer",
        feedback_type="rating",
        rating=4,
    )

    response = await submit_user_feedback(feedback)

    assert response == {"success": False, "error": "feedback failed"}


@pytest.mark.asyncio
async def test_oracle_health_check_reports_active_service() -> None:
    response = await oracle_health_check()

    assert response["status"] == "active"
    assert response["service"] == "Oracle v5.3"
    assert response["mode"] == "Refactored (Service Layer)"
    assert isinstance(response["timestamp"], float)
