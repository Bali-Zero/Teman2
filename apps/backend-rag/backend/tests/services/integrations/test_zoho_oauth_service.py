from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from backend.services.integrations.zoho_oauth_service import ZohoOAuthService


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any] | None] | None = None) -> None:
        self.rows = rows or []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((sql, args))
        if self.rows:
            return self.rows.pop(0)
        return None

    async def execute(self, sql: str, *args: Any) -> str:
        self.execute_calls.append((sql, args))
        return "OK"


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any],
        *,
        status_code: int = 200,
        content: bytes = b"payload",
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = content

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(
        self,
        *,
        post_responses: list[FakeResponse] | None = None,
        get_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.post_responses = post_responses or []
        self.get_responses = get_responses or []
        self.posts: list[dict[str, Any]] = []
        self.gets: list[dict[str, Any]] = []
        self.is_closed = False

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        if self.post_responses:
            return self.post_responses.pop(0)
        return FakeResponse({"access_token": "new-token"})

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.gets.append({"url": url, **kwargs})
        if self.get_responses:
            return self.get_responses.pop(0)
        return FakeResponse({"data": []})

    async def aclose(self) -> None:
        self.is_closed = True


def make_service(
    connection: FakeConnection | None = None,
    client: FakeClient | None = None,
) -> ZohoOAuthService:
    service = ZohoOAuthService.__new__(ZohoOAuthService)
    service.db_pool = FakePool(connection or FakeConnection())
    service.client_id = "client-id"
    service.client_secret = "client-secret"
    service.redirect_uri = "https://kita.balizero.com/oauth"
    service.accounts_url = "https://accounts.zoho.com"
    service.api_domain = "https://mail.zoho.com"
    service._client = client

    def fake_get_client() -> FakeClient:
        if service._client is None:
            service._client = FakeClient()
        return service._client

    service._get_client = fake_get_client  # type: ignore[method-assign]
    return service


def test_get_authorization_url_includes_scopes_and_state() -> None:
    service = make_service()

    url = service.get_authorization_url("state-123")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.path == "/oauth/v2/auth"
    assert params["client_id"] == ["client-id"]
    assert params["response_type"] == ["code"]
    assert params["access_type"] == ["offline"]
    assert params["prompt"] == ["consent"]
    assert params["state"] == ["state-123"]
    for scope in ZohoOAuthService.SCOPES:
        assert scope in params["scope"][0]


def test_get_authorization_url_requires_client_id() -> None:
    service = make_service()
    service.client_id = ""

    with pytest.raises(ValueError, match="ZOHO_CLIENT_ID missing"):
        service.get_authorization_url("state-123")


@pytest.mark.asyncio
async def test_exchange_code_posts_token_form_and_stores_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient(
        post_responses=[
            FakeResponse(
                {
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 1800,
                },
            ),
        ],
    )
    service = make_service(client=client)
    stored: dict[str, Any] = {}

    async def fake_get_account_info(access_token: str) -> dict[str, str]:
        assert access_token == "access-1"
        return {"account_id": "account-1", "email": "zero@example.com"}

    async def fake_store_tokens(**kwargs: Any) -> None:
        stored.update(kwargs)

    monkeypatch.setattr(service, "_get_account_info", fake_get_account_info)
    monkeypatch.setattr(service, "_store_tokens", fake_store_tokens)

    token_data = await service.exchange_code("code-1", "user-1")

    assert token_data["access_token"] == "access-1"
    assert client.posts[0]["url"] == "https://accounts.zoho.com/oauth/v2/token"
    assert client.posts[0]["data"] == {
        "grant_type": "authorization_code",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "redirect_uri": "https://kita.balizero.com/oauth",
        "code": "code-1",
    }
    assert stored == {
        "user_id": "user-1",
        "account_id": "account-1",
        "email_address": "zero@example.com",
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "expires_in": 1800,
    }


@pytest.mark.asyncio
async def test_exchange_code_rejects_oauth_error_payload() -> None:
    client = FakeClient(post_responses=[FakeResponse({"error": "invalid_grant"})])
    service = make_service(client=client)

    with pytest.raises(ValueError, match="OAuth error: invalid_grant"):
        await service.exchange_code("bad-code", "user-1")


@pytest.mark.asyncio
async def test_get_account_info_extracts_primary_email() -> None:
    client = FakeClient(
        get_responses=[
            FakeResponse(
                {
                    "data": [
                        {
                            "accountId": "account-1",
                            "email": [
                                {"isPrimary": False, "mailId": "alias@example.com"},
                                {"isPrimary": True, "mailId": "zero@example.com"},
                            ],
                        },
                    ],
                },
            ),
        ],
    )
    service = make_service(client=client)

    account = await service._get_account_info("access-1")

    assert account == {"account_id": "account-1", "email": "zero@example.com"}
    assert client.gets[0]["headers"] == {"Authorization": "Zoho-oauthtoken access-1"}


@pytest.mark.asyncio
async def test_store_tokens_upserts_expiry_and_scopes() -> None:
    connection = FakeConnection()
    service = make_service(connection=connection)

    await service._store_tokens(
        user_id="user-1",
        account_id="account-1",
        email_address="zero@example.com",
        access_token="access-1",
        refresh_token="refresh-1",
        expires_in=1800,
    )

    sql, args = connection.execute_calls[0]
    assert "INSERT INTO zoho_email_tokens" in sql
    assert args[:5] == (
        "user-1",
        "account-1",
        "zero@example.com",
        "access-1",
        "refresh-1",
    )
    assert isinstance(args[5], datetime)
    assert args[6] == ZohoOAuthService.SCOPES
    assert args[7] == "https://mail.zoho.com"


@pytest.mark.asyncio
async def test_get_valid_token_returns_current_token_without_refresh() -> None:
    connection = FakeConnection(
        [
            {
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "account_id": "account-1",
            },
        ],
    )
    service = make_service(connection=connection)

    assert await service.get_valid_token("user-1") == "access-1"


@pytest.mark.asyncio
async def test_get_valid_token_refreshes_when_expiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(
        [
            {
                "access_token": "old-access",
                "refresh_token": "refresh-1",
                "token_expires_at": datetime.now(timezone.utc) + timedelta(minutes=1),
                "account_id": "account-1",
            },
        ],
    )
    service = make_service(connection=connection)
    refreshed: dict[str, str] = {}

    async def fake_refresh_token(user_id: str, account_id: str, refresh_token: str) -> str:
        refreshed.update(
            {"user_id": user_id, "account_id": account_id, "refresh_token": refresh_token},
        )
        return "fresh-access"

    monkeypatch.setattr(service, "_refresh_token", fake_refresh_token)

    assert await service.get_valid_token("user-1") == "fresh-access"
    assert refreshed == {
        "user_id": "user-1",
        "account_id": "account-1",
        "refresh_token": "refresh-1",
    }


@pytest.mark.asyncio
async def test_get_valid_token_rejects_permanently_invalidated_token() -> None:
    connection = FakeConnection(
        [
            {
                "access_token": "old-access",
                "refresh_token": "refresh-1",
                "token_expires_at": datetime.now(timezone.utc) - timedelta(days=181),
                "account_id": "account-1",
            },
        ],
    )
    service = make_service(connection=connection)

    with pytest.raises(ValueError, match="reconnect required"):
        await service.get_valid_token("user-1")


@pytest.mark.asyncio
async def test_refresh_token_updates_database() -> None:
    connection = FakeConnection()
    client = FakeClient(post_responses=[FakeResponse({"access_token": "fresh", "expires_in": 900})])
    service = make_service(connection=connection, client=client)

    assert await service._refresh_token("user-1", "account-1", "refresh-1") == "fresh"
    assert client.posts[0]["data"] == {
        "grant_type": "refresh_token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-1",
    }
    sql, args = connection.execute_calls[0]
    assert "UPDATE zoho_email_tokens" in sql
    assert args[0] == "fresh"
    assert args[2:] == ("user-1", "account-1")


@pytest.mark.asyncio
async def test_refresh_token_invalidates_stored_token_on_oauth_error() -> None:
    connection = FakeConnection()
    client = FakeClient(post_responses=[FakeResponse({"error": "invalid_code"})])
    service = make_service(connection=connection, client=client)

    with pytest.raises(ValueError, match="Refresh error: invalid_code"):
        await service._refresh_token("user-1", "account-1", "refresh-1")

    assert "SET token_expires_at" in connection.execute_calls[0][0]
    assert connection.execute_calls[0][1] == ("user-1", "account-1")


@pytest.mark.asyncio
async def test_get_account_id_returns_row_or_raises() -> None:
    service = make_service(FakeConnection([{"account_id": "account-1"}]))

    assert await service.get_account_id("user-1") == "account-1"

    missing = make_service(FakeConnection([None]))
    with pytest.raises(ValueError, match="No Zoho account connected"):
        await missing.get_account_id("user-1")


@pytest.mark.asyncio
async def test_get_connection_status_reports_connected_and_disconnected() -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    connected = make_service(
        FakeConnection(
            [
                {
                    "account_id": "account-1",
                    "email_address": "zero@example.com",
                    "token_expires_at": expires_at,
                    "api_domain": "https://mail.zoho.com",
                },
            ],
        ),
    )
    disconnected = make_service(FakeConnection([None]))

    assert await connected.get_connection_status("user-1") == {
        "connected": True,
        "email": "zero@example.com",
        "account_id": "account-1",
        "expires_at": expires_at.isoformat(),
        "api_domain": "https://mail.zoho.com",
    }
    assert await disconnected.get_connection_status("user-1") == {
        "connected": False,
        "email": None,
        "account_id": None,
        "expires_at": None,
    }


@pytest.mark.asyncio
async def test_disconnect_revokes_refresh_token_and_clears_storage() -> None:
    connection = FakeConnection([{"refresh_token": "refresh-1"}])
    client = FakeClient()
    service = make_service(connection=connection, client=client)

    assert await service.disconnect("user-1") is True
    assert client.posts[0]["url"] == "https://accounts.zoho.com/oauth/v2/token/revoke"
    assert client.posts[0]["params"] == {"token": "refresh-1"}
    assert "DELETE FROM zoho_email_tokens" in connection.execute_calls[0][0]
    assert "DELETE FROM zoho_email_cache" in connection.execute_calls[1][0]


@pytest.mark.asyncio
async def test_close_closes_http_client() -> None:
    client = FakeClient()
    service = make_service(client=client)

    await service.close()

    assert client.is_closed is True
