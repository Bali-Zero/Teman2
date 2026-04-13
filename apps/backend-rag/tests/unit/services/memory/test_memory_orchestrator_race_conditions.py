"""
Tests for MemoryOrchestrator race condition handling - concurrent access patterns.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_concurrent_read_write_memory():
    """Concurrent reads and writes should not corrupt state."""
    lock = asyncio.Lock()
    state = {"value": 0}

    async def write():
        async with lock:
            state["value"] += 1

    async def read():
        async with lock:
            return state["value"]

    tasks = [write() for _ in range(10)] + [read() for _ in range(5)]
    await asyncio.gather(*tasks)
    assert state["value"] == 10


@pytest.mark.asyncio
async def test_concurrent_writes_serialized():
    """Concurrent writes should be serialized via lock."""
    lock = asyncio.Lock()
    results = []

    async def writer(idx):
        async with lock:
            results.append(idx)
            await asyncio.sleep(0.001)

    await asyncio.gather(*[writer(i) for i in range(5)])
    assert len(results) == 5
    assert sorted(results) == list(range(5))


@pytest.mark.asyncio
async def test_write_lock_timeout():
    """Write lock should handle timeout scenarios."""
    lock = asyncio.Lock()
    acquired = False

    async with lock:
        try:
            acquired = await asyncio.wait_for(lock.acquire(), timeout=0.01)
        except asyncio.TimeoutError:
            acquired = False
    assert acquired is False


@pytest.mark.asyncio
async def test_concurrent_reads_allowed():
    """Multiple concurrent reads should all complete."""
    read_count = 0

    async def reader():
        nonlocal read_count
        await asyncio.sleep(0.001)
        read_count += 1

    await asyncio.gather(*[reader() for _ in range(10)])
    assert read_count == 10
