"""
Performance tests for context_manager.py parallel loading optimization.

These tests measure the timing improvement from parallelizing Profile + Memory fetch.
Target: 200-400ms speedup vs sequential execution.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.memory import MemoryContext
from backend.services.rag.agentic.context_manager import get_user_context


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool"""
    pool = AsyncMock()
    mock_acquire = AsyncMock()
    mock_connection = AsyncMock()
    mock_connection.fetchrow = AsyncMock(
        return_value={
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": "Sales",
            "preferred_language": "it",
            "notes": "Test notes",
            "email": "test@example.com",
            "latest_conversation": None,
        },
    )
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_connection)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=mock_acquire)
    return pool


@pytest.fixture
def mock_memory_orchestrator():
    """Mock MemoryOrchestrator with simulated delay"""
    orchestrator = MagicMock()

    async def delayed_get_user_context(user_id, query=None):
        # Simulate network/DB delay (200-300ms typical)
        await asyncio.sleep(0.25)  # 250ms delay
        return MemoryContext(
            user_id=user_id,
            profile_facts=["Fact 1", "Fact 2"],
            collective_facts=["Collective fact 1"],
            timeline_summary="Timeline summary",
            kg_entities=[{"type": "person", "name": "John"}],
            summary="Conversation summary",
            counters={"conversations": 5, "searches": 10, "tasks": 2},
            has_data=True,
        )

    orchestrator.get_user_context = delayed_get_user_context
    return orchestrator


@pytest.fixture
def mock_db_with_delay(mock_db_pool):
    """Mock DB pool with simulated delay"""

    async def delayed_fetchrow(*args, **kwargs):
        # Simulate DB query delay (200-300ms typical)
        await asyncio.sleep(0.2)  # 200ms delay
        return {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": "Sales",
            "preferred_language": "it",
            "notes": "Test notes",
            "email": "test@example.com",
            "latest_conversation": None,
        }

    mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = delayed_fetchrow
    return mock_db_pool


@pytest.mark.asyncio
@patch("backend.services.rag.agentic.context_manager.get_memory_cache")
async def test_parallel_loading_timing(
    mock_get_cache, mock_db_with_delay, mock_memory_orchestrator,
):
    """
    Test that parallel loading is faster than sequential.

    Expected:
    - Sequential: ~450ms (200ms DB + 250ms Memory)
    - Parallel: ~250ms (max of the two)
    - Speedup: ~200ms
    """

    mock_cache = MagicMock()
    mock_cache.get_entities = MagicMock(return_value={})
    mock_get_cache.return_value = mock_cache

    start_time = time.time()

    result = await get_user_context(
        db_pool=mock_db_with_delay,
        user_id="test@example.com",
        memory_orchestrator=mock_memory_orchestrator,
        query="Test query",
    )

    total_time = time.time() - start_time

    # Verify results
    assert result["profile"] is not None
    assert len(result["facts"]) == 2

    # Verify timing: parallel should be ~max(DB, Memory) not sum
    # With 200ms DB + 250ms Memory, parallel should be ~250ms
    # Sequential would be ~450ms
    assert total_time < 0.4, f"Parallel loading took {total_time:.3f}s, expected < 0.4s"

    # Log the improvement
    estimated_sequential = 0.45  # 200ms + 250ms
    speedup = estimated_sequential - total_time
    print("\n⚡ Performance Test Results:")
    print(f"   Parallel time: {total_time:.3f}s")
    print(f"   Estimated sequential: {estimated_sequential:.3f}s")
    print(f"   Speedup: {speedup:.3f}s ({speedup / estimated_sequential * 100:.1f}% faster)")


@pytest.mark.asyncio
@patch("backend.services.rag.agentic.context_manager.get_memory_cache")
async def test_parallel_loading_with_one_failure(mock_get_cache, mock_db_with_delay):
    """
    Test that parallel loading continues even if one task fails.
    """

    mock_cache = MagicMock()
    mock_cache.get_entities = MagicMock(return_value={})
    mock_get_cache.return_value = mock_cache

    # Memory orchestrator that fails
    failing_orchestrator = MagicMock()
    failing_orchestrator.get_user_context = AsyncMock(
        side_effect=Exception("Memory service unavailable"),
    )

    start_time = time.time()

    result = await get_user_context(
        db_pool=mock_db_with_delay,
        user_id="test@example.com",
        memory_orchestrator=failing_orchestrator,
    )

    total_time = time.time() - start_time

    # Should still get profile even if memory fails
    assert result["profile"] is not None
    assert result["facts"] == []  # Empty due to failure
    assert result["collective_facts"] == []

    # Should complete quickly (only DB delay, not waiting for memory)
    assert total_time < 0.3, f"Should complete quickly even with memory failure: {total_time:.3f}s"


@pytest.mark.asyncio
@patch("backend.services.rag.agentic.context_manager.get_memory_cache")
async def test_parallel_loading_logs_timing(
    mock_get_cache, mock_db_pool, mock_memory_orchestrator, caplog,
):
    """
    Test that timing metrics are logged correctly.
    """
    import logging

    mock_cache = MagicMock()
    mock_cache.get_entities = MagicMock(return_value={})
    mock_get_cache.return_value = mock_cache

    with caplog.at_level(logging.INFO):
        await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
        )

    # Check that timing logs are present
    log_messages = caplog.text

    assert "Profile fetch:" in log_messages
    assert "Memory fetch:" in log_messages
    assert "PARALLEL LOADING completed" in log_messages
    assert "speedup:" in log_messages.lower()
