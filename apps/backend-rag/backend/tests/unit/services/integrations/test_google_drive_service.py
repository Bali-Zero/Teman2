"""
Unit tests for GoogleDriveService.

Tests OAuth flow, token management, and file operations
with all external dependencies mocked.
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = {"content-type": "application/json"}
    return resp


def _make_pool(conn: AsyncMock | None = None):
    """Create a properly mocked asyncpg pool with async context manager."""
    pool = MagicMock()
    conn = conn or AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: Any) -> None:
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    pool._conn = conn
    return pool, conn


def _make_service(
    *,
    client_id: str = "test-client-id",
    client_secret: str = "test-client-secret",
    redirect_uri: str = "https://example.com/callback",
    root_folder_id: str | None = "root-folder-123",
    pool=None,
    conn=None,
):
    """Create GoogleDriveService with mock db_pool and settings."""
    mock_settings = MagicMock()
    mock_settings.google_drive_client_id = client_id
    mock_settings.google_drive_client_secret = client_secret
    mock_settings.google_drive_redirect_uri = redirect_uri
    mock_settings.google_drive_root_folder_id = root_folder_id

    if pool is None:
        pool, conn = _make_pool(conn)

    with patch(
        "backend.services.integrations.google_drive_service.settings",
        mock_settings,
    ):
        from backend.services.integrations.google_drive_service import (
            GoogleDriveService,
        )

        svc = GoogleDriveService(db_pool=pool)

    return svc, pool, conn


# ---------------------------------------------------------------------------
# Tests: Static / configuration helpers
# ---------------------------------------------------------------------------


class TestSanitizeDriveQueryString:
    def test_no_special_chars(self):
        from backend.services.integrations.google_drive_service import GoogleDriveService
        assert GoogleDriveService._sanitize_drive_query_string("hello world") == "hello world"

    def test_single_quote_escaped(self):
        from backend.services.integrations.google_drive_service import GoogleDriveService
        assert GoogleDriveService._sanitize_drive_query_string("it's a test") == "it\\'s a test"

    def test_backslash_escaped(self):
        from backend.services.integrations.google_drive_service import GoogleDriveService
        assert GoogleDriveService._sanitize_drive_query_string("a\\b") == "a\\\\b"

    def test_both_escaped(self):
        from backend.services.integrations.google_drive_service import GoogleDriveService
        result = GoogleDriveService._sanitize_drive_query_string("it's a \\test")
        assert result == "it\\'s a \\\\test"


class TestIsConfigured:
    def test_configured_when_both_present(self):
        svc, _, _ = _make_service()
        assert svc.is_configured() is True

    def test_not_configured_missing_client_id(self):
        svc, _, _ = _make_service(client_id="")
        assert svc.is_configured() is False

    def test_not_configured_missing_secret(self):
        svc, _, _ = _make_service(client_secret="")
        assert svc.is_configured() is False


class TestGetAuthorizationUrl:
    def test_returns_url_with_params(self):
        svc, _, _ = _make_service()
        url = svc.get_authorization_url(state="csrf-token-123")
        assert "accounts.google.com" in url
        assert "client_id=test-client-id" in url
        assert "state=csrf-token-123" in url
        assert "access_type=offline" in url

    def test_raises_when_not_configured(self):
        svc, _, _ = _make_service(client_id="", client_secret="")
        with pytest.raises(ValueError, match="not configured"):
            svc.get_authorization_url(state="x")


# ---------------------------------------------------------------------------
# Tests: HTTP client lifecycle
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_creates_client_on_first_call(self):
        svc, _, _ = _make_service()
        client = svc._get_client()
        assert isinstance(client, httpx.AsyncClient)

    def test_reuses_open_client(self):
        svc, _, _ = _make_service()
        c1 = svc._get_client()
        c2 = svc._get_client()
        assert c1 is c2


@pytest.mark.asyncio
class TestClose:
    async def test_close_open_client(self):
        svc, _, _ = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_awaited_once()

    async def test_close_already_closed(self):
        svc, _, _ = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = True
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_not_awaited()

    async def test_close_no_client(self):
        svc, _, _ = _make_service()
        await svc.close()


# ---------------------------------------------------------------------------
# Tests: Token exchange
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExchangeCode:
    async def test_successful_exchange(self):
        svc, _, conn = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _make_mock_response(
            200, {"access_token": "at-123", "refresh_token": "rt-456", "expires_in": 3600},
        )
        svc._client = mock_client

        result = await svc.exchange_code("auth-code", "user-1")
        assert result["access_token"] == "at-123"
        conn.execute.assert_awaited_once()

    async def test_exchange_failure(self):
        svc, _, _ = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _make_mock_response(
            400, {"error": "invalid_grant", "error_description": "Bad code"},
        )
        svc._client = mock_client

        with pytest.raises(ValueError, match="Bad code"):
            await svc.exchange_code("bad-code", "user-1")


# ---------------------------------------------------------------------------
# Tests: Token refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetValidToken:
    async def test_returns_valid_token(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "access_token": "valid-token", "refresh_token": "rt", "expires_at": future,
        }
        svc, _, _ = _make_service(conn=conn)

        result = await svc.get_valid_token("user-1")
        assert result == "valid-token"

    async def test_returns_none_no_token(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = None
        svc, _, _ = _make_service(conn=conn)

        result = await svc.get_valid_token("user-1")
        assert result is None

    async def test_refreshes_expired_token(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "access_token": "expired-token", "refresh_token": "rt-valid", "expires_at": past,
        }
        svc, _, _ = _make_service(conn=conn)

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _make_mock_response(
            200, {"access_token": "new-token", "expires_in": 3600},
        )
        svc._client = mock_client

        result = await svc.get_valid_token("user-1")
        assert result == "new-token"

    async def test_returns_none_expired_no_refresh(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "access_token": "expired", "refresh_token": None, "expires_at": past,
        }
        svc, _, _ = _make_service(conn=conn)

        result = await svc.get_valid_token("user-1")
        assert result is None


@pytest.mark.asyncio
class TestRefreshToken:
    async def test_refresh_failure_returns_none(self):
        svc, _, _ = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _make_mock_response(401, {})
        svc._client = mock_client

        result = await svc._refresh_token("user-1", "bad-rt")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Connection check / disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIsConnected:
    async def test_connected_when_valid_token(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        assert await svc.is_connected("user-1") is True

    async def test_not_connected_when_no_token(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value=None)
        assert await svc.is_connected("user-1") is False


@pytest.mark.asyncio
class TestDisconnect:
    async def test_disconnect_with_existing_token(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = {"access_token": "to-revoke"}
        svc, _, _ = _make_service(conn=conn)

        mock_client = AsyncMock()
        mock_client.is_closed = False
        svc._client = mock_client

        result = await svc.disconnect("user-1")
        assert result is True
        mock_client.post.assert_awaited_once()
        conn.execute.assert_awaited_once()

    async def test_disconnect_no_existing_token(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = None
        svc, _, _ = _make_service(conn=conn)

        result = await svc.disconnect("user-1")
        assert result is True


# ---------------------------------------------------------------------------
# Tests: File operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListFiles:
    async def test_list_files_success(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token-123")

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = _make_mock_response(
            200, {"files": [{"id": "f1", "name": "doc.pdf"}], "nextPageToken": "page2"},
        )
        svc._client = mock_client

        result = await svc.list_files("user-1")
        assert len(result["files"]) == 1
        assert result["next_page_token"] == "page2"

    async def test_list_files_not_connected(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not connected"):
            await svc.list_files("user-1")

    async def test_list_files_api_error(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = _make_mock_response(403, {"error": {"message": "Forbidden"}})
        svc._client = mock_client
        with pytest.raises(ValueError, match="Forbidden"):
            await svc.list_files("user-1")


@pytest.mark.asyncio
class TestGetFile:
    async def test_get_file_success(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = _make_mock_response(200, {"id": "f1", "name": "test.pdf"})
        svc._client = mock_client
        result = await svc.get_file("user-1", "f1")
        assert result["name"] == "test.pdf"

    async def test_get_file_not_connected(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not connected"):
            await svc.get_file("user-1", "f1")


@pytest.mark.asyncio
class TestSearchFiles:
    async def test_search_returns_results(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = _make_mock_response(200, {"files": [{"id": "f1"}]})
        svc._client = mock_client
        result = await svc.search_files("user-1", "passport")
        assert len(result) == 1

    async def test_search_empty_on_failure(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = _make_mock_response(500, {})
        svc._client = mock_client
        result = await svc.search_files("user-1", "passport")
        assert result == []


@pytest.mark.asyncio
class TestGetFolderPath:
    async def test_folder_path_traversal(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.side_effect = [
            _make_mock_response(200, {"id": "f1", "name": "Sub", "parents": ["root-folder-123"]}),
        ]
        svc._client = mock_client
        result = await svc.get_folder_path("user-1", "f1")
        assert len(result) == 1
        assert result[0]["name"] == "Sub"


@pytest.mark.asyncio
class TestGetUserFolder:
    async def test_finds_user_folder(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = _make_mock_response(200, {"files": [{"id": "uf-1", "name": "Anton"}]})
        svc._client = mock_client
        result = await svc.get_user_folder("user-1", "anton@balizero.com")
        assert result["name"] == "Anton"

    async def test_returns_none_when_no_token(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value=None)
        result = await svc.get_user_folder("user-1", "anton@balizero.com")
        assert result is None


@pytest.mark.asyncio
class TestCreateFolder:
    async def test_create_success(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _make_mock_response(200, {"id": "nf", "name": "tf", "webViewLink": "url"})
        svc._client = mock_client
        result = await svc.create_folder("user-1", "tf", parent_id="p1")
        assert result["id"] == "nf"

    async def test_create_failure(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _make_mock_response(403, {"error": {"message": "quota exceeded"}})
        svc._client = mock_client
        with pytest.raises(ValueError, match="quota exceeded"):
            await svc.create_folder("user-1", "tf")


@pytest.mark.asyncio
class TestListFolderFiles:
    async def test_list_with_pagination(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = _make_mock_response(200, {
            "files": [
                {"id": "f1", "name": "a.pdf", "mimeType": "application/pdf", "size": "1024", "modifiedTime": "2026-01-01", "createdTime": "2026-01-01"},
                {"id": "f2", "name": "b/", "mimeType": "application/vnd.google-apps.folder"},
            ],
        })
        svc._client = mock_client
        result = await svc.list_folder_files("user-1", "folder-1", limit=10, offset=0)
        assert result["total"] == 2
        assert result["files"][0]["size_bytes"] == 1024
        assert result["files"][1]["is_folder"] is True


@pytest.mark.asyncio
class TestUploadFileToFolder:
    async def test_upload_success(self):
        svc, _, _ = _make_service()
        svc.get_valid_token = AsyncMock(return_value="token")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _make_mock_response(200, {"id": "up1", "name": "p.pdf", "size": "2048"})
        mock_client.patch.return_value = _make_mock_response(200, {})
        svc._client = mock_client

        result = await svc.upload_file_to_folder("user-1", "f1", b"PDF", "p.pdf")
        assert result["id"] == "up1"
        assert result["download_url"] == "/api/documents/proxy/up1"


@pytest.mark.asyncio
class TestGetFolderStats:
    async def test_delegates_to_get_folder_structure(self):
        svc, _, _ = _make_service()
        svc.get_folder_structure = AsyncMock(return_value={
            "root_folder_id": "r1",
            "folders": [{"name": "00_Profile", "file_count": 5, "total_size_bytes": 1048576, "last_modified": None}],
            "total_files": 5,
            "total_size_bytes": 1048576,
        })
        result = await svc.get_folder_stats("user-1", "r1")
        assert result["total_files"] == 5
        assert result["total_size_mb"] == 1.0
        assert "00_Profile" in result["by_category"]
