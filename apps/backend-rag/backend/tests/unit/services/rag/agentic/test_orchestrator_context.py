"""
Unit tests for OrchestratorContextManager

Test coverage target: >95%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.rag.agentic.orchestrator_context import OrchestratorContextManager


@pytest.fixture
def mock_memory_handler():
    """Mock MemoryHandler"""
    handler = MagicMock()
    handler.get_memory_orchestrator = AsyncMock(return_value=MagicMock())
    return handler


@pytest.fixture
def mock_context_window_manager():
    """Mock ContextWindowManager"""
    manager = MagicMock()
    manager.trim_conversation_history = MagicMock(
        return_value={
            "needs_summarization": False,
            "trimmed_messages": [{"role": "user", "content": "test"}],
            "messages_to_summarize": [],
            "context_summary": None,
        }
    )
    manager.generate_summary = AsyncMock(return_value="Summary")
    manager.inject_summary_into_history = MagicMock(
        return_value=[{"role": "assistant", "content": "Summary"}]
    )
    return manager


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return MagicMock()


@pytest.fixture
def context_manager(mock_memory_handler, mock_context_window_manager, mock_db_pool):
    """Create OrchestratorContextManager instance"""
    return OrchestratorContextManager(
        memory_handler=mock_memory_handler,
        context_window_manager=mock_context_window_manager,
        db_pool=mock_db_pool,
    )


@pytest.mark.asyncio
async def test_load_user_context_success(context_manager, mock_memory_handler):
    """Test successful user context loading"""
    mock_context = {
        "profile": {"id": "user123", "email": "test@example.com"},
        "facts": [{"fact": "test"}],
        "collective_facts": [],
        "history": [],
    }

    with patch(
        "backend.services.rag.agentic.orchestrator_context.get_user_context",
        new_callable=AsyncMock,
        return_value=mock_context,
    ):
        result = await context_manager.load_user_context(
            user_id="user123", query="test query", session_id="session123"
        )

        assert result == mock_context
        mock_memory_handler.get_memory_orchestrator.assert_called_once()


@pytest.mark.asyncio
async def test_load_user_context_error_fallback(context_manager, mock_memory_handler):
    """Test user context loading with error fallback"""
    mock_memory_handler.get_memory_orchestrator.side_effect = Exception("DB error")

    with patch(
        "backend.services.rag.agentic.orchestrator_context.get_user_context",
        new_callable=AsyncMock,
        side_effect=Exception("Connection failed"),
    ):
        result = await context_manager.load_user_context(
            user_id="user123", query="test query"
        )

        assert result == {
            "profile": None,
            "facts": [],
            "collective_facts": [],
            "history": [],
        }


@pytest.mark.asyncio
async def test_prepare_conversation_history_valid(context_manager):
    """Test preparing valid conversation history"""
    user_context = {"history": [{"role": "user", "content": "test"}]}
    result = context_manager.prepare_conversation_history(None, user_context)

    assert result == [{"role": "user", "content": "test"}]


@pytest.mark.asyncio
async def test_prepare_conversation_history_invalid(context_manager):
    """Test preparing invalid conversation history"""
    # Invalid: not a list
    result = context_manager.prepare_conversation_history("not a list", {})
    assert result == []

    # Invalid: list but not dicts
    result = context_manager.prepare_conversation_history(["not", "dict"], {})
    assert result == []


@pytest.mark.asyncio
async def test_apply_context_window_management_no_summarization(
    context_manager, mock_context_window_manager
):
    """Test context window management without summarization"""
    history = [{"role": "user", "content": "test"}]
    result = await context_manager.apply_context_window_management(history)

    assert result == [{"role": "user", "content": "test"}]
    mock_context_window_manager.trim_conversation_history.assert_called_once_with(history)
    mock_context_window_manager.generate_summary.assert_not_called()


@pytest.mark.asyncio
async def test_apply_context_window_management_with_summarization(
    context_manager, mock_context_window_manager
):
    """Test context window management with summarization"""
    mock_context_window_manager.trim_conversation_history.return_value = {
        "needs_summarization": True,
        "trimmed_messages": [{"role": "user", "content": "recent"}],
        "messages_to_summarize": [{"role": "user", "content": "old"}],
        "context_summary": None,
    }

    history = [{"role": "user", "content": "old"}, {"role": "user", "content": "recent"}]
    result = await context_manager.apply_context_window_management(history)

    assert result == [{"role": "assistant", "content": "Summary"}]
    mock_context_window_manager.generate_summary.assert_called_once()
    mock_context_window_manager.inject_summary_into_history.assert_called_once()


@pytest.mark.asyncio
async def test_apply_context_window_management_summarization_error(
    context_manager, mock_context_window_manager
):
    """Test context window management with summarization error"""
    mock_context_window_manager.trim_conversation_history.return_value = {
        "needs_summarization": True,
        "trimmed_messages": [{"role": "user", "content": "recent"}],
        "messages_to_summarize": [{"role": "user", "content": "old"}],
        "context_summary": None,
    }
    mock_context_window_manager.generate_summary.side_effect = Exception("Summary failed")

    history = [{"role": "user", "content": "old"}]
    result = await context_manager.apply_context_window_management(history)

    assert result == [{"role": "user", "content": "recent"}]


@pytest.mark.asyncio
async def test_get_full_context_success(context_manager):
    """Test getting full context successfully"""
    mock_context = {
        "profile": {"id": "user123"},
        "facts": [{"fact": "test"}],
        "collective_facts": [],
        "history": [{"role": "user", "content": "test"}],
    }

    with patch.object(
        context_manager, "load_user_context", new_callable=AsyncMock, return_value=mock_context
    ), patch.object(
        context_manager,
        "prepare_conversation_history",
        return_value=[{"role": "user", "content": "test"}],
    ), patch.object(
        context_manager,
        "apply_context_window_management",
        new_callable=AsyncMock,
        return_value=[{"role": "user", "content": "test"}],
    ):
        user_context, history = await context_manager.get_full_context(
            user_id="user123", query="test", session_id="session123"
        )

        assert user_context == mock_context
        assert history == [{"role": "user", "content": "test"}]


@pytest.mark.asyncio
async def test_get_full_context_empty_history(context_manager):
    """Test getting full context with empty history"""
    mock_context = {"profile": None, "facts": [], "collective_facts": [], "history": []}

    with patch.object(
        context_manager, "load_user_context", new_callable=AsyncMock, return_value=mock_context
    ), patch.object(
        context_manager, "prepare_conversation_history", return_value=[]
    ), patch.object(
        context_manager,
        "apply_context_window_management",
        new_callable=AsyncMock,
        return_value=[],
    ):
        user_context, history = await context_manager.get_full_context(
            user_id="user123", query="test"
        )

        assert history == []
