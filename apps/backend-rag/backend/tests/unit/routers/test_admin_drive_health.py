"""Tests for admin Drive health and poll endpoints."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.routers.admin_drive_health import drive_poll_status, trigger_drive_poll


class FakeAcquire:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    async def __aenter__(self) -> Any:
        return self.conn

    async def __aexit__(self, *_args: Any) -> bool:
        return False


class FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.conn = AsyncMock()
        self.conn.fetch.return_value = rows

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


def _request_with_pool(pool: Any | None) -> MagicMock:
    request = MagicMock()
    if pool is None:
        request.app.state.db_pool = None
    else:
        request.app.state.db_pool = pool
    return request


@pytest.mark.asyncio
async def test_drive_poll_status_reports_worker_heartbeat() -> None:
    pool = FakePool(
        [
            {
                "key": "drive_poll_worker_heartbeat_at",
                "value": "2099-01-01T00:00:00+00:00",
                "updated_at": None,
            },
            {
                "key": "drive_poll_worker_last_status",
                "value": "ok",
                "updated_at": None,
            },
            {
                "key": "drive_poll_worker_last_result",
                "value": '{"status": "ok", "processed": 4}',
                "updated_at": None,
            },
        ],
    )

    with patch.dict("os.environ", {"DRIVE_POLL_API_MODE": ""}, clear=False):
        result = await drive_poll_status(_request_with_pool(pool))

    assert result["status"] == "ok"
    assert result["worker_owned"] is True
    assert result["result"]["healthy"] is True
    assert result["result"]["last_result"]["processed"] == 4


@pytest.mark.asyncio
async def test_drive_poll_status_is_stale_without_heartbeat() -> None:
    with patch.dict("os.environ", {"DRIVE_POLL_API_MODE": ""}, clear=False):
        result = await drive_poll_status(_request_with_pool(FakePool([])))

    assert result["status"] == "stale"
    assert result["result"]["healthy"] is False
    assert result["result"]["status"] == "never_seen"


@pytest.mark.asyncio
async def test_trigger_drive_poll_defaults_to_worker_status_without_polling() -> None:
    poll_drive_changes = AsyncMock(return_value={"status": "ok", "processed": 2})
    pool = FakePool(
        [
            {
                "key": "drive_poll_worker_heartbeat_at",
                "value": "2099-01-01T00:00:00+00:00",
                "updated_at": None,
            },
            {
                "key": "drive_poll_worker_last_status",
                "value": "ok",
                "updated_at": None,
            },
        ],
    )

    with (
        patch(
            "backend.services.crm.drive_poll_service.poll_drive_changes",
            new=poll_drive_changes,
        ),
        patch.dict("os.environ", {"DRIVE_POLL_API_MODE": ""}, clear=False),
    ):
        result = await trigger_drive_poll(_request_with_pool(pool))

    poll_drive_changes.assert_not_awaited()
    assert result["status"] == "ok"
    assert result["processed"] == 0
    assert result["worker_owned"] is True
    assert result["mode"] == "worker"


@pytest.mark.asyncio
async def test_trigger_drive_poll_disables_inline_ocr_by_default() -> None:
    poll_drive_changes = AsyncMock(return_value={"status": "ok", "processed": 2})

    with (
        patch(
            "backend.services.crm.drive_poll_service.poll_drive_changes",
            new=poll_drive_changes,
        ),
        patch.dict(
            "os.environ",
            {
                "DRIVE_POLL_API_MODE": "direct",
                "DRIVE_POLL_INLINE_OCR": "",
                "DRIVE_POLL_API_TIMEOUT_SECONDS": "30",
            },
            clear=False,
        ),
    ):
        result = await trigger_drive_poll(MagicMock())

    poll_drive_changes.assert_awaited_once_with(inline_ocr=False)
    assert result["status"] == "ok"
    assert result["processed"] == 2
    assert result["inline_ocr"] is False


@pytest.mark.asyncio
async def test_trigger_drive_poll_can_enable_inline_ocr_by_env() -> None:
    poll_drive_changes = AsyncMock(return_value={"status": "ok", "processed": 1})

    with (
        patch(
            "backend.services.crm.drive_poll_service.poll_drive_changes",
            new=poll_drive_changes,
        ),
        patch.dict(
            "os.environ",
            {
                "DRIVE_POLL_API_MODE": "direct",
                "DRIVE_POLL_INLINE_OCR": "true",
                "DRIVE_POLL_API_TIMEOUT_SECONDS": "30",
            },
            clear=False,
        ),
    ):
        result = await trigger_drive_poll(MagicMock())

    poll_drive_changes.assert_awaited_once_with(inline_ocr=True)
    assert result["inline_ocr"] is True


@pytest.mark.asyncio
async def test_trigger_drive_poll_timeout_raises_504() -> None:
    async def slow_poll(*, inline_ocr: bool) -> dict[str, Any]:
        await asyncio.sleep(1)
        return {"status": "ok", "processed": 1, "inline_ocr": inline_ocr}

    with (
        patch("backend.services.crm.drive_poll_service.poll_drive_changes", new=slow_poll),
        patch("backend.app.routers.admin_drive_health._drive_poll_api_timeout_seconds", return_value=0.01),
        patch.dict(
            "os.environ",
            {"DRIVE_POLL_API_MODE": "direct", "DRIVE_POLL_INLINE_OCR": ""},
            clear=False,
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await trigger_drive_poll(MagicMock())

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail["status"] == "timeout"
    assert exc_info.value.detail["inline_ocr"] is False
