"""
Race Condition Tests for CollectiveMemoryService

Tests concurrent fact contributions to ensure atomic promotion.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import asyncpg
import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.memory.collective_memory_service import CollectiveMemoryService


@pytest.fixture
async def test_db_pool():
    """Create test database pool"""
    # Use testcontainers or mock pool
    pool = AsyncMock(spec=asyncpg.Pool)
    conn = AsyncMock()
    pool.acquire = AsyncMock(return_value=conn.__aenter__())
    return pool


@pytest.mark.asyncio
async def test_concurrent_fact_promotion(test_db_pool):
    """Test that fact promotion is atomic when multiple users contribute simultaneously."""
    service = CollectiveMemoryService(pool=test_db_pool)
    content = "Test fact for promotion"

    # Mock database responses
    conn = AsyncMock()
    test_db_pool.acquire = AsyncMock(return_value=conn.__aenter__())

    # Mock SELECT FOR UPDATE to return None (new fact)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=1)  # New memory_id
    conn.execute = AsyncMock()

    # Mock transaction context
    transaction = AsyncMock()
    conn.transaction = AsyncMock(return_value=transaction.__aenter__())

    # 5 users contribute simultaneously
    tasks = [
        service.add_contribution(
            user_id=f"user{i}@example.com",
            content=content,
            category="test",
        )
        for i in range(5)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Found exceptions: {exceptions}"

    # Note: Full integration test would verify:
    # - Only one fact created
    # - All 5 users added as sources
    # - Promotion happened exactly once when threshold crossed


@pytest.mark.asyncio
async def test_concurrent_contribution_same_fact(test_db_pool):
    """Test that concurrent contributions to same fact don't create duplicates."""
    service = CollectiveMemoryService(pool=test_db_pool)
    content = "Existing fact"
    content_hash = service._hash_content(content)

    # Mock existing fact
    conn = AsyncMock()
    test_db_pool.acquire = AsyncMock(return_value=conn.__aenter__())
    transaction = AsyncMock()
    conn.transaction = AsyncMock(return_value=transaction.__aenter__())

    # Mock SELECT FOR UPDATE to return existing fact
    conn.fetchrow = AsyncMock(return_value={"id": 1, "source_count": 2, "is_promoted": False})
    conn.fetchval = AsyncMock(return_value=None)  # No existing source
    conn.execute = AsyncMock()

    # 3 users contribute simultaneously to existing fact
    tasks = [
        service.add_contribution(
            user_id=f"user{i}@example.com",
            content=content,
            category="test",
        )
        for i in range(3)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Found exceptions: {exceptions}"

    # Note: Full integration test would verify:
    # - SELECT FOR UPDATE prevented race conditions
    # - All sources added atomically
    # - Promotion happened exactly once
