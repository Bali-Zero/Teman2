import pytest

from backend.services.common import cache as cache_module
from backend.services.crm.client_identity_resolver import ClientIdentityResolver, normalize_phone


class FakeAcquire:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def __aenter__(self) -> object:
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


class FakeConn:
    def __init__(
        self,
        fetchvals: list[object] | None = None,
        fetchrows: list[dict | None] | None = None,
        fetch_rows: list[dict] | None = None,
        execute_result: str = "UPDATE 1",
    ) -> None:
        self.fetchvals = fetchvals or []
        self.fetchrows = fetchrows or []
        self.fetch_rows = fetch_rows or []
        self.execute_result = execute_result
        self.fetchval_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchval(self, query: str, *args: object) -> object:
        self.fetchval_calls.append((query, args))
        return self.fetchvals.pop(0) if self.fetchvals else None

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        self.fetchrow_calls.append((query, args))
        return self.fetchrows.pop(0) if self.fetchrows else None

    async def fetch(self, query: str, *args: object) -> list[dict]:
        self.fetch_calls.append((query, args))
        return self.fetch_rows

    async def execute(self, query: str, *args: object) -> str:
        self.execute_calls.append((query, args))
        return self.execute_result


def test_normalize_phone_delegates_to_canonical_e164_normalizer() -> None:
    assert normalize_phone(None) is None
    assert normalize_phone("0812-3456-7890") == "+6281234567890"
    assert normalize_phone("+62 812 3456 7890") == "+6281234567890"


@pytest.mark.asyncio
async def test_find_client_by_telegram_uses_string_identifier() -> None:
    conn = FakeConn(fetchvals=[123])
    resolver = ClientIdentityResolver(FakePool(conn))

    result = await resolver.find_client_by_telegram(987654)

    assert result == 123
    assert conn.fetchval_calls[0][1] == ("987654",)


@pytest.mark.asyncio
async def test_find_client_by_whatsapp_falls_back_to_clients_table() -> None:
    conn = FakeConn(fetchvals=[None, 456])
    resolver = ClientIdentityResolver(FakePool(conn))

    result = await resolver.find_client_by_whatsapp("0812-3456-7890")

    assert result == 456
    assert conn.fetchval_calls[0][1] == ("+6281234567890",)
    assert conn.fetchval_calls[1][1] == ("+6281234567890",)


@pytest.mark.asyncio
async def test_find_client_by_email_short_circuits_empty_email() -> None:
    conn = FakeConn(fetchvals=[789])
    resolver = ClientIdentityResolver(FakePool(conn))

    assert await resolver.find_client_by_email("") is None
    assert await resolver.find_client_by_email("Client@Example.com") == 789
    assert conn.fetchval_calls[0][1] == ("Client@Example.com",)


@pytest.mark.asyncio
async def test_link_messaging_user_to_client_reports_updated_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_invalidate(pattern: str) -> int:
        return 1

    monkeypatch.setattr(cache_module, "_invalidate_cache", fake_invalidate)
    conn = FakeConn(execute_result="UPDATE 1")
    resolver = ClientIdentityResolver(FakePool(conn))

    assert await resolver.link_messaging_user_to_client("whatsapp", "0812 3456 7890", 99)
    assert conn.execute_calls[0][1] == (99, "+6281234567890")
    assert not await resolver.link_messaging_user_to_client("unknown", "id", 99)


@pytest.mark.asyncio
async def test_resolve_or_create_client_creates_when_no_existing_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_invalidate(pattern: str) -> int:
        return 1

    monkeypatch.setattr(cache_module, "_invalidate_cache", fake_invalidate)
    conn = FakeConn(fetchvals=[None], fetchrows=[{"id": 321}], execute_result="UPDATE 0")
    resolver = ClientIdentityResolver(FakePool(conn))

    client_id, is_new = await resolver.resolve_or_create_client(
        "email",
        "client@example.com",
        {"full_name": "Client Name", "email": "client@example.com", "source": "email"},
    )

    assert (client_id, is_new) == (321, True)
    assert "INSERT INTO clients" in conn.fetchrow_calls[0][0]


@pytest.mark.asyncio
async def test_get_client_channels_returns_plain_dicts() -> None:
    conn = FakeConn(
        fetch_rows=[
            {
                "channel": "telegram",
                "identifier": "123",
                "active": True,
                "created_at": None,
                "last_message_at": None,
            }
        ]
    )
    resolver = ClientIdentityResolver(FakePool(conn))

    channels = await resolver.get_client_channels(42)

    assert channels == [
        {
            "channel": "telegram",
            "identifier": "123",
            "active": True,
            "created_at": None,
            "last_message_at": None,
        }
    ]
    assert conn.fetch_calls[0][1] == (42,)
