"""
Unit tests for Team Drive Router
Tests Google Drive file operations for team members
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Add backend to path
backend_path = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_current_user():
    """Mock current user dict"""
    return {"user_id": "user_123", "email": "test@example.com", "role": "team"}


@pytest.fixture
def mock_team_drive_service():
    """Mock TeamDriveService"""
    service = MagicMock()
    service.is_configured = MagicMock(return_value=True)
    service.get_connection_info = MagicMock(
        return_value={
            "mode": "oauth",
            "connected_as": "test@example.com",
            "is_oauth": True,
        }
    )
    service.list_files = AsyncMock(
        return_value={
            "files": [
                {
                    "id": "file1",
                    "name": "test_file.pdf",
                    "type": "file",
                    "mimeType": "application/pdf",
                    "size": 1024,
                    "modifiedTime": "2024-01-01T00:00:00Z",
                }
            ],
            "next_page_token": None,
        }
    )
    service.get_file_metadata = AsyncMock(
        return_value={
            "id": "file1",
            "name": "test_file.pdf",
            "type": "file",
            "mimeType": "application/pdf",
            "size": 1024,
        }
    )
    service.download_file = AsyncMock(
        return_value=(b"file content", "test_file.pdf", "application/pdf")
    )
    service.get_folder_path = AsyncMock(return_value=[{"id": "root", "name": "My Drive"}])
    service.search_files = AsyncMock(
        return_value=[
            {
                "id": "file1",
                "name": "test_file.pdf",
                "type": "file",
                "mimeType": "application/pdf",
            }
        ]
    )
    service.upload_file = AsyncMock(
        return_value={
            "id": "file_new",
            "name": "uploaded_file.pdf",
            "type": "file",
            "mimeType": "application/pdf",
            "size": 2048,
        }
    )
    service.create_folder = AsyncMock(
        return_value={
            "id": "folder_new",
            "name": "New Folder",
            "type": "folder",
            "mimeType": "application/vnd.google-apps.folder",
        }
    )
    service.create_google_doc = AsyncMock(
        return_value={
            "id": "doc_new",
            "name": "New Document",
            "type": "file",
            "mimeType": "application/vnd.google-apps.document",
        }
    )
    service.rename_file = AsyncMock(
        return_value={
            "id": "file1",
            "name": "renamed_file.pdf",
            "type": "file",
            "mimeType": "application/pdf",
        }
    )
    service.delete_file = AsyncMock(return_value=True)
    service.move_file = AsyncMock(
        return_value={
            "id": "file1",
            "name": "test_file.pdf",
            "type": "file",
            "mimeType": "application/pdf",
        }
    )
    service.copy_file = AsyncMock(
        return_value={
            "id": "file_copy",
            "name": "copy_of_file.pdf",
            "type": "file",
            "mimeType": "application/pdf",
        }
    )
    service.list_permissions = AsyncMock(
        return_value=[
            {
                "id": "perm1",
                "email": "user@example.com",
                "name": "Test User",
                "role": "reader",
                "type": "user",
            }
        ]
    )
    service.add_permission = AsyncMock(
        return_value={
            "id": "perm_new",
            "email": "new@example.com",
            "name": "New User",
            "role": "reader",
            "type": "user",
        }
    )
    service.update_permission = AsyncMock(
        return_value={
            "id": "perm1",
            "email": "user@example.com",
            "name": "Test User",
            "role": "writer",
            "type": "user",
        }
    )
    service.remove_permission = AsyncMock(return_value=True)
    return service


# ============================================================================
# Tests for helper functions
# ============================================================================


def test_folder_matches_allowed_wildcard():
    """Test folder_matches_allowed with wildcard"""
    from app.routers.team_drive import folder_matches_allowed

    assert folder_matches_allowed("any_folder", ["*"]) is True


def test_folder_matches_allowed_exact_match():
    """Test folder_matches_allowed with exact match"""
    from app.routers.team_drive import folder_matches_allowed

    assert folder_matches_allowed("Legal", ["Legal"]) is True
    assert folder_matches_allowed("legal", ["Legal"]) is True  # Case insensitive


def test_folder_matches_allowed_partial_match():
    """Test folder_matches_allowed with partial match"""
    from app.routers.team_drive import folder_matches_allowed

    assert folder_matches_allowed("Legal Documents", ["Legal"]) is True
    assert folder_matches_allowed("Legal", ["Legal Documents"]) is True


def test_folder_matches_allowed_no_match():
    """Test folder_matches_allowed with no match"""
    from app.routers.team_drive import folder_matches_allowed

    assert folder_matches_allowed("Other", ["Legal", "Tax"]) is False


@pytest.mark.asyncio
async def test_get_user_allowed_folders_user_not_found(mock_db_pool):
    """Test get_user_allowed_folders when user not found"""
    from app.routers.team_drive import get_user_allowed_folders

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value=None)

    folders, can_see_all = await get_user_allowed_folders("unknown@example.com", pool)

    assert can_see_all is False
    assert "_Shared" in folders or "Shared" in folders  # Default shared folders


@pytest.mark.asyncio
async def test_get_user_allowed_folders_with_wildcard(mock_db_pool):
    """Test get_user_allowed_folders with wildcard rule"""
    from app.routers.team_drive import get_user_allowed_folders

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[{"allowed_folders": ["*"], "priority": 1}])

    folders, can_see_all = await get_user_allowed_folders("test@example.com", pool)

    assert can_see_all is True
    assert "*" in folders


@pytest.mark.asyncio
async def test_check_is_board_true(mock_db_pool):
    """Test check_is_board returns True for board member"""
    from app.routers.team_drive import check_is_board

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value={"can_see_all": True})

    result = await check_is_board("board@example.com", pool)

    assert result is True


@pytest.mark.asyncio
async def test_check_is_board_false(mock_db_pool):
    """Test check_is_board returns False for non-board member"""
    from app.routers.team_drive import check_is_board

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value={"can_see_all": False})

    result = await check_is_board("user@example.com", pool)

    assert result is False


@pytest.mark.asyncio
async def test_get_drive_service_not_configured(mock_db_pool):
    """Test get_drive raises HTTPException when service not configured"""
    from app.routers.team_drive import get_drive

    pool, conn = mock_db_pool

    with patch("app.routers.team_drive.get_team_drive_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.is_configured.return_value = False
        mock_get_service.return_value = mock_service

        with pytest.raises(HTTPException) as exc:
            await get_drive(pool)

        assert exc.value.status_code == 503


# ============================================================================
# Tests for GET /status endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_drive_status_success(mock_team_drive_service, mock_current_user):
    """Test drive_status endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "connected"
            assert "mode" in data


@pytest.mark.asyncio
async def test_drive_status_error(mock_current_user):
    """Test drive_status endpoint error handling"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    mock_service = MagicMock()
    mock_service.list_files = AsyncMock(side_effect=Exception("Service error"))
    mock_service.get_connection_info = MagicMock(
        return_value={"mode": "oauth", "connected_as": "test", "is_oauth": True}
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_service):
            client = TestClient(app)
            response = client.get("/api/drive/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"


# ============================================================================
# Tests for GET /files endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_list_files_success(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test list_files endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.get("/api/drive/files")

                assert response.status_code == 200
                data = response.json()
                assert "files" in data
                assert len(data["files"]) > 0


@pytest.mark.asyncio
async def test_list_files_error(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test list_files endpoint error handling"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    mock_team_drive_service.list_files = AsyncMock(side_effect=Exception("Service error"))

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.get("/api/drive/files")

                assert response.status_code == 500


# ============================================================================
# Tests for GET /files/{file_id} endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_file_success(mock_team_drive_service, mock_current_user):
    """Test get_file endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/files/file1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "file1"
            assert data["name"] == "test_file.pdf"


@pytest.mark.asyncio
async def test_get_file_not_found(mock_team_drive_service, mock_current_user):
    """Test get_file endpoint file not found"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    mock_team_drive_service.get_file_metadata = AsyncMock(side_effect=Exception("Not found"))

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/files/invalid_id")

            assert response.status_code == 404


# ============================================================================
# Tests for GET /files/{file_id}/download endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_download_file_success(mock_team_drive_service, mock_current_user):
    """Test download_file endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/files/file1/download")

            assert response.status_code == 200
            assert response.headers["Content-Disposition"] == 'attachment; filename="test_file.pdf"'
            assert response.content == b"file content"


@pytest.mark.asyncio
async def test_download_file_error(mock_team_drive_service, mock_current_user):
    """Test download_file endpoint error handling"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    mock_team_drive_service.download_file = AsyncMock(side_effect=Exception("Download error"))

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/files/file1/download")

            assert response.status_code == 500


# ============================================================================
# Tests for GET /folders/{folder_id}/path endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_folder_path_success(mock_team_drive_service, mock_current_user):
    """Test get_folder_path endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/folders/folder1/path")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0


@pytest.mark.asyncio
async def test_get_folder_path_error(mock_team_drive_service, mock_current_user):
    """Test get_folder_path endpoint error handling"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    mock_team_drive_service.get_folder_path = AsyncMock(side_effect=Exception("Error"))

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/folders/invalid/path")

            assert response.status_code == 200
            data = response.json()
            assert data == []  # Returns empty list on error


# ============================================================================
# Tests for GET /search endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_search_files_success(mock_team_drive_service, mock_current_user):
    """Test search_files endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/search?q=test")

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "count" in data
            assert data["query"] == "test"


@pytest.mark.asyncio
async def test_search_files_error(mock_team_drive_service, mock_current_user):
    """Test search_files endpoint error handling"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    mock_team_drive_service.search_files = AsyncMock(side_effect=Exception("Search error"))

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/search?q=test")

            assert response.status_code == 500


# ============================================================================
# Tests for POST /files/upload endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_upload_file_success(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test upload_file endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])
    mock_team_drive_service.get_folder_path = AsyncMock(
        return_value=[{"id": "parent", "name": "Legal"}]
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.post(
                    "/api/drive/files/upload",
                    files={"file": ("test.pdf", b"content", "application/pdf")},
                    data={"parent_id": "parent_folder"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "file" in data


@pytest.mark.asyncio
async def test_upload_file_permission_denied(
    mock_team_drive_service, mock_current_user, mock_db_pool
):
    """Test upload_file endpoint permission denied"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])
    mock_team_drive_service.get_folder_path = AsyncMock(
        return_value=[{"id": "parent", "name": "Restricted"}]
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.post(
                    "/api/drive/files/upload",
                    files={"file": ("test.pdf", b"content", "application/pdf")},
                    data={"parent_id": "restricted_folder"},
                )

                assert response.status_code == 403


# ============================================================================
# Tests for POST /folders endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_create_folder_success(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test create_folder endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])
    mock_team_drive_service.get_folder_path = AsyncMock(
        return_value=[{"id": "parent", "name": "Legal"}]
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.post(
                    "/api/drive/folders",
                    json={"name": "New Folder", "parent_id": "parent_folder"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "file" in data


# ============================================================================
# Tests for POST /files/create endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_create_doc_success(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test create_doc endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])
    mock_team_drive_service.get_folder_path = AsyncMock(
        return_value=[{"id": "parent", "name": "Legal"}]
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.post(
                    "/api/drive/files/create",
                    json={"name": "New Doc", "parent_id": "parent_folder", "doc_type": "document"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True


@pytest.mark.asyncio
async def test_create_doc_invalid_type(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test create_doc endpoint invalid doc_type"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])
    mock_team_drive_service.create_google_doc = AsyncMock(
        side_effect=ValueError("Invalid doc_type")
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.post(
                    "/api/drive/files/create",
                    json={"name": "New Doc", "parent_id": "parent_folder", "doc_type": "invalid"},
                )

                assert response.status_code == 400


# ============================================================================
# Tests for PATCH /files/{file_id}/rename endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_rename_file_success(mock_team_drive_service, mock_current_user):
    """Test rename_file endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.patch(
                "/api/drive/files/file1/rename",
                json={"new_name": "renamed_file.pdf"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["file"]["name"] == "renamed_file.pdf"


# ============================================================================
# Tests for DELETE /files/{file_id} endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_delete_file_success(mock_team_drive_service, mock_current_user):
    """Test delete_file endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.delete("/api/drive/files/file1")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


@pytest.mark.asyncio
async def test_delete_file_permanent(mock_team_drive_service, mock_current_user):
    """Test delete_file endpoint with permanent=True"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.delete("/api/drive/files/file1?permanent=true")

            assert response.status_code == 200
            data = response.json()
            assert "eliminato definitivamente" in data["message"]


# ============================================================================
# Tests for PATCH /files/{file_id}/move endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_move_file_success(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test move_file endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])
    mock_team_drive_service.get_folder_path = AsyncMock(
        return_value=[{"id": "parent", "name": "Legal"}]
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.patch(
                    "/api/drive/files/file1/move",
                    json={"new_parent_id": "new_parent", "old_parent_id": "old_parent"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True


# ============================================================================
# Tests for POST /files/{file_id}/copy endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_copy_file_success(mock_team_drive_service, mock_current_user, mock_db_pool):
    """Test copy_file endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"department": "SETUP", "full_name": "Test User", "can_see_all": False}
    )
    conn.fetch = AsyncMock(return_value=[])
    mock_team_drive_service.get_folder_path = AsyncMock(
        return_value=[{"id": "parent", "name": "Legal"}]
    )

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            with patch("app.routers.team_drive.get_database_pool", return_value=pool):
                client = TestClient(app)
                response = client.post(
                    "/api/drive/files/file1/copy",
                    json={"new_name": "copy_of_file.pdf", "parent_id": "parent_folder"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True


# ============================================================================
# Tests for permissions endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_list_permissions_success(mock_team_drive_service, mock_current_user):
    """Test list_permissions endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.get("/api/drive/files/file1/permissions")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0


@pytest.mark.asyncio
async def test_add_permission_success(mock_team_drive_service, mock_current_user):
    """Test add_permission endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.post(
                "/api/drive/files/file1/permissions",
                json={"email": "new@example.com", "role": "reader", "send_notification": True},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "new@example.com"
            assert data["role"] == "reader"


@pytest.mark.asyncio
async def test_update_permission_success(mock_team_drive_service, mock_current_user):
    """Test update_permission endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.patch(
                "/api/drive/files/file1/permissions/perm1",
                json={"role": "writer"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["role"] == "writer"


@pytest.mark.asyncio
async def test_remove_permission_success(mock_team_drive_service, mock_current_user):
    """Test remove_permission endpoint success"""
    from fastapi import FastAPI

    from app.routers.team_drive import router

    app = FastAPI()
    app.include_router(router)

    with patch("app.routers.team_drive.get_current_user", return_value=mock_current_user):
        with patch("app.routers.team_drive.get_drive", return_value=mock_team_drive_service):
            client = TestClient(app)
            response = client.delete("/api/drive/files/file1/permissions/perm1")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
