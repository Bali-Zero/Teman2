"""Tests for portal Drive proxy endpoints."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.app.routers.portal_drive import (
    _get_drive_service,
    _list_client_drive_files,
    list_drive_files,
    list_subfolder_files,
)


@pytest.mark.asyncio
async def test_list_files_returns_client_safe_empty_projection() -> None:
    """Portal Drive endpoint must not expose navigable Drive folder metadata."""
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

    assert result == {
        "files": [],
        "folders": [],
        "total_files": 0,
        "message": "Drive navigation is not exposed in the client portal",
    }
    mock_drive.get_folder_structure.assert_not_called()


def test_get_drive_service_returns_service_account_drive_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = object()

    class FakeDriveService:
        def __new__(cls) -> object:
            return created

    from backend.app.routers import portal_drive

    monkeypatch.setattr(portal_drive, "ServiceAccountDriveService", FakeDriveService)

    service = _get_drive_service()

    assert service is created


@pytest.mark.asyncio
async def test_list_drive_files_wraps_safe_projection() -> None:
    mock_pool = MagicMock()
    mock_drive = MagicMock()
    expected = {
        "files": [],
        "folders": [],
        "total_files": 0,
        "message": "Drive navigation is not exposed in the client portal",
    }

    async def fake_list(pool: object, drive_service: object, client_id: int) -> dict[str, Any]:
        assert pool is mock_pool
        assert drive_service is mock_drive
        assert client_id == 7
        return expected

    from backend.app.routers import portal_drive

    original = portal_drive._list_client_drive_files
    portal_drive._list_client_drive_files = fake_list
    try:
        result = await list_drive_files(
            client={"client_id": 7},
            db_pool=mock_pool,
            drive_service=mock_drive,
        )
    finally:
        portal_drive._list_client_drive_files = original

    assert result == {"success": True, "data": expected}


@pytest.mark.asyncio
async def test_list_drive_files_hides_backend_errors() -> None:
    async def broken_list(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("drive unavailable")

    from backend.app.routers import portal_drive

    original = portal_drive._list_client_drive_files
    portal_drive._list_client_drive_files = broken_list
    try:
        with pytest.raises(HTTPException) as exc:
            await list_drive_files(
                client={"client_id": 7},
                db_pool=MagicMock(),
                drive_service=MagicMock(),
            )
    finally:
        portal_drive._list_client_drive_files = original

    assert exc.value.status_code == 500
    assert exc.value.detail == "Failed to load documents from Drive"


@pytest.mark.asyncio
async def test_list_subfolder_files_is_not_exposed() -> None:
    with pytest.raises(HTTPException) as exc:
        await list_subfolder_files(
            folder_id="folder_123",
            client={"client_id": 7},
            db_pool=MagicMock(),
            drive_service=MagicMock(),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Drive navigation is not exposed in the client portal"


@pytest.mark.asyncio
async def test_list_files_returns_same_safe_projection_when_no_folder() -> None:
    """Portal Drive endpoint stays shape-compatible even without a Drive folder."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_drive = MagicMock()

    result = await _list_client_drive_files(mock_pool, mock_drive, client_id=1)

    assert result == {
        "files": [],
        "folders": [],
        "total_files": 0,
        "message": "Drive navigation is not exposed in the client portal",
    }
    mock_drive.get_folder_structure.assert_not_called()
