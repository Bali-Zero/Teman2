"""
Tests for MemoryHandler — race condition protection, lock eviction, background tasks.
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.memory_handler import MemoryHandler


# ============================================================
# Fixtures
# ============================================================


@dataclass
class FakeProcessResult:
    success: bool = True
    facts_extracted: int = 3
    facts_saved: int = 2
    processing_time_ms: float = 15.0


@pytest.fixture
def handler() -> MemoryHandler:
    return MemoryHandler(db_pool=MagicMock(), lock_timeout=2.0)


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    orch = AsyncMock()
    orch.process_conversation = AsyncMock(return_value=FakeProcessResult())
    orch.initialize = AsyncMock()
    return orch


# ============================================================
# Per-user locking — serialization
# ============================================================


@pytest.mark.asyncio
async def test_concurrent_saves_serialized(handler: MemoryHandler, mock_orchestrator: AsyncMock):
    """Three concurrent saves for the same user should execute serially (no data loss)."""
    handler._memory_orchestrator = mock_orchestrator

    call_order: list[int] = []

    original_process = mock_orchestrator.process_conversation

    async def tracked_process(**kwargs):
        idx = len(call_order)
        call_order.append(idx)
        await asyncio.sleep(0.01)  # Simulate I/O
        return await original_process(**kwargs)

    mock_orchestrator.process_conversation = tracked_process

    # Launch 3 concurrent saves for the same user
    tasks = [
        asyncio.create_task(
            handler.save_conversation_memory(
                user_id="user@test.com", query=f"q{i}", answer=f"a{i}"
            )
        )
        for i in range(3)
    ]
    await asyncio.gather(*tasks)

    # All three should have completed — process_conversation called 3 times
    assert len(call_order) == 3


@pytest.mark.asyncio
async def test_different_users_not_blocked(handler: MemoryHandler, mock_orchestrator: AsyncMock):
    """Saves for different users should proceed concurrently (not serialized)."""
    handler._memory_orchestrator = mock_orchestrator

    user_start_times: dict[str, float] = {}

    async def tracked_process(**kwargs):
        user = kwargs.get("user_email", "")
        loop = asyncio.get_event_loop()
        user_start_times[user] = loop.time()
        await asyncio.sleep(0.05)
        return FakeProcessResult()

    mock_orchestrator.process_conversation = tracked_process

    tasks = [
        asyncio.create_task(
            handler.save_conversation_memory(user_id=f"user{i}@test.com", query="q", answer="a")
        )
        for i in range(3)
    ]
    await asyncio.gather(*tasks)

    # All three users should have started within a short window (concurrent)
    times = list(user_start_times.values())
    assert len(times) == 3
    # Max time spread should be small (all started nearly simultaneously)
    assert max(times) - min(times) < 0.04


# ============================================================
# Anonymous / empty user skip
# ============================================================


@pytest.mark.asyncio
async def test_skip_anonymous_user(handler: MemoryHandler, mock_orchestrator: AsyncMock):
    """Should skip memory save for anonymous users."""
    handler._memory_orchestrator = mock_orchestrator
    await handler.save_conversation_memory(user_id="anonymous", query="q", answer="a")
    mock_orchestrator.process_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_skip_empty_user(handler: MemoryHandler, mock_orchestrator: AsyncMock):
    """Should skip memory save for empty user_id."""
    handler._memory_orchestrator = mock_orchestrator
    await handler.save_conversation_memory(user_id="", query="q", answer="a")
    mock_orchestrator.process_conversation.assert_not_called()


# ============================================================
# Lock timeout handling
# ============================================================


@pytest.mark.asyncio
async def test_lock_timeout_does_not_crash(handler: MemoryHandler, mock_orchestrator: AsyncMock):
    """If lock acquisition times out, should log warning and continue."""
    handler._memory_orchestrator = mock_orchestrator
    handler._lock_timeout = 0.05  # Very short timeout

    # Locks are now keyed by "user_id::session_id"; when the caller omits
    # session_id the sentinel "__nosession__" is used.
    lock = handler._memory_locks["user@test.com::__nosession__"]
    await lock.acquire()  # Hold the lock

    try:
        # This should timeout, not crash
        await handler.save_conversation_memory(
            user_id="user@test.com", query="q", answer="a"
        )
    finally:
        lock.release()

    # process_conversation should NOT have been called (lock was held)
    mock_orchestrator.process_conversation.assert_not_called()


# ============================================================
# Lock eviction
# ============================================================


@pytest.mark.asyncio
async def test_stale_lock_eviction(handler: MemoryHandler, mock_orchestrator: AsyncMock):
    """Stale (unlocked) entries should be evicted when dict grows past limit."""
    handler._memory_orchestrator = mock_orchestrator

    # Create many stale lock entries
    for i in range(50):
        _ = handler._memory_locks[f"stale_user_{i}@test.com"]

    assert len(handler._memory_locks) == 50

    # Manually trigger eviction
    handler._evict_stale_locks()

    # All unlocked entries should be removed
    assert len(handler._memory_locks) == 0


# ============================================================
# create_save_task
# ============================================================


@pytest.mark.asyncio
async def test_create_save_task_returns_task(handler: MemoryHandler, mock_orchestrator: AsyncMock):
    """create_save_task should return an asyncio.Task."""
    handler._memory_orchestrator = mock_orchestrator
    task = handler.create_save_task(user_id="user@test.com", query="q", answer="a")
    assert isinstance(task, asyncio.Task)
    await task  # Let it complete


@pytest.mark.asyncio
async def test_create_save_task_returns_none_for_anonymous(handler: MemoryHandler):
    """create_save_task should return None for anonymous users."""
    result = handler.create_save_task(user_id="anonymous", query="q", answer="a")
    assert result is None


@pytest.mark.asyncio
async def test_create_save_task_returns_none_for_empty_answer(handler: MemoryHandler):
    """create_save_task should return None when answer is empty."""
    result = handler.create_save_task(user_id="user@test.com", query="q", answer="")
    assert result is None


@pytest.mark.asyncio
async def test_create_save_task_retains_strong_ref(
    handler: MemoryHandler, mock_orchestrator: AsyncMock,
) -> None:
    """Regression (S09): caller drops the Task, but handler must keep a
    strong ref so CPython can't GC the coroutine mid-save."""
    handler._memory_orchestrator = mock_orchestrator
    # Simulate caller that ignores the return value.
    handler.create_save_task(user_id="user@test.com", query="q", answer="a")
    assert len(handler._inflight_tasks) == 1
    # Drain.
    await asyncio.sleep(0)
    for task in list(handler._inflight_tasks):
        await task
    await asyncio.sleep(0)
    assert len(handler._inflight_tasks) == 0


# ============================================================
# Lazy MemoryOrchestrator init
# ============================================================


@pytest.mark.asyncio
async def test_lazy_orchestrator_init():
    """get_memory_orchestrator should initialize on first call."""
    handler = MemoryHandler(db_pool=MagicMock())
    assert handler._memory_orchestrator is None

    mock_instance = AsyncMock()
    mock_instance.initialize = AsyncMock()

    with patch("backend.services.memory.MemoryOrchestrator", return_value=mock_instance):
        result = await handler.get_memory_orchestrator()
        assert result is mock_instance
        mock_instance.initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_lazy_orchestrator_returns_cached():
    """Second call to get_memory_orchestrator should return cached instance."""
    handler = MemoryHandler(db_pool=MagicMock())
    fake_orch = AsyncMock()
    handler._memory_orchestrator = fake_orch

    result = await handler.get_memory_orchestrator()
    assert result is fake_orch


@pytest.mark.asyncio
async def test_lazy_orchestrator_init_failure():
    """get_memory_orchestrator should return None on init failure."""
    handler = MemoryHandler(db_pool=MagicMock())

    with patch("backend.services.memory.MemoryOrchestrator", side_effect=RuntimeError("DB down")):
        result = await handler.get_memory_orchestrator()
        assert result is None


# ============================================================
# Session-scoped locking (feat/react-memory-hardening)
# ============================================================


@pytest.mark.asyncio
async def test_save_concurrent_different_sessions_not_serialized(
    handler: MemoryHandler, mock_orchestrator: AsyncMock,
) -> None:
    """Two saves for the same user but different session_id must run in
    parallel — the lock is now keyed by ``(user_id, session_id)``, so
    cross-session traffic should no longer serialize.

    Proof is deterministic: both coroutines are required to reach
    ``process_conversation`` before either is allowed to return. If the
    new lock were still user-scoped, only one would enter and the second
    would time out on the barrier event — turning the regression into a
    visible ``TimeoutError``/``AssertionError`` instead of a silent pass.
    """
    handler._memory_orchestrator = mock_orchestrator

    entered_queries: set[str] = set()
    both_entered = asyncio.Event()

    async def tracked_process(**kwargs: object) -> FakeProcessResult:
        entered_queries.add(str(kwargs.get("user_message", "?")))
        if len(entered_queries) == 2:
            # Second entrant flips the barrier so both can complete.
            both_entered.set()
        try:
            await asyncio.wait_for(both_entered.wait(), timeout=1.0)
        except asyncio.TimeoutError as exc:
            raise AssertionError(
                "Session-scoped saves were serialized unexpectedly; "
                "only one branch entered process_conversation within 1s.",
            ) from exc
        return FakeProcessResult()

    mock_orchestrator.process_conversation = tracked_process

    tasks = [
        asyncio.create_task(
            handler.save_conversation_memory(
                user_id="user@test.com",
                query="q0",
                answer="a0",
                session_id="sess-A",
            ),
        ),
        asyncio.create_task(
            handler.save_conversation_memory(
                user_id="user@test.com",
                query="q1",
                answer="a1",
                session_id="sess-B",
            ),
        ),
    ]
    await asyncio.gather(*tasks)

    assert entered_queries == {"q0", "q1"}


@pytest.mark.asyncio
async def test_save_concurrent_same_session_serialized(
    handler: MemoryHandler, mock_orchestrator: AsyncMock,
) -> None:
    """Two saves for the same user AND session_id must serialize: the
    second caller has to wait for the first lock holder to release before
    entering process_conversation."""
    handler._memory_orchestrator = mock_orchestrator

    concurrency_peak = 0
    concurrency_current = 0
    lock_probe = asyncio.Lock()

    async def tracked_process(**_kwargs: object) -> FakeProcessResult:
        nonlocal concurrency_peak, concurrency_current
        async with lock_probe:
            concurrency_current += 1
            concurrency_peak = max(concurrency_peak, concurrency_current)
        # Hold the critical section long enough for the second task to
        # queue up on the user+session lock.
        await asyncio.sleep(0.05)
        async with lock_probe:
            concurrency_current -= 1
        return FakeProcessResult()

    mock_orchestrator.process_conversation = tracked_process

    tasks = [
        asyncio.create_task(
            handler.save_conversation_memory(
                user_id="user@test.com",
                query=f"q{i}",
                answer=f"a{i}",
                session_id="sess-SAME",
            ),
        )
        for i in range(2)
    ]
    await asyncio.gather(*tasks)

    # Under correct serialization, the two tasks never overlap inside
    # process_conversation -> peak concurrency is 1.
    assert concurrency_peak == 1, (
        f"same-session saves overlapped (peak={concurrency_peak}); "
        "session-scoped lock is not serializing."
    )


@pytest.mark.asyncio
async def test_save_backward_compat_no_session_id(
    handler: MemoryHandler, mock_orchestrator: AsyncMock,
) -> None:
    """Calling save_conversation_memory without session_id must still work
    and must register a lock entry under the sentinel ``__nosession__`` key,
    preserving the pre-refactor serialization contract for legacy callers."""
    handler._memory_orchestrator = mock_orchestrator

    await handler.save_conversation_memory(
        user_id="user@test.com", query="q", answer="a",
    )

    mock_orchestrator.process_conversation.assert_awaited_once()
    # The lock dict now keys by "user_id::session_id" — when session_id is
    # omitted the sentinel "__nosession__" must appear.
    assert "user@test.com::__nosession__" in handler._memory_locks


@pytest.mark.asyncio
async def test_create_save_task_propagates_session_id(
    handler: MemoryHandler, mock_orchestrator: AsyncMock,
) -> None:
    """create_save_task must forward session_id through to the coroutine
    and include it in the task name for observability."""
    handler._memory_orchestrator = mock_orchestrator

    task = handler.create_save_task(
        user_id="user@test.com",
        query="q",
        answer="a",
        session_id="sess-X",
    )
    assert task is not None
    assert task.get_name() == "memory-save:user@test.com:sess-X"
    await task
    assert "user@test.com::sess-X" in handler._memory_locks
