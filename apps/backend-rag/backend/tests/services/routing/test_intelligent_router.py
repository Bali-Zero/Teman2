from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any

import pytest

from backend.services.routing.intelligent_router import IntelligentRouter


class FakeOrchestrator:
    def __init__(self, result: Any | None = None) -> None:
        self.result = result or SimpleNamespace(
            answer="Use the visa oracle answer.",
            sources=[{"title": "Visa"}],
            routing_stats={"route": "visa"},
        )
        self.initialized = False
        self.process_calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        self.initialized = True

    async def process_query(self, **kwargs: Any) -> Any:
        self.process_calls.append(kwargs)
        return self.result

    async def stream_query(self, **kwargs: Any) -> AsyncGenerator[dict[str, str], None]:
        self.stream_calls.append(kwargs)
        yield {"type": "token", "content": "hello"}
        yield {"type": "done"}


def make_router(orchestrator: FakeOrchestrator) -> IntelligentRouter:
    router = IntelligentRouter.__new__(IntelligentRouter)
    router.orchestrator = orchestrator
    return router


@pytest.mark.asyncio
async def test_initialize_delegates_to_orchestrator() -> None:
    orchestrator = FakeOrchestrator()
    router = make_router(orchestrator)

    await router.initialize()

    assert orchestrator.initialized is True


@pytest.mark.asyncio
async def test_route_chat_maps_core_result_to_webapp_contract() -> None:
    orchestrator = FakeOrchestrator()
    router = make_router(orchestrator)

    result = await router.route_chat(
        message="How do I apply for KITAS?",
        user_id="user-1",
        conversation_history=[{"role": "user", "content": "hi"}],
    )

    assert result == {
        "response": "Use the visa oracle answer.",
        "ai_used": "agentic-rag",
        "category": "agentic",
        "model": "gemini-2.0-flash-lite",
        "tokens": {},
        "used_rag": True,
        "used_tools": False,
        "tools_called": [],
        "sources": [{"title": "Visa"}],
        "routing_stats": {"route": "visa"},
    }
    assert orchestrator.process_calls == [
        {
            "query": "How do I apply for KITAS?",
            "user_id": "user-1",
            "conversation_history": [{"role": "user", "content": "hi"}],
        },
    ]


@pytest.mark.asyncio
async def test_route_chat_accepts_dict_result_for_backward_compatibility() -> None:
    router = make_router(
        FakeOrchestrator(
            {
                "answer": "Dictionary answer",
                "sources": [{"title": "Source"}],
            },
        ),
    )

    result = await router.route_chat("question", "user-1")

    assert result["response"] == "Dictionary answer"
    assert result["sources"] == [{"title": "Source"}]
    assert "routing_stats" not in result


@pytest.mark.asyncio
async def test_stream_chat_passes_through_orchestrator_chunks() -> None:
    orchestrator = FakeOrchestrator()
    router = make_router(orchestrator)

    chunks = [
        chunk
        async for chunk in router.stream_chat(
            message="stream it",
            user_id="user-1",
            conversation_history=[],
            session_id="frontend-session",
        )
    ]

    assert chunks == [{"type": "token", "content": "hello"}, {"type": "done"}]
    assert orchestrator.stream_calls == [
        {
            "query": "stream it",
            "user_id": "user-1",
            "conversation_history": [],
            "session_id": None,
        },
    ]


def test_get_stats_reports_agentic_wrapper() -> None:
    assert IntelligentRouter.__new__(IntelligentRouter).get_stats() == {
        "router": "agentic_rag_wrapper",
        "model": "gemini-2.0-flash-lite",
        "rag_available": True,
    }
