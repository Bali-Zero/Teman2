from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.services.oracle import oracle_service as oracle_module
from backend.services.oracle.oracle_service import OracleService


def blank_service() -> OracleService:
    service = OracleService.__new__(OracleService)
    service._followup_service = None
    service._citation_service = None
    service._clarification_service = None
    service._golden_answer_service = None
    service._memory_service = None
    service._fact_extractor = None
    service._memory_orchestrator = None
    return service


def test_detect_query_language_delegates_to_language_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeLanguageDetectionService:
        def detect_language(self, query: str) -> str:
            assert query == "Terima kasih"
            return "id"

    monkeypatch.setattr(
        oracle_module,
        "LanguageDetectionService",
        FakeLanguageDetectionService,
    )

    assert oracle_module.detect_query_language("Terima kasih") == "id"


def test_generate_query_hash_delegates_to_analytics_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeOracleAnalyticsService:
        def generate_query_hash(self, query_text: str) -> str:
            assert query_text == "visa question"
            return "hash-123"

    monkeypatch.setattr(
        oracle_module,
        "OracleAnalyticsService",
        FakeOracleAnalyticsService,
    )

    assert oracle_module.generate_query_hash("visa question") == "hash-123"


def test_download_pdf_from_drive_delegates_to_retrieval_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDocumentRetrievalService:
        def download_pdf_from_drive(self, filename: str) -> str:
            assert filename == "regulation.pdf"
            return "/tmp/regulation.pdf"

    monkeypatch.setattr(
        oracle_module,
        "DocumentRetrievalService",
        FakeDocumentRetrievalService,
    )

    assert oracle_module.download_pdf_from_drive("regulation.pdf") == "/tmp/regulation.pdf"


@pytest.mark.asyncio
async def test_reason_with_gemini_delegates_to_reasoning_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeReasoningEngineService:
        def __init__(self, *, prompt_builder: object, response_validator: object) -> None:
            captured["prompt_builder"] = prompt_builder
            captured["response_validator"] = response_validator

        async def reason_with_gemini(self, **kwargs: Any) -> dict[str, Any]:
            captured["kwargs"] = kwargs
            return {"answer": "grounded answer"}

    prompt_builder = object()
    response_validator = object()
    context = object()
    monkeypatch.setattr(
        oracle_module,
        "ReasoningEngineService",
        FakeReasoningEngineService,
    )

    result = await oracle_module.reason_with_gemini(
        documents=["doc"],
        query="What permit is needed?",
        context=context,
        prompt_builder=prompt_builder,
        response_validator=response_validator,
        use_full_docs=True,
        user_memory_facts=["prefers concise"],
        conversation_history=[{"role": "user", "content": "hi"}],
    )

    assert result == {"answer": "grounded answer"}
    assert captured["prompt_builder"] is prompt_builder
    assert captured["response_validator"] is response_validator
    assert captured["kwargs"] == {
        "documents": ["doc"],
        "query": "What permit is needed?",
        "context": context,
        "use_full_docs": True,
        "user_memory_facts": ["prefers concise"],
        "conversation_history": [{"role": "user", "content": "hi"}],
    }


def test_lazy_services_are_created_once(monkeypatch: pytest.MonkeyPatch) -> None:
    service = blank_service()
    followup = object()
    citation = object()
    clarification = object()
    fact_extractor = object()

    monkeypatch.setattr(oracle_module, "FollowupService", lambda: followup)
    monkeypatch.setattr(oracle_module, "CitationService", lambda: citation)
    monkeypatch.setattr(oracle_module, "ClarificationService", lambda: clarification)
    monkeypatch.setattr(oracle_module, "MemoryFactExtractor", lambda: fact_extractor)

    assert service.followup_service is followup
    assert service.followup_service is followup
    assert service.citation_service is citation
    assert service.citation_service is citation
    assert service.clarification_service is clarification
    assert service.clarification_service is clarification
    assert service.personality_service is None
    assert service.fact_extractor is fact_extractor
    assert service.fact_extractor is fact_extractor


def test_database_backed_lazy_services_use_configured_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = blank_service()
    created: dict[str, str | None] = {}

    class FakeGoldenAnswerService:
        def __init__(self, database_url: str) -> None:
            created["golden"] = database_url

    class FakeMemoryServicePostgres:
        def __init__(self, database_url: str) -> None:
            created["memory"] = database_url

    class FakeMemoryOrchestrator:
        is_initialized = True

        def __init__(self, database_url: str | None = None) -> None:
            created["orchestrator"] = database_url

    monkeypatch.setattr(oracle_module, "config", SimpleNamespace(database_url="postgresql://test"))
    monkeypatch.setattr(oracle_module, "GoldenAnswerService", FakeGoldenAnswerService)
    monkeypatch.setattr(oracle_module, "MemoryServicePostgres", FakeMemoryServicePostgres)
    monkeypatch.setattr(oracle_module, "MemoryOrchestrator", FakeMemoryOrchestrator)

    golden_answer_service = service.golden_answer_service
    memory_service = service.memory_service
    memory_orchestrator = service.memory_orchestrator

    assert service.golden_answer_service is golden_answer_service
    assert service.memory_service is memory_service
    assert service.memory_orchestrator is memory_orchestrator
    assert created == {
        "golden": "postgresql://test",
        "memory": "postgresql://test",
        "orchestrator": "postgresql://test",
    }


@pytest.mark.asyncio
async def test_process_query_maps_agentic_result_and_stores_analytics() -> None:
    service = blank_service()
    service._memory_service = object()

    class FakeUserContext:
        memory_service: object | None = None

        async def get_full_user_context(self, user_email: str | None) -> dict[str, Any]:
            assert user_email == "owner@example.com"
            return {
                "profile": {"language": "id"},
                "personality": {"personality_type": "concise"},
                "memory_facts": ["prefers Bahasa"],
                "user_name": "Owner",
                "user_role": "admin",
            }

    class FakeLanguageDetector:
        def __init__(self) -> None:
            self.detected_query: str | None = None

        def detect_language(self, query: str) -> str:
            self.detected_query = query
            return "en"

        def get_target_language(
            self,
            query: str,
            *,
            language_override: str | None,
            user_language: str | None,
        ) -> str:
            assert query == "Explain investor KITAS"
            assert language_override is None
            return user_language or "en"

    class FakeAnalytics:
        def __init__(self) -> None:
            self.build_kwargs: dict[str, Any] | None = None
            self.stored: list[dict[str, Any]] = []

        def build_analytics_data(self, **kwargs: Any) -> dict[str, Any]:
            self.build_kwargs = kwargs
            return {"query_text": kwargs["query"]}

        async def store_query_analytics(self, analytics_data: dict[str, Any]) -> None:
            self.stored.append(analytics_data)

    class FakeOrchestrator:
        def __init__(self) -> None:
            self.received: dict[str, Any] | None = None

        async def process_query(self, **kwargs: Any) -> SimpleNamespace:
            self.received = kwargs
            return SimpleNamespace(
                answer="Investor KITAS requires a compliant sponsor.",
                sources=[{"title": "Visa Guide"}],
                model_used="agentic-rag",
                timings={"total": 0.25, "domain_scores": {"visa": 0.92}},
                is_ambiguous=False,
                clarification_question=None,
                document_count=2,
                collection_used="visa_oracle",
            )

    language_detector = FakeLanguageDetector()
    analytics = FakeAnalytics()
    orchestrator = FakeOrchestrator()
    service.user_context = FakeUserContext()
    service.language_detector = language_detector
    service.analytics = analytics

    async def fake_get_orchestrator(search_service: object) -> FakeOrchestrator:
        assert search_service == "search"
        return orchestrator

    service._get_orchestrator = fake_get_orchestrator

    result = await service.process_query(
        request_query="Explain investor KITAS",
        request_user_email="owner@example.com",
        request_limit=5,
        request_session_id="session-1",
        request_include_sources=True,
        request_use_ai=True,
        request_language_override=None,
        request_conversation_history=None,
        search_service="search",
    )

    assert result["success"] is True
    assert result["answer_language"] == "id"
    assert result["sources"] == [{"title": "Visa Guide"}]
    assert result["domain_confidence"] == {"visa": 0.92}
    assert result["user_memory_facts"] == ["prefers Bahasa"]
    assert language_detector.detected_query == "Explain investor KITAS"
    assert orchestrator.received == {
        "query": "Explain investor KITAS",
        "user_id": "owner@example.com",
        "conversation_history": [],
        "session_id": "session-1",
    }
    assert analytics.build_kwargs is not None
    assert analytics.build_kwargs["document_count"] == 2
    assert analytics.stored == [
        {"query_text": "Explain investor KITAS", "language_preference": "id"},
    ]


@pytest.mark.asyncio
async def test_process_query_records_error_analytics_on_runtime_failure() -> None:
    service = blank_service()
    service._memory_service = object()

    class FakeUserContext:
        async def get_full_user_context(self, user_email: str | None) -> dict[str, Any]:
            return {
                "profile": {},
                "personality": {},
                "memory_facts": [],
                "user_name": None,
                "user_role": None,
            }

    class FakeLanguageDetector:
        def detect_language(self, query: str) -> str:
            return "en"

        def get_target_language(
            self,
            query: str,
            *,
            language_override: str | None,
            user_language: str | None,
        ) -> str:
            return "en"

    class FakeAnalytics:
        def __init__(self) -> None:
            self.stored: list[dict[str, Any]] = []

        async def store_query_analytics(self, analytics_data: dict[str, Any]) -> None:
            self.stored.append(analytics_data)

    analytics = FakeAnalytics()
    service.user_context = FakeUserContext()
    service.language_detector = FakeLanguageDetector()
    service.analytics = analytics

    async def fake_get_orchestrator(search_service: object) -> object:
        raise RuntimeError("orchestrator failed")

    service._get_orchestrator = fake_get_orchestrator

    result = await service.process_query(
        request_query="bad query",
        request_user_email=None,
        request_limit=5,
        request_session_id=None,
        request_include_sources=False,
        request_use_ai=True,
        request_language_override=None,
        request_conversation_history=None,
        search_service=object(),
    )

    assert result["success"] is False
    assert result["error"] == "orchestrator failed"
    assert analytics.stored == [
        {"query_text": "bad query", "metadata": {"error": "orchestrator failed"}},
    ]


@pytest.mark.asyncio
async def test_submit_feedback_delegates_to_database_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feedback = {"user_email": "owner@example.com", "rating": 5}

    class FakeDatabaseManager:
        async def store_feedback(self, feedback_data: dict[str, Any]) -> dict[str, Any]:
            assert feedback_data is feedback
            return {"stored": True}

    monkeypatch.setattr(oracle_module, "db_manager", FakeDatabaseManager())

    assert await blank_service().submit_feedback(feedback) == {"stored": True}
