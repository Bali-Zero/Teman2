"""
Performance tests for context_manager.py parallel loading optimization.

These tests prove that Profile + Memory are fetched CONCURRENTLY rather than one
after the other.

They deliberately do NOT assert a wall-clock ceiling. They used to: `total_time
< 0.4` against a 250ms floor left 150ms of headroom, and the sibling failure test
left 100ms. On 2026-07-27 the first one failed at 0.447s while the fleet was at
load 50 — the machine was slow, the code was not sequential. That is a gate that
measures the runner instead of the diff, and it hard-blocks the pre-push gate for
every branch, including diffs nowhere near this module (same family as the four
gates cured in #3144).

What is asserted instead is the actual property, which no amount of load can
falsify: the two loads' [start, end] intervals OVERLAP. Sequential execution
cannot produce overlapping intervals however fast or slow the box is; concurrent
execution always does. The remaining bounds are floors and self-scaling ratios,
never absolute ceilings — a floor can only be violated by the code, never by a
busy scheduler.
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


DB_DELAY = 0.2  # 200ms — typical profile query
MEMORY_DELAY = 0.25  # 250ms — typical memory fetch


@pytest.fixture
def timeline():
    """Records `{name: (start, end)}` on a monotonic clock for each mocked load.

    Monotonic, not wall clock: NTP steps must not be able to invert an interval.
    """
    return {}


@pytest.fixture
def mock_memory_orchestrator(timeline):
    """Mock MemoryOrchestrator with simulated delay"""
    orchestrator = MagicMock()

    async def delayed_get_user_context(user_id, query=None):
        started = time.monotonic()
        # Simulate network/DB delay (200-300ms typical)
        await asyncio.sleep(MEMORY_DELAY)  # 250ms delay
        timeline["memory"] = (started, time.monotonic())
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
def mock_db_with_delay(mock_db_pool, timeline):
    """Mock DB pool with simulated delay"""

    async def delayed_fetchrow(*args, **kwargs):
        started = time.monotonic()
        # Simulate DB query delay (200-300ms typical)
        await asyncio.sleep(DB_DELAY)  # 200ms delay
        timeline["db"] = (started, time.monotonic())
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
    mock_get_cache,
    mock_db_with_delay,
    mock_memory_orchestrator,
    timeline,
):
    """
    Profile and Memory must be fetched CONCURRENTLY, not one after the other.

    Sequential would be ~450ms (200ms DB + 250ms Memory); concurrent is ~250ms,
    the max of the two. The assertion is on the overlap of the two intervals,
    not on the elapsed total — see this module's docstring for why the old
    wall-clock ceiling had to go.
    """

    mock_cache = MagicMock()
    mock_cache.get_entities = MagicMock(return_value={})
    mock_get_cache.return_value = mock_cache

    start_time = time.monotonic()

    result = await get_user_context(
        db_pool=mock_db_with_delay,
        user_id="test@example.com",
        memory_orchestrator=mock_memory_orchestrator,
        query="Test query",
    )

    total_time = time.monotonic() - start_time

    # Verify results
    assert result["profile"] is not None
    assert len(result["facts"]) == 2

    # Both loads actually ran (a timeline entry missing would make every
    # timing claim below vacuously true).
    assert "db" in timeline, "the profile query never ran"
    assert "memory" in timeline, "the memory fetch never ran"
    db_start, db_end = timeline["db"]
    mem_start, mem_end = timeline["memory"]

    # THE property: the two intervals overlap. Sequential execution cannot
    # produce this on any machine, at any speed; concurrent execution always
    # does. Load can stretch both intervals but never separate them.
    assert db_start < mem_end and mem_start < db_end, (
        "profile and memory did not overlap — they ran sequentially: "
        f"db=[{db_start:.3f}, {db_end:.3f}] memory=[{mem_start:.3f}, {mem_end:.3f}]"
    )

    overlap = min(db_end, mem_end) - max(db_start, mem_start)
    # A FLOOR, not a ceiling: only the code can violate it (by not sleeping the
    # mocked delays), never a busy scheduler — load only pushes it up.
    assert total_time >= max(DB_DELAY, MEMORY_DELAY), (
        f"total {total_time:.3f}s is below the slowest mocked delay — the mocks did not run"
    )

    print("\n⚡ Concurrency check:")
    print(f"   overlap: {overlap:.3f}s (sequential would be <= 0)")
    print(f"   total: {total_time:.3f}s (sequential floor {DB_DELAY + MEMORY_DELAY:.3f}s)")


@pytest.mark.asyncio
@patch("backend.services.rag.agentic.context_manager.get_memory_cache")
async def test_the_overlap_assertion_catches_sequential_loading(
    mock_get_cache,
    mock_db_with_delay,
    mock_memory_orchestrator,
    timeline,
):
    """GUILT: prove the overlap check above is not decorative.

    Replace `asyncio.gather` inside the module under test with a shim that awaits
    the coroutines one after another — the regression this file exists to catch —
    and confirm the intervals then do NOT overlap. Without this, a check that only
    ever sees the healthy path is a check that has never been shown to fail.
    """

    mock_cache = MagicMock()
    mock_cache.get_entities = MagicMock(return_value={})
    mock_get_cache.return_value = mock_cache

    async def sequential_gather(*coros, **kwargs):
        results = []
        for coro in coros:
            try:
                results.append(await coro)
            except Exception as exc:  # mirror gather(return_exceptions=True)
                if not kwargs.get("return_exceptions"):
                    raise
                results.append(exc)
        return results

    with patch(
        "backend.services.rag.agentic.context_manager.asyncio.gather",
        new=sequential_gather,
    ):
        await get_user_context(
            db_pool=mock_db_with_delay,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
            query="Test query",
        )

    db_start, db_end = timeline["db"]
    mem_start, mem_end = timeline["memory"]
    overlapped = db_start < mem_end and mem_start < db_end
    assert not overlapped, (
        "the intervals still overlapped under a deliberately SEQUENTIAL gather — "
        "the overlap assertion in test_parallel_loading_timing cannot fail, so it "
        "proves nothing"
    )


@pytest.mark.asyncio
@patch("backend.services.rag.agentic.context_manager.get_memory_cache")
async def test_parallel_loading_with_one_failure(mock_get_cache, mock_db_with_delay, timeline):
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

    start_time = time.monotonic()

    result = await get_user_context(
        db_pool=mock_db_with_delay,
        user_id="test@example.com",
        memory_orchestrator=failing_orchestrator,
    )

    total_time = time.monotonic() - start_time

    # Should still get profile even if memory fails
    assert result["profile"] is not None
    assert result["facts"] == []  # Empty due to failure
    assert result["collective_facts"] == []

    # The DB query is the only thing that should have taken time here — the
    # memory orchestrator raises immediately. Expressed as a RATIO of the
    # measured DB span rather than an absolute ceiling (`total_time < 0.3` had
    # only 100ms of headroom over its own 200ms floor, so a busy box failed it):
    # under load the DB span inflates too, so the ratio holds while a genuine
    # regression — a serialized retry/backoff on the failing branch — would add
    # time comparable to a whole delay and still trip it.
    assert "db" in timeline, "the profile query never ran"
    db_start, db_end = timeline["db"]
    db_span = db_end - db_start
    outside_db = total_time - db_span
    assert outside_db < db_span, (
        f"{outside_db:.3f}s spent outside the profile query (span {db_span:.3f}s) — "
        "the failing memory branch looks serialized, not fail-fast"
    )


@pytest.mark.asyncio
@patch("backend.services.rag.agentic.context_manager.get_memory_cache")
async def test_parallel_loading_logs_timing(
    mock_get_cache,
    mock_db_pool,
    mock_memory_orchestrator,
    caplog,
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
