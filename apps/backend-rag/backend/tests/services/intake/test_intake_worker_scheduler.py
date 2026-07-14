"""DB-free scheduler regression tests for the Intake worker."""

from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import AsyncMock

import asyncpg
import pytest

from backend.services.intake import worker as worker_module
from backend.services.intake.worker import IntakeWorker, WorkerConfig


@pytest.mark.asyncio
async def test_fast_lane_reclaims_before_slowest_sibling_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A millisecond stage must not idle behind a slow OCR/model stage."""
    monkeypatch.setattr(worker_module, "remap_legacy_statuses", AsyncMock())
    monkeypatch.setattr(worker_module, "reap_expired_review_claims", AsyncMock())

    worker = IntakeWorker(
        cast(asyncpg.Pool, object()),
        config=WorkerConfig(concurrency=2, poll_interval_seconds=0.001),
        worker_id="scheduler-test",
    )
    slow_lane_release = asyncio.Event()
    fast_lane_reclaimed = asyncio.Event()
    call_lock = asyncio.Lock()
    call_count = 0

    async def run_once() -> bool:
        nonlocal call_count
        async with call_lock:
            call_number = call_count
            call_count += 1
        if call_number == 0:
            await slow_lane_release.wait()
            return True
        if call_number == 1:
            return True
        fast_lane_reclaimed.set()
        worker.stop()
        return False

    monkeypatch.setattr(worker, "run_once", run_once)
    runner = asyncio.create_task(worker.run_forever())
    try:
        await asyncio.wait_for(fast_lane_reclaimed.wait(), timeout=0.5)
        assert not slow_lane_release.is_set()
        assert call_count >= 3
    finally:
        slow_lane_release.set()
        worker.stop()
        await asyncio.wait_for(runner, timeout=1.0)
