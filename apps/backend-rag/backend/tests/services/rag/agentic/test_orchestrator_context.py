from unittest.mock import AsyncMock, patch

import pytest

from backend.services.rag.agentic.orchestrator_context import OrchestratorContextManager


@pytest.mark.asyncio
async def test_prepare_query_context_delegates_history_to_context_window_manager() -> None:
    memory_handler = AsyncMock()
    memory_orchestrator = object()
    memory_handler.get_memory_orchestrator.return_value = memory_orchestrator

    context_window_manager = AsyncMock()
    optimized_history = [
        {"role": "system", "content": "[Earlier conversation summary]: older turns"},
        {"role": "user", "content": "recent"},
    ]
    context_window_manager.manage_context.return_value = optimized_history

    manager = OrchestratorContextManager(
        db_pool=object(),
        memory_handler=memory_handler,
        context_window_manager=context_window_manager,
    )
    incoming_history = [{"role": "user", "content": "old"}]

    with patch(
        "backend.services.rag.agentic.orchestrator_context._context_manager_module.get_user_context",
        new=AsyncMock(
            return_value={
                "profile": {"id": "user-1"},
                "history": [{"role": "assistant", "content": "stored"}],
                "memory_facts": ["fact"],
                "collective_facts": [],
            },
        ),
    ) as get_user_context:
        context_data = await manager.prepare_query_context(
            user_id="user-1",
            query="current question",
            conversation_history=incoming_history,
        )

    assert context_data["history"] == optimized_history
    memory_handler.get_memory_orchestrator.assert_awaited_once()
    get_user_context.assert_awaited_once_with(
        db_pool=manager.db_pool,
        user_id="user-1",
        memory_orchestrator=memory_orchestrator,
        query="current question",
        deep_think_mode=False,
        session_id=None,
    )
    context_window_manager.manage_context.assert_awaited_once_with(
        incoming_history,
        query="current question",
    )


@pytest.mark.asyncio
async def test_prepare_query_context_gracefully_falls_back_on_context_failure() -> None:
    memory_handler = AsyncMock()
    memory_handler.get_memory_orchestrator.side_effect = RuntimeError("memory down")
    manager = OrchestratorContextManager(
        db_pool=object(),
        memory_handler=memory_handler,
        context_window_manager=AsyncMock(),
    )
    history = [{"role": "user", "content": "keep me"}]

    context_data = await manager.prepare_query_context(
        user_id="user-1",
        query="question",
        conversation_history=history,
    )

    assert context_data == {
        "profile": {},
        "history": history,
        "memory_facts": [],
        "collective_facts": [],
    }


@pytest.mark.asyncio
async def test_get_full_context_returns_context_and_optimized_history() -> None:
    manager = OrchestratorContextManager(
        db_pool=object(),
        memory_handler=AsyncMock(),
        context_window_manager=AsyncMock(),
    )
    manager.prepare_query_context = AsyncMock(
        return_value={"profile": {"id": "user-1"}, "history": [{"role": "user"}]},
    )

    context_data, optimized_history = await manager.get_full_context(
        user_id="user-1",
        query="question",
        conversation_history=[{"role": "user"}],
        session_id="session-1",
    )

    assert context_data["profile"] == {"id": "user-1"}
    assert optimized_history == [{"role": "user"}]
    manager.prepare_query_context.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_context_window_management_summarizes_when_requested() -> None:
    class FakeContextWindowManager:
        def trim_conversation_history(self, history):
            assert history
            return {
                "needs_summarization": True,
                "messages_to_summarize": [{"role": "user", "content": "old"}],
                "trimmed_messages": [{"role": "user", "content": "recent"}],
            }

        async def generate_summary(self, messages):
            assert messages == [{"role": "user", "content": "old"}]
            return "summary"

        def inject_summary_into_history(self, recent_messages, summary):
            assert recent_messages == [{"role": "user", "content": "recent"}]
            assert summary == "summary"
            return [
                {"role": "system", "content": "summary"},
                {"role": "user", "content": "recent"},
            ]

    context_window_manager = FakeContextWindowManager()
    manager = OrchestratorContextManager(
        db_pool=object(),
        memory_handler=AsyncMock(),
        context_window_manager=context_window_manager,
    )

    optimized = await manager.apply_context_window_management(
        [{"role": "user", "content": "old"}, {"role": "user", "content": "recent"}],
    )

    assert optimized == [
        {"role": "system", "content": "summary"},
        {"role": "user", "content": "recent"},
    ]


@pytest.mark.asyncio
async def test_enrich_user_context_preserves_existing_non_null_fields() -> None:
    memory_handler = AsyncMock()
    memory_handler.get_memory_orchestrator.return_value = object()
    manager = OrchestratorContextManager(
        db_pool=object(),
        memory_handler=memory_handler,
        context_window_manager=AsyncMock(),
    )

    with patch(
        "backend.services.rag.agentic.orchestrator_context._context_manager_module.get_user_context",
        new=AsyncMock(return_value={"profile": {"id": "fresh"}, "memory_facts": ["new"]}),
    ):
        enriched = await manager.enrich_user_context(
            user_context={"profile": {"id": "existing"}, "history": None},
            user_id="user-1",
            query="question",
        )

    assert enriched == {"profile": {"id": "existing"}, "memory_facts": ["new"]}
