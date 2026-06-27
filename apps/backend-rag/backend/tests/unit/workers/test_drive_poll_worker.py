"""Tests for the Drive poll background worker."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.workers.drive_poll_worker import DrivePollWorkerConfig, load_config, run_once


class FakeAcquire:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    async def __aenter__(self) -> Any:
        return self.conn

    async def __aexit__(self, *_args: Any) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.conn = AsyncMock()
        self.closed = False

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)

    async def close(self) -> None:
        self.closed = True


def test_load_config_from_env() -> None:
    with patch.dict(
        "os.environ",
        {
            "DATABASE_URL": "postgresql://test/db",
            "DRIVE_POLL_WORKER_INTERVAL_SECONDS": "120",
            "DRIVE_POLL_WORKER_JITTER_SECONDS": "0",
            "DRIVE_POLL_WORKER_TIMEOUT_SECONDS": "240",
            "DRIVE_POLL_WORKER_INLINE_OCR": "true",
        },
        clear=False,
    ):
        config = load_config(["--once"])

    assert config.database_url == "postgresql://test/db"
    assert config.interval_seconds == 120
    assert config.jitter_seconds == 0
    assert config.timeout_seconds == 240
    assert config.inline_ocr is True
    assert config.once is True


@pytest.mark.asyncio
async def test_run_once_records_heartbeat_and_result() -> None:
    fake_pool = FakePool()
    config = DrivePollWorkerConfig(
        database_url="postgresql://test/db",
        interval_seconds=300,
        jitter_seconds=0,
        timeout_seconds=840,
        inline_ocr=False,
        once=True,
    )
    poll = AsyncMock(return_value={"status": "ok", "processed": 3})

    with (
        patch(
            "backend.workers.drive_poll_worker.asyncpg.create_pool",
            new=AsyncMock(return_value=fake_pool),
        ),
        patch("backend.workers.drive_poll_worker.poll_drive_changes", new=poll),
    ):
        result = await run_once(config)

    assert result == {"status": "ok", "processed": 3}
    assert fake_pool.closed is True
    poll.assert_awaited_once_with(inline_ocr=False, acquire_advisory_lock=True)

    written_keys = [call.args[1] for call in fake_pool.conn.execute.await_args_list]
    assert "drive_poll_worker_heartbeat_at" in written_keys
    assert "drive_poll_worker_last_status" in written_keys
    assert "drive_poll_worker_last_result" in written_keys


@pytest.mark.asyncio
async def test_run_once_records_timeout_state() -> None:
    fake_pool = FakePool()
    config = DrivePollWorkerConfig(
        database_url="postgresql://test/db",
        interval_seconds=300,
        jitter_seconds=0,
        timeout_seconds=60,
        inline_ocr=False,
        once=True,
    )
    poll = AsyncMock(return_value={"status": "ok"})

    async def fake_wait_for(awaitable: Any, timeout: int) -> Any:
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise TimeoutError

    with (
        patch(
            "backend.workers.drive_poll_worker.asyncpg.create_pool",
            new=AsyncMock(return_value=fake_pool),
        ),
        patch("backend.workers.drive_poll_worker.poll_drive_changes", new=poll),
        patch("backend.workers.drive_poll_worker.asyncio.wait_for", new=fake_wait_for),
    ):
        result = await run_once(config)

    assert result == {
        "status": "timeout",
        "error": "Drive poll worker exceeded 60s",
        "timeout_seconds": 60,
    }
    assert fake_pool.closed is True

    written = {
        call.args[1]: call.args[2] for call in fake_pool.conn.execute.await_args_list
    }
    assert written["drive_poll_worker_last_status"] == "timeout"
    assert written["drive_poll_worker_last_error"] == "Drive poll worker exceeded 60s"
    assert "drive_poll_worker_last_finished_at" in written
