"""
Race Condition Tests for AgenticRAGOrchestrator

Tests concurrent memory save operations to ensure no data corruption.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.memory import MemoryOrchestrator
from services.memory.models import MemoryProcessResult
from services.rag.agentic.orchestrator import AgenticRAGOrchestrator


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    return pool


@pytest.fixture
def mock_memory_orchestrator():
    """Mock memory orchestrator"""
    orchestrator = AsyncMock(spec=MemoryOrchestrator)
    orchestrator.process_conversation = AsyncMock(
        return_value=MemoryProcessResult(
            facts_extracted=1,
            facts_saved=1,
            processing_time_ms=10.0,
        )
    )
    orchestrator.get_user_context = AsyncMock(
        return_value=MagicMock(has_data=True, facts=["fact1", "fact2"])
    )
    return orchestrator


@pytest.fixture
def orchestrator(mock_db_pool, mock_memory_orchestrator):
    """Create AgenticRAGOrchestrator instance"""
    tools = []
    orchestrator = AgenticRAGOrchestrator(
        tools=tools,
        db_pool=mock_db_pool,
    )
    # Inject mock memory orchestrator
    orchestrator._memory_orchestrator = mock_memory_orchestrator
    return orchestrator


@pytest.mark.asyncio
async def test_concurrent_memory_save_same_user(orchestrator, mock_memory_orchestrator):
    """Test that concurrent memory saves for same user don't corrupt data."""
    user_id = "test@example.com"

    # Simulate 10 concurrent saves
    tasks = [
        orchestrator._save_conversation_memory(
            user_id=user_id,
            query=f"Query {i}",
            answer=f"Response {i}",
        )
        for i in range(10)
    ]

    # All should complete without errors
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Found exceptions: {exceptions}"

    # Verify all calls were made (may be serialized due to lock)
    assert mock_memory_orchestrator.process_conversation.call_count == 10


@pytest.mark.asyncio
async def test_memory_save_lock_timeout(orchestrator):
    """Test that lock timeout is handled gracefully."""
    user_id = "test@example.com"

    # Create a lock that's already acquired
    lock = orchestrator._memory_locks[user_id]
    await lock.acquire()

    try:
        # This should timeout gracefully
        await orchestrator._save_conversation_memory(
            user_id=user_id,
            query="Test query",
            answer="Test answer",
        )
        # Should not raise exception, just log warning
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_concurrent_memory_save_different_users(orchestrator, mock_memory_orchestrator):
    """Test that concurrent saves for different users proceed in parallel."""
    user_ids = [f"user{i}@example.com" for i in range(5)]

    # Simulate concurrent saves for different users
    tasks = [
        orchestrator._save_conversation_memory(
            user_id=user_id,
            query=f"Query from {user_id}",
            answer=f"Response for {user_id}",
        )
        for user_id in user_ids
    ]

    # All should complete without errors
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Found exceptions: {exceptions}"

    # Verify all calls were made
    assert mock_memory_orchestrator.process_conversation.call_count == 5

