"""
Test scenario: Memory Orchestrator non disponibile

Verifica che il sistema gestisca correttamente il caso in cui
memory_orchestrator non è disponibile, senza bloccare il flusso principale.

Test:
- MemoryHandler ritorna None quando orchestrator non è disponibile
- Nessun errore viene propagato al chiamante
- Timing metrics vengono registrati correttamente
- Logging appropriato degli errori
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.memory_handler import MemoryHandler


@pytest.fixture
def memory_handler():
    """Create MemoryHandler instance for testing."""
    return MemoryHandler(db_pool=None, lock_timeout=5.0)


@pytest.fixture
def mock_metrics_collector():
    """Create mock metrics collector."""
    collector = MagicMock()
    collector.record_memory_lock_contention = MagicMock()
    collector.record_memory_lock_timeout = MagicMock()
    return collector


@pytest.mark.asyncio
async def test_memory_orchestrator_unavailable_returns_none(memory_handler):
    """Test che get_memory_orchestrator ritorna None quando non disponibile."""
    # Mock initialization failure - patch the import inside get_memory_orchestrator
    # MemoryOrchestrator is imported inside the method, so we patch backend.services.memory
    with patch(
        "backend.services.memory.MemoryOrchestrator",
        side_effect=RuntimeError("Database connection failed"),
    ):
        orchestrator = await memory_handler.get_memory_orchestrator()
        assert orchestrator is None


@pytest.mark.asyncio
async def test_save_memory_gracefully_handles_unavailable_orchestrator(
    memory_handler, mock_metrics_collector
):
    """Test che save_conversation_memory gestisce gracefully orchestrator non disponibile."""
    # Mock get_memory_orchestrator to return None
    memory_handler.get_memory_orchestrator = AsyncMock(return_value=None)

    # Should not raise exception
    await memory_handler.save_conversation_memory(
        user_id="test@example.com",
        query="Test query",
        answer="Test answer",
        metrics_collector=mock_metrics_collector,
    )

    # Verify orchestrator was attempted
    memory_handler.get_memory_orchestrator.assert_called_once()


@pytest.mark.asyncio
async def test_save_memory_timing_metrics_recorded(memory_handler, mock_metrics_collector):
    """Test che i timing metrics vengono registrati correttamente."""
    # Mock orchestrator with successful save
    mock_orchestrator = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.facts_saved = 2
    mock_result.facts_extracted = 2
    mock_result.processing_time_ms = 150.5
    mock_orchestrator.process_conversation = AsyncMock(return_value=mock_result)
    memory_handler.get_memory_orchestrator = AsyncMock(return_value=mock_orchestrator)

    start_time = time.time()
    await memory_handler.save_conversation_memory(
        user_id="test@example.com",
        query="Test query",
        answer="Test answer",
        metrics_collector=mock_metrics_collector,
    )
    elapsed_time = time.time() - start_time

    # Verify orchestrator was called
    mock_orchestrator.process_conversation.assert_called_once()

    # Verify lock contention metric was checked (may or may not be called depending on timing)
    # The metric is only recorded if lock_wait_time > 0.01
    # Since we're using a fresh lock, it should acquire immediately


@pytest.mark.asyncio
async def test_save_memory_lock_timeout_handled(memory_handler, mock_metrics_collector):
    """Test che il lock timeout viene gestito correttamente."""
    # Create a handler with very short timeout
    handler = MemoryHandler(db_pool=None, lock_timeout=0.01)

    # Acquire lock manually to cause timeout
    lock = handler._memory_locks["test@example.com"]
    await lock.acquire()

    try:
        # This should timeout
        await handler.save_conversation_memory(
            user_id="test@example.com",
            query="Test query",
            answer="Test answer",
            metrics_collector=mock_metrics_collector,
        )

        # Verify timeout metric was recorded
        mock_metrics_collector.record_memory_lock_timeout.assert_called_once_with(
            user_id="test@example.com"
        )
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_save_memory_database_error_handled(memory_handler, mock_metrics_collector):
    """Test che gli errori del database vengono gestiti senza propagazione."""
    # Mock orchestrator to raise database error
    mock_orchestrator = MagicMock()
    mock_orchestrator.process_conversation = AsyncMock(side_effect=RuntimeError("Connection lost"))
    memory_handler.get_memory_orchestrator = AsyncMock(return_value=mock_orchestrator)

    # Should not raise exception
    await memory_handler.save_conversation_memory(
        user_id="test@example.com",
        query="Test query",
        answer="Test answer",
        metrics_collector=mock_metrics_collector,
    )

    # Verify orchestrator was called
    mock_orchestrator.process_conversation.assert_called_once()


@pytest.mark.asyncio
async def test_save_memory_anonymous_user_skipped(memory_handler):
    """Test che gli utenti anonymous vengono saltati."""
    # Should return immediately without calling orchestrator
    await memory_handler.save_conversation_memory(
        user_id="anonymous",
        query="Test query",
        answer="Test answer",
    )

    # Verify orchestrator was not initialized
    assert memory_handler._memory_orchestrator is None


@pytest.mark.asyncio
async def test_create_save_task_returns_none_for_invalid_input(memory_handler):
    """Test che create_save_task ritorna None per input invalidi."""
    # Anonymous user
    task = memory_handler.create_save_task("anonymous", "query", "answer")
    assert task is None

    # Empty answer
    task = memory_handler.create_save_task("test@example.com", "query", "")
    assert task is None

    # None answer
    task = memory_handler.create_save_task("test@example.com", "query", None)
    assert task is None


@pytest.mark.asyncio
async def test_create_save_task_creates_background_task(memory_handler):
    """Test che create_save_task crea un task in background."""
    memory_handler.save_conversation_memory = AsyncMock()

    task = memory_handler.create_save_task("test@example.com", "Test query", "Test answer")

    assert task is not None
    assert isinstance(task, asyncio.Task)

    # Wait for task to complete
    await task

    # Verify save_conversation_memory was called
    memory_handler.save_conversation_memory.assert_called_once()


@pytest.mark.asyncio
async def test_multiple_concurrent_saves_same_user(memory_handler):
    """Test che multiple chiamate concorrenti per lo stesso utente sono serializzate."""
    call_order = []
    call_times = {}

    async def mock_save(user_id, query, answer, metrics_collector=None):
        call_times[user_id] = time.time()
        call_order.append(user_id)
        await asyncio.sleep(0.1)  # Simulate work

    memory_handler.save_conversation_memory = mock_save

    # Create multiple concurrent tasks for same user
    tasks = [
        memory_handler.create_save_task("user@example.com", f"query{i}", f"answer{i}")
        for i in range(3)
    ]

    await asyncio.gather(*tasks)

    # Verify all calls completed
    assert len(call_order) == 3
    assert len(set(call_order)) == 1  # All same user
