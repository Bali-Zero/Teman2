"""Tests for admin Drive health and poll endpoints."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.routers.admin_drive_health import trigger_drive_poll


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
        patch.dict("os.environ", {"DRIVE_POLL_INLINE_OCR": ""}, clear=False),
        pytest.raises(HTTPException) as exc_info,
    ):
        await trigger_drive_poll(MagicMock())

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail["status"] == "timeout"
    assert exc_info.value.detail["inline_ocr"] is False
