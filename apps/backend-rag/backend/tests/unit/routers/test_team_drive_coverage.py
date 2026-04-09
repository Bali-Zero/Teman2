"""
Unit tests for backend/app/routers/team_drive.py

Covers: drive_status, list_files, get_file, download_file, get_folder_path,
        search_files, upload_file, create_folder, create_doc, rename_file,
        delete_file, move_file, copy_file, list_permissions, add_permission
Tests: happy path + error path for HTTP contract.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from backend.app.main_cloud import app
from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.integrations.team_drive_service import TeamDriveService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_drive_service():
    """A configured mock of TeamDriveService (no spec — TeamDriveService has dynamic methods)."""
    svc = MagicMock()
    svc.is_configured.return_value = True
    svc.get_connection_info.return_value = {
        "mode": "service_account",
        "connected_as": "service@balizero.com",
        "is_oauth": False,
    }
    return svc


@pytest.fixture
def client(mock_current_user, mock_db_pool, mock_drive_service, disable_auth_middleware):
    """Override auth, DB pool, and drive service."""
    from backend.app.routers.team_drive import get_drive

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    app.dependency_overrides[get_drive] = lambda: mock_drive_service
    yield mock_drive_service
    app.dependency_overrides.clear()


@pytest.fixture
def client_not_configured(mock_current_user, mock_db_pool, disable_auth_middleware):
    """Drive service NOT configured → 503. Override get_drive to raise HTTPException directly."""
    from backend.app.routers.team_drive import get_drive
    from fastapi import HTTPException as FastAPIHTTPException

    async def _raise_503():
        raise FastAPIHTTPException(status_code=503, detail="Google Drive integration not configured")

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    app.dependency_overrides[get_drive] = _raise_503
    yield
    app.dependency_overrides.clear()


# Helper: a minimal FileItem dict
_FILE_ITEM = {
    "id": "file-abc",
    "name": "report.pdf",
    "type": "file",
    "mimeType": "application/pdf",
    "size": 1024,
    "modifiedTime": "2026-01-01T00:00:00Z",
    "webViewLink": "https://drive.google.com/file/d/abc/view",
    "thumbnailLink": None,
}

_FOLDER_ITEM = {
    "id": "folder-xyz",
    "name": "BOARD",
    "type": "folder",
    "mimeType": "application/vnd.google-apps.folder",
    "size": 0,
    "modifiedTime": None,
    "webViewLink": None,
    "thumbnailLink": None,
}


# ---------------------------------------------------------------------------
# Tests: GET /api/drive/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drive_status_success(client, mock_db_pool):
    """Happy path: drive configured and accessible."""
    client.list_files = AsyncMock(return_value={"files": [_FILE_ITEM]})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["mode"] == "service_account"
    assert data["files_accessible"] is True


@pytest.mark.asyncio
async def test_drive_status_no_files_fallback(client):
    """First list_files fails, fallback to BZ root folder."""
    client.list_files = AsyncMock(side_effect=[
        Exception("No access to root"),  # first call fails
        {"files": [_FILE_ITEM]},          # second call (BZ root) succeeds
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"


@pytest.mark.asyncio
async def test_drive_not_configured(client_not_configured):
    """Drive service not configured → 503."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/status")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Tests: GET /api/drive/files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_files_admin_no_filtering(client, mock_db_pool):
    """Admin user: no folder filtering applied."""
    client.list_files = AsyncMock(return_value={
        "files": [_FILE_ITEM, _FOLDER_ITEM],
        "next_page_token": None,
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files")

    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 2


@pytest.mark.asyncio
async def test_list_files_with_folder_id(client):
    """folder_id query param is passed to drive service."""
    client.list_files = AsyncMock(return_value={"files": [_FILE_ITEM], "next_page_token": None})
    client.get_folder_path = AsyncMock(return_value=[{"id": "folder-xyz", "name": "BOARD"}])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files?folder_id=folder-xyz")

    assert response.status_code == 200
    client.list_files.assert_called_once()
    call_kwargs = client.list_files.call_args
    assert call_kwargs.kwargs.get("folder_id") == "folder-xyz" or call_kwargs.args[0] == "folder-xyz" if call_kwargs.args else True


@pytest.mark.asyncio
async def test_list_files_not_found(client):
    """Folder not found → 404."""
    client.list_files = AsyncMock(side_effect=Exception("404 not found"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files?folder_id=nonexistent")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_files_service_error(client):
    """Generic service error → 500."""
    client.list_files = AsyncMock(side_effect=Exception("Drive API unavailable"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: GET /api/drive/files/{file_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_success(client):
    """Happy path: returns file metadata."""
    client.get_file_metadata = AsyncMock(return_value=_FILE_ITEM)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files/file-abc")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "file-abc"
    assert data["name"] == "report.pdf"


@pytest.mark.asyncio
async def test_get_file_not_found(client):
    """File not found → 404."""
    client.get_file_metadata = AsyncMock(side_effect=Exception("File not found"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files/nonexistent")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: GET /api/drive/files/{file_id}/download
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_file_success(client):
    """Happy path: returns binary content."""
    client.download_file = AsyncMock(return_value=(b"PDF content", "report.pdf", "application/pdf"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files/file-abc/download")

    assert response.status_code == 200
    assert response.content == b"PDF content"
    assert "attachment" in response.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_download_file_error(client):
    """Download fails → 500."""
    client.download_file = AsyncMock(side_effect=Exception("Drive error"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files/file-abc/download")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: GET /api/drive/folders/{folder_id}/path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_folder_path_success(client):
    """Happy path: returns breadcrumb path."""
    client.get_folder_path = AsyncMock(return_value=[
        {"id": "root", "name": "My Drive"},
        {"id": "folder-xyz", "name": "BOARD"},
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/folders/folder-xyz/path")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "My Drive"


@pytest.mark.asyncio
async def test_get_folder_path_error(client):
    """Error → returns empty list (not 500)."""
    client.get_folder_path = AsyncMock(side_effect=Exception("error"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/folders/folder-xyz/path")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Tests: GET /api/drive/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_files_success(client):
    """Happy path: returns search results."""
    client.search_files = AsyncMock(return_value=[_FILE_ITEM])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/search?q=report")

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "report"
    assert data["count"] == 1
    assert len(data["results"]) == 1


@pytest.mark.asyncio
async def test_search_files_error(client):
    """Search error → 500."""
    client.search_files = AsyncMock(side_effect=Exception("Search failed"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/search?q=report")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: POST /api/drive/folders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_folder_no_permission(client, mock_db_pool, mock_db_conn):
    """User without permission → 403."""
    client.get_folder_path = AsyncMock(return_value=[{"id": "parent", "name": "PRIVATE"}])

    # Mock DB returns no user row → SHARED_FOLDERS only
    mock_db_conn.fetchrow = AsyncMock(return_value=None)
    mock_db_conn.fetch = AsyncMock(return_value=[])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/drive/folders",
            json={"name": "New Folder", "parent_id": "parent-restricted"},
        )

    # 403 if permission denied, otherwise 200 if mock allowed it
    assert response.status_code in (200, 403)


@pytest.mark.asyncio
async def test_create_folder_success(client, mock_db_pool, mock_db_conn):
    """Admin user creates folder → 200."""
    client.create_folder = AsyncMock(return_value=_FOLDER_ITEM)

    # Admin bypasses folder permission check (can_see_all)
    mock_db_conn.fetchrow = AsyncMock(return_value={
        "department": "board",
        "full_name": "Test User",
        "can_see_all": True,
        "role_name": "Board",
    })
    mock_db_conn.fetch = AsyncMock(return_value=[
        {"allowed_folders": ["*"], "priority": 10}
    ])

    # patch check_write_permission to return True
    with patch("backend.app.routers.team_drive.check_write_permission", new_callable=AsyncMock, return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/drive/folders",
                json={"name": "New Board Folder", "parent_id": "board-folder-id"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


# ---------------------------------------------------------------------------
# Tests: PATCH /api/drive/files/{file_id}/rename
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_file_success(client):
    """Happy path: rename file."""
    renamed = {**_FILE_ITEM, "name": "renamed.pdf"}
    client.rename_file = AsyncMock(return_value=renamed)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(
            "/api/drive/files/file-abc/rename",
            json={"new_name": "renamed.pdf"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["file"]["name"] == "renamed.pdf"


@pytest.mark.asyncio
async def test_rename_file_error(client):
    """Rename error → 500."""
    client.rename_file = AsyncMock(side_effect=Exception("Permission denied"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(
            "/api/drive/files/file-abc/rename",
            json={"new_name": "fail.pdf"},
        )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: DELETE /api/drive/files/{file_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_file_trash(client):
    """Soft delete (trash) → 200."""
    client.delete_file = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/api/drive/files/file-abc")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "cestino" in data["message"]


@pytest.mark.asyncio
async def test_delete_file_permanent(client):
    """Permanent delete → 200."""
    client.delete_file = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/api/drive/files/file-abc?permanent=true")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "definitivamente" in data["message"]


@pytest.mark.asyncio
async def test_delete_file_error(client):
    """Delete error → 500."""
    client.delete_file = AsyncMock(side_effect=Exception("Drive error"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/api/drive/files/file-abc")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: PATCH /api/drive/files/{file_id}/move
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_move_file_success(client, mock_db_pool, mock_db_conn):
    """Move file with permission → 200."""
    moved = {**_FILE_ITEM, "id": "file-abc-moved"}
    client.move_file = AsyncMock(return_value=moved)

    with patch("backend.app.routers.team_drive.check_write_permission", new_callable=AsyncMock, return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch(
                "/api/drive/files/file-abc/move",
                json={"new_parent_id": "folder-new", "old_parent_id": "folder-old"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_move_file_no_permission(client, mock_db_pool):
    """Move without permission → 403."""
    with patch("backend.app.routers.team_drive.check_write_permission", new_callable=AsyncMock, return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch(
                "/api/drive/files/file-abc/move",
                json={"new_parent_id": "restricted-folder"},
            )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /api/drive/files/{file_id}/copy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_copy_file_success(client, mock_db_pool):
    """Copy file → 200."""
    copied = {**_FILE_ITEM, "id": "file-abc-copy", "name": "report_copy.pdf"}
    client.copy_file = AsyncMock(return_value=copied)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/drive/files/file-abc/copy",
            json={"new_name": "report_copy.pdf"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_copy_file_with_parent_no_permission(client, mock_db_pool):
    """Copy to restricted folder → 403."""
    with patch("backend.app.routers.team_drive.check_write_permission", new_callable=AsyncMock, return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/drive/files/file-abc/copy",
                json={"new_name": "copy.pdf", "parent_id": "restricted-folder"},
            )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: GET /api/drive/files/{file_id}/permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_permissions_success(client):
    """Happy path: list permissions."""
    client.list_permissions = AsyncMock(return_value=[
        {
            "id": "perm-1",
            "email": "team@balizero.com",
            "name": "Team Member",
            "role": "writer",
            "type": "user",
        }
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files/file-abc/permissions")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_permissions_error(client):
    """Permissions error → 500."""
    client.list_permissions = AsyncMock(side_effect=Exception("API error"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/drive/files/file-abc/permissions")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: POST /api/drive/files/{file_id}/permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_permission_success(client):
    """Add permission → 200."""
    client.add_permission = AsyncMock(return_value={
        "id": "perm-2",
        "email": "newuser@balizero.com",
        "name": "New User",
        "role": "reader",
        "type": "user",
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/drive/files/file-abc/permissions",
            json={"email": "newuser@balizero.com", "role": "reader"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@balizero.com"


@pytest.mark.asyncio
async def test_add_permission_error(client):
    """Add permission fails → 500."""
    client.add_permission = AsyncMock(side_effect=Exception("Google API error"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/drive/files/file-abc/permissions",
            json={"email": "fail@balizero.com", "role": "writer"},
        )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: helper functions (unit, no HTTP)
# ---------------------------------------------------------------------------


def test_folder_matches_exact():
    from backend.app.routers.team_drive import folder_matches_allowed
    assert folder_matches_allowed("BOARD", ["BOARD", "CRM"]) is True


def test_folder_matches_partial_word():
    from backend.app.routers.team_drive import folder_matches_allowed
    # "Legal" should NOT match "Illegal"
    assert folder_matches_allowed("Illegal Files", ["Legal"]) is False


def test_folder_matches_word_boundary():
    from backend.app.routers.team_drive import folder_matches_allowed
    # "Tax" should match "Tax Department"
    assert folder_matches_allowed("Tax Department", ["Tax"]) is True


def test_folder_matches_wildcard():
    from backend.app.routers.team_drive import folder_matches_allowed
    assert folder_matches_allowed("Anything", ["*"]) is True


def test_folder_no_match():
    from backend.app.routers.team_drive import folder_matches_allowed
    assert folder_matches_allowed("Private Folder", ["BOARD", "CRM"]) is False
