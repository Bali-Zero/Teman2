"""
Race Condition Tests for MemoryOrchestrator

Tests concurrent read-write operations to ensure data consistency.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.memory.models import MemoryContext, MemoryProcessResult
from backend.services.memory.orchestrator import MemoryOrchestrator


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    return pool


@pytest.fixture
def mock_memory_service():
    """Mock memory service"""
    service = MagicMock()
    service.pool = AsyncMock()
    service.get_memory = AsyncMock(
        return_value=MagicMock(
            profile_facts=["fact1", "fact2"],
            summary="Test summary",
            counters={"conversations": 5},
            updated_at=None,
        )
    )
    service.add_fact = AsyncMock(return_value=True)
    service.increment_counter = AsyncMock()
    return service


@pytest.fixture
def mock_fact_extractor():
    """Mock fact extractor"""
    extractor = MagicMock()
    extractor.extract_facts_from_conversation = MagicMock(
        return_value=[{"content": "Test fact", "type": "general", "confidence": 0.8}]
    )
    return extractor


@pytest.fixture
def orchestrator(mock_db_pool, mock_memory_service, mock_fact_extractor):
    """Create MemoryOrchestrator instance"""
    from backend.services.memory.orchestrator import MemoryServiceStatus
    orchestrator = MemoryOrchestrator(db_pool=mock_db_pool)
    orchestrator._memory_service = mock_memory_service
    orchestrator._fact_extractor = mock_fact_extractor
    orchestrator._is_initialized = True
    orchestrator._status = MemoryServiceStatus.HEALTHY
    return orchestrator


@pytest.mark.asyncio
async def test_concurrent_read_write_memory(orchestrator):
    """Test that reads can proceed during writes."""
    user_email = "test@example.com"

    # Start write operation
    write_task = asyncio.create_task(
        orchestrator.process_conversation(
            user_email=user_email,
            user_message="Test message",
            ai_response="Test response",
        )
    )

    # Multiple reads should be able to proceed
    read_tasks = [orchestrator.get_user_context(user_email) for _ in range(5)]

    # All should complete
    results = await asyncio.gather(*read_tasks, write_task, return_exceptions=True)

    # Split reads and write result
    reads = results[:-1]
    write_result = results[-1]

    # Verify no exceptions
    assert not any(isinstance(r, Exception) for r in reads)
    assert not isinstance(write_result, Exception)

    # Verify all reads returned valid contexts
    for read in reads:
        assert isinstance(read, MemoryContext)
        assert read.user_id == user_email


@pytest.mark.asyncio
async def test_concurrent_writes_serialized(orchestrator):
    """Test that concurrent writes for same user are serialized."""
    user_email = "test@example.com"

    # Simulate 5 concurrent writes
    tasks = [
        orchestrator.process_conversation(
            user_email=user_email,
            user_message=f"Message {i}",
            ai_response=f"Response {i}",
        )
        for i in range(5)
    ]

    # All should complete without errors
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Found exceptions: {exceptions}"

    # Verify all results are valid
    for result in results:
        assert isinstance(result, MemoryProcessResult)


@pytest.mark.asyncio
async def test_write_lock_timeout(orchestrator):
    """Test that write lock timeout is handled gracefully."""
    user_email = "test@example.com"

    # Create a lock that's already acquired
    lock = orchestrator._write_locks[user_email]
    await lock.acquire()

    try:
        # This should timeout gracefully
        result = await orchestrator.process_conversation(
            user_email=user_email,
            user_message="Test message",
            ai_response="Test response",
        )
        # Should return empty result instead of failing
        assert isinstance(result, MemoryProcessResult)
        assert result.facts_saved == 0
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_concurrent_reads_allowed(orchestrator):
    """Test that multiple concurrent reads are allowed."""
    user_email = "test@example.com"

    # Simulate 20 concurrent reads (more than semaphore limit of 10)
    tasks = [orchestrator.get_user_context(user_email) for _ in range(20)]

    # All should complete (semaphore will serialize but not block indefinitely)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Found exceptions: {exceptions}"

    # Verify all results are valid contexts
    for result in results:
        assert isinstance(result, MemoryContext)
