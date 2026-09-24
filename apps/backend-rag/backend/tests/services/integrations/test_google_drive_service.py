"""
Tests for GoogleDriveService.

Covers:
- Drive query injection sanitization
- Token refresh logic
- File operations (mocked httpx + asyncpg)
- close() lifecycle
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.integrations.google_drive_service import GoogleDriveService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> GoogleDriveService:
    """Return a GoogleDriveService with a mock DB pool."""
    pool = AsyncMock()
    with patch("backend.services.integrations.google_drive_service.settings") as mock_settings:
        mock_settings.google_drive_client_id = "fake-client-id"
        mock_settings.google_drive_client_secret = "fake-secret"
        mock_settings.google_drive_redirect_uri = "http://localhost/callback"
        mock_settings.google_drive_root_folder_id = "root-folder-id"
        svc = GoogleDriveService(db_pool=pool)
    return svc


# ---------------------------------------------------------------------------
# _sanitize_drive_query_string
# ---------------------------------------------------------------------------


class TestSanitizeDriveQueryString:
    def test_plain_string_unchanged(self):
        assert GoogleDriveService._sanitize_drive_query_string("hello world") == "hello world"

    def test_single_quote_escaped(self):
        result = GoogleDriveService._sanitize_drive_query_string("O'Brien")
        assert result == "O\\'Brien"

    def test_backslash_escaped(self):
        result = GoogleDriveService._sanitize_drive_query_string("path\\file")
        assert result == "path\\\\file"

    def test_injection_attempt_neutralized(self):
        # Classic Drive query injection: break out of contains clause
        malicious = "x' or '1'='1"
        result = GoogleDriveService._sanitize_drive_query_string(malicious)
        # The injected single-quotes must be escaped
        assert "\\'" in result
        # The result must NOT contain unescaped single quotes that would break
        # out of the surrounding Drive query string literal.
        assert result == "x\\' or \\'1\\'=\\'1"

    def test_empty_string(self):
        assert GoogleDriveService._sanitize_drive_query_string("") == ""

    def test_both_backslash_and_quote(self):
        result = GoogleDriveService._sanitize_drive_query_string("\\'")
        # backslash -> \\\\ then quote -> \\'  →  final: \\\\'
        assert result == "\\\\\\'", f"Unexpected: {result!r}"


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


class TestIsConfigured:
    def test_configured_when_both_set(self):
        svc = _make_service()
        svc.client_id = "id"
        svc.client_secret = "secret"
        assert svc.is_configured() is True

    def test_not_configured_when_client_id_missing(self):
        svc = _make_service()
        svc.client_id = ""
        svc.client_secret = "secret"
        assert svc.is_configured() is False

    def test_not_configured_when_secret_missing(self):
        svc = _make_service()
        svc.client_id = "id"
        svc.client_secret = ""
        assert svc.is_configured() is False


# ---------------------------------------------------------------------------
# get_authorization_url
# ---------------------------------------------------------------------------


class TestGetAuthorizationUrl:
    def test_returns_url_with_state(self):
        svc = _make_service()
        url = svc.get_authorization_url(state="csrf-token-123")
        assert "accounts.google.com" in url
        assert "csrf-token-123" in url
        assert "offline" in url

    def test_raises_when_not_configured(self):
        svc = _make_service()
        svc.client_id = ""
        with pytest.raises(ValueError):
            svc.get_authorization_url(state="x")


# ---------------------------------------------------------------------------
# _get_client / close
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    def test_get_client_creates_instance(self):
        svc = _make_service()
        client = svc._get_client()
        import httpx

        assert isinstance(client, httpx.AsyncClient)

    def test_get_client_reuses_open_instance(self):
        svc = _make_service()
        c1 = svc._get_client()
        c2 = svc._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        svc = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_skips_already_closed(self):
        svc = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = True
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_safe_when_no_client(self):
        svc = _make_service()
        svc._client = None
        # Must not raise
        await svc.close()


# ---------------------------------------------------------------------------
# get_valid_token — token still valid
# ---------------------------------------------------------------------------


class TestGetValidToken:
    @pytest.mark.asyncio
    async def test_returns_token_when_not_expired(self):
        svc = _make_service()
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "access_token": "valid-token",
            "refresh_token": "refresh-tok",
            "expires_at": future_expiry,
        }
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        svc.db_pool.acquire = MagicMock(return_value=mock_ctx)

        token = await svc.get_valid_token("user1")
        assert token == "valid-token"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_row(self):
        svc = _make_service()

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        svc.db_pool.acquire = MagicMock(return_value=mock_ctx)

        token = await svc.get_valid_token("user1")
        assert token is None


# ---------------------------------------------------------------------------
# search_files — query injection guard
# ---------------------------------------------------------------------------


class TestSearchFiles:
    @pytest.mark.asyncio
    async def test_sanitizes_query_in_request(self):
        """Malicious search query must not reach the Drive API unescaped."""
        svc = _make_service()

        # Provide a valid token so the method proceeds to the HTTP call
        svc.get_valid_token = AsyncMock(return_value="tok")

        captured_params: dict = {}

        async def fake_get(url, **kwargs):
            captured_params.update(kwargs.get("params", {}))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"files": []}
            return mock_resp

        mock_client = AsyncMock()
        mock_client.get = fake_get
        mock_client.is_closed = False
        svc._client = mock_client

        malicious_query = "x' or '1'='1"
        await svc.search_files("user1", malicious_query)

        q = captured_params.get("q", "")
        # The raw single-quotes from the injection must be escaped as \'
        assert "\\'" in q, f"Expected escaped quotes in Drive query: {q!r}"
        # Crucially: the malicious payload must not appear verbatim in the query.
        assert "x' or '1'='1" not in q, f"Unescaped injection payload found in Drive query: {q!r}"


# ---------------------------------------------------------------------------
# list_folder_files — search sanitization
# ---------------------------------------------------------------------------


class TestListFolderFiles:
    @pytest.mark.asyncio
    async def test_sanitizes_search_param(self):
        svc = _make_service()
        svc.get_valid_token = AsyncMock(return_value="tok")

        captured_params: dict = {}

        async def fake_get(url, **kwargs):
            captured_params.update(kwargs.get("params", {}))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"files": []}
            return mock_resp

        mock_client = AsyncMock()
        mock_client.get = fake_get
        mock_client.is_closed = False
        svc._client = mock_client

        await svc.list_folder_files(
            user_id="user1",
            folder_id="folder123",
            search="test' AND trashed=false",
        )

        q = captured_params.get("q", "")
        # Injected single-quote must be escaped
        assert "\\'" in q
