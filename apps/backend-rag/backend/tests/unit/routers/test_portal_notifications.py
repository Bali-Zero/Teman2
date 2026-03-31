"""Tests for portal notifications endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers.portal_notifications import _get_notifications, _mark_read


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

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _get_notifications(mock_pool, client_id=1, limit=50)

    assert len(result["notifications"]) == 2
    assert result["unread_count"] == 1
    assert result["notifications"][0]["title"] == "Passport verified"


@pytest.mark.asyncio
async def test_get_notifications_graceful_on_missing_table() -> None:
    """Returns empty when portal_notifications table doesn't exist."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = Exception("relation 'portal_notifications' does not exist")

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _get_notifications(mock_pool, client_id=1)
    assert len(result["notifications"]) == 0
    assert result["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_read_updates_notification() -> None:
    """Mark read returns True on success."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 1

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _mark_read(mock_pool, client_id=1, notification_id=1)
    assert result is True


@pytest.mark.asyncio
async def test_mark_read_returns_false_for_wrong_client() -> None:
    """Mark read returns False if not found."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _mark_read(mock_pool, client_id=999, notification_id=1)
    assert result is False
