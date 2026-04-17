"""Tests for backend.services.common.background.spawn()."""
from __future__ import annotations

import asyncio
import logging

import pytest

from backend.services.common import background


@pytest.fixture(autouse=True)
def _clear_inflight():
    """Ensure clean state between tests (module-level set)."""
    background._inflight.clear()
    yield
    background._inflight.clear()


@pytest.mark.asyncio
async def test_spawn_returns_task_and_executes_coroutine():
    executed = asyncio.Event()

    async def work():
        executed.set()

    task = background.spawn(work())
    assert isinstance(task, asyncio.Task)
    await asyncio.wait_for(executed.wait(), timeout=1.0)
    await task  # ensure done


@pytest.mark.asyncio
async def test_spawn_adds_task_to_inflight_set():
    started = asyncio.Event()
    release = asyncio.Event()

    async def work():
        started.set()
        await release.wait()

    task = background.spawn(work(), name="test-inflight")
    await started.wait()
    assert task in background._inflight
    release.set()
    await task
    # After completion the done_callback removes from inflight
    await asyncio.sleep(0)  # let callback run
    assert task not in background._inflight


@pytest.mark.asyncio
async def test_spawn_accepts_name():
    async def work():
        return None

    task = background.spawn(work(), name="my-task")
    assert task.get_name() == "my-task"
    await task


@pytest.mark.asyncio
async def test_spawn_surfaces_exception_via_logger(caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.ERROR, logger="backend.services.common.background")

    async def boom():
        raise RuntimeError("kaboom")

    task = background.spawn(boom(), name="explodes")
    # Wait for task to finish; done_callback fires after
    with pytest.raises(RuntimeError):
        await task
    await asyncio.sleep(0)

    matching = [r for r in caplog.records if "explodes" in r.getMessage()]
    assert matching, f"no error log surfaced for failing task; records={caplog.records}"
    rec = matching[0]
    assert rec.levelno == logging.ERROR
    assert rec.exc_info is not None


@pytest.mark.asyncio
async def test_spawn_cancellation_does_not_log_error(caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.ERROR, logger="backend.services.common.background")

    async def long_work():
        await asyncio.sleep(10)

    task = background.spawn(long_work(), name="cancel-me")
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    # Cancellation is intentional → no ERROR log
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not error_records, f"cancellation logged as error: {error_records}"


@pytest.mark.asyncio
async def test_spawn_prevents_gc_of_task():
    """Regression test: without strong-ref, a bare asyncio.create_task result
    may be garbage-collected. spawn() must keep it alive until completion."""
    import gc

    counter = {"n": 0}

    async def work():
        await asyncio.sleep(0.01)
        counter["n"] += 1

    # Do NOT keep the returned task reference locally (simulate fire-and-forget)
    background.spawn(work(), name="no-local-ref")
    gc.collect()  # force collection of any weak refs

    # Wait for task to drain naturally
    for _ in range(50):
        if counter["n"] == 1 and not background._inflight:
            break
        await asyncio.sleep(0.01)

    assert counter["n"] == 1


@pytest.mark.asyncio
async def test_spawn_multiple_tasks_independent():
    results: list[int] = []

    async def work(n: int):
        await asyncio.sleep(0.01)
        results.append(n)

    tasks = [background.spawn(work(i), name=f"t{i}") for i in range(5)]
    await asyncio.gather(*tasks)
    assert sorted(results) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_inflight_cleared_after_all_done():
    async def work():
        await asyncio.sleep(0.01)

    tasks = [background.spawn(work()) for _ in range(3)]
    await asyncio.gather(*tasks)
    await asyncio.sleep(0)
    assert len(background._inflight) == 0
