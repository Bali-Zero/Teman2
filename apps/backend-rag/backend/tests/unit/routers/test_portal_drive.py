"""Tests for portal Drive proxy endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers.portal_drive import _list_client_drive_files


@pytest.mark.asyncio
async def test_list_files_returns_drive_files():
    """Drive list endpoint returns files from client's Drive folder."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = "folder_abc123"

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_drive = MagicMock()
    mock_drive.get_folder_structure = AsyncMock(return_value={
        "root_id": "folder_abc123",
        "root_name": "Client_John",
        "folders": [{"id": "sub1", "name": "Documents"}, {"id": "sub2", "name": "Final"}],
        "total_files": 5,
        "total_size_bytes": 1024000,
    })

    result = await _list_client_drive_files(mock_pool, mock_drive, client_id=1)

    assert result is not None
    assert result["root_name"] == "Client_John"
    assert len(result["folders"]) == 2
    assert result["total_files"] == 5


@pytest.mark.asyncio
async def test_list_files_returns_none_when_no_folder():
    """Drive list endpoint returns None if client has no Drive folder."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_drive = MagicMock()

    result = await _list_client_drive_files(mock_pool, mock_drive, client_id=1)

    assert result is None
    mock_drive.get_folder_structure.assert_not_called()
