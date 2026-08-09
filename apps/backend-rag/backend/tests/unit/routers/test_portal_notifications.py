"""Tests for portal notifications endpoints."""

import logging
import re
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from fastapi import HTTPException

from backend.app.routers.portal_notifications import (
    _get_notifications,
    _mark_read,
    mark_all_read,
)


def _pool_with_connection(mock_conn: AsyncMock) -> MagicMock:
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _pool_with_lifecycle_failure(marker: str, failure_phase: str) -> MagicMock:
    mock_pool = MagicMock()
    if failure_phase == "acquire":
        mock_pool.acquire.side_effect = RuntimeError(marker)
        return mock_pool

    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    if failure_phase == "enter":
        mock_pool.acquire.return_value.__aenter__.side_effect = RuntimeError(marker)
    elif failure_phase == "exit":
        mock_pool.acquire.return_value.__aexit__.side_effect = RuntimeError(marker)
    else:  # pragma: no cover - parametrization is the closed phase set
        raise AssertionError(f"Unknown lifecycle failure phase: {failure_phase}")
    return mock_pool


def _assert_safe_unavailable(
    exc_info: pytest.ExceptionInfo[HTTPException],
    caplog: pytest.LogCaptureFixture,
    marker: str,
) -> None:
    assert exc_info.value.status_code == 503
    detail = str(exc_info.value.detail)
    match = re.fullmatch(
        r"Notifications temporarily unavailable\. Reference: ([0-9a-f]{32})",
        detail,
    )
    assert match is not None
    assert marker not in detail
    assert marker not in caplog.text
    assert f"error_ref={match.group(1)}" in caplog.text
    assert "error_type=RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_get_notifications_returns_list() -> None:
    """Notifications endpoint returns ordered list."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 1,
            "type": "document_verified",
            "title": "Passport verified",
            "body": "Your passport has been verified",
            "data": "{}",
            "read_at": None,
            "created_at": "2026-03-30T10:00:00+00:00",
        },
        {
            "id": 2,
            "type": "status_changed",
            "title": "KITAS approved",
            "body": "Your visa was approved",
            "data": "{}",
            "read_at": "2026-03-30T11:00:00+00:00",
            "created_at": "2026-03-29T10:00:00+00:00",
        },
    ]
    mock_conn.fetchval.return_value = 1

    mock_pool = _pool_with_connection(mock_conn)

    result = await _get_notifications(mock_pool, client_id=1, limit=50)

    assert len(result["notifications"]) == 2
    assert result["unread_count"] == 1
    assert result["notifications"][0]["title"] == "Passport verified"


@pytest.mark.asyncio
async def test_get_notifications_graceful_on_missing_table() -> None:
    """A schema-migration gap is explicit rather than a false empty state."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = asyncpg.UndefinedTableError(
        "relation 'portal_notifications' does not exist",
    )

    mock_pool = _pool_with_connection(mock_conn)

    result = await _get_notifications(mock_pool, client_id=1)
    assert len(result["notifications"]) == 0
    assert result["unread_count"] == 0
    assert result["degraded"] is True


@pytest.mark.asyncio
async def test_get_notifications_maps_database_outage_to_safe_503(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A real outage must not be reported as an empty notification inbox."""
    marker = "SYNTHETIC_NOTIFICATION_DB_OUTAGE"
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = RuntimeError(marker)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await _get_notifications(_pool_with_connection(mock_conn), client_id=1)

    _assert_safe_unavailable(exc_info, caplog, marker)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_phase", ["acquire", "enter", "exit"])
async def test_get_notifications_maps_pool_lifecycle_failure_to_safe_503(
    failure_phase: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pool lifecycle failures must stay behind the client boundary."""
    marker = f"SYNTHETIC_NOTIFICATION_POOL_{failure_phase.upper()}_OUTAGE"

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await _get_notifications(
                _pool_with_lifecycle_failure(marker, failure_phase),
                client_id=1,
            )

    _assert_safe_unavailable(exc_info, caplog, marker)


@pytest.mark.asyncio
async def test_mark_read_updates_notification() -> None:
    """Mark read returns True on success."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 1

    mock_pool = _pool_with_connection(mock_conn)

    result = await _mark_read(mock_pool, client_id=1, notification_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_mark_read_returns_false_for_wrong_client() -> None:
    """Mark read returns False if not found."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None

    mock_pool = _pool_with_connection(mock_conn)

    result = await _mark_read(mock_pool, client_id=999, notification_id=1)
    assert result is False


@pytest.mark.asyncio
async def test_mark_read_maps_database_outage_to_safe_503(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A write outage must not masquerade as a missing notification."""
    marker = "SYNTHETIC_MARK_READ_DB_OUTAGE"
    mock_conn = AsyncMock()
    mock_conn.fetchval.side_effect = RuntimeError(marker)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await _mark_read(
                _pool_with_connection(mock_conn),
                client_id=1,
                notification_id=7,
            )

    _assert_safe_unavailable(exc_info, caplog, marker)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_phase", ["acquire", "enter", "exit"])
async def test_mark_read_maps_pool_lifecycle_failure_to_safe_503(
    failure_phase: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mark-one must redact failures across the pool lifecycle."""
    marker = f"SYNTHETIC_MARK_READ_POOL_{failure_phase.upper()}_OUTAGE"

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await _mark_read(
                _pool_with_lifecycle_failure(marker, failure_phase),
                client_id=1,
                notification_id=7,
            )

    _assert_safe_unavailable(exc_info, caplog, marker)


@pytest.mark.asyncio
async def test_mark_all_maps_database_outage_to_safe_503(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mark-all must not return success when no database write occurred."""
    marker = "SYNTHETIC_MARK_ALL_DB_OUTAGE"
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = RuntimeError(marker)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await mark_all_read(
                client={"client_id": 1},
                db_pool=_pool_with_connection(mock_conn),
            )

    _assert_safe_unavailable(exc_info, caplog, marker)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_phase", ["acquire", "enter", "exit"])
async def test_mark_all_maps_pool_lifecycle_failure_to_safe_503(
    failure_phase: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mark-all must redact failures across the pool lifecycle."""
    marker = f"SYNTHETIC_MARK_ALL_POOL_{failure_phase.upper()}_OUTAGE"

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await mark_all_read(
                client={"client_id": 1},
                db_pool=_pool_with_lifecycle_failure(marker, failure_phase),
            )

    _assert_safe_unavailable(exc_info, caplog, marker)
