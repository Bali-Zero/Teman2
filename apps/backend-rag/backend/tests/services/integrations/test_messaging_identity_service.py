from __future__ import annotations

from typing import Any

import pytest

from backend.services.integrations import messaging_identity_service as identity_module
from backend.services.integrations.messaging_identity_service import MessagingIdentityService


class FakeConnection:
    def __init__(
        self,
        *,
        fetchrow_result: dict[str, Any] | None = None,
        fetch_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self.fetchrow_result = fetchrow_result
        self.fetch_result = fetch_result or []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((sql, args))
        return self.fetchrow_result

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((sql, args))
        return self.fetch_result

    async def execute(self, sql: str, *args: Any) -> None:
        self.execute_calls.append((sql, args))


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def test_get_messaging_identity_service_reuses_singleton() -> None:
    identity_module._messaging_identity_service = None
    pool = FakePool(FakeConnection())

    first = identity_module.get_messaging_identity_service(pool)
    second = identity_module.get_messaging_identity_service(FakePool(FakeConnection()))

    try:
        assert first is second
        assert first.db_pool is pool
    finally:
        identity_module._messaging_identity_service = None


@pytest.mark.asyncio
async def test_get_user_by_phone_normalizes_plus_prefix() -> None:
    row = {
        "user_id": "user-1",
        "display_name": "Client",
        "verified": True,
        "last_message_at": None,
    }
    connection = FakeConnection(fetchrow_result=row)
    service = MessagingIdentityService(FakePool(connection))

    assert await service.get_user_by_phone("+628123") == row
    assert connection.fetchrow_calls[0][1] == ("628123",)


@pytest.mark.asyncio
async def test_get_user_by_telegram_returns_mapping() -> None:
    row = {"user_id": "user-1", "display_name": "Client", "verified": False}
    connection = FakeConnection(fetchrow_result=row)
    service = MessagingIdentityService(FakePool(connection))

    assert await service.get_user_by_telegram(12345) == row
    assert connection.fetchrow_calls[0][1] == (12345,)


@pytest.mark.asyncio
async def test_create_mapping_validates_channel_and_required_identifier() -> None:
    service = MessagingIdentityService(FakePool(FakeConnection()))

    assert await service.create_mapping("user-1", "sms") is False
    assert await service.create_mapping("user-1", "whatsapp") is False
    assert await service.create_mapping("user-1", "telegram") is False


@pytest.mark.asyncio
async def test_create_mapping_persists_normalized_whatsapp_phone() -> None:
    connection = FakeConnection()
    service = MessagingIdentityService(FakePool(connection))

    result = await service.create_mapping(
        user_id="user-1",
        channel="whatsapp",
        phone="+628123",
        display_name="Client",
        verified=True,
    )

    assert result is True
    _, args = connection.execute_calls[0]
    assert args == ("user-1", "whatsapp", "628123", None, "Client", True)


@pytest.mark.asyncio
async def test_update_last_message_and_deactivate_require_an_identifier() -> None:
    connection = FakeConnection()
    service = MessagingIdentityService(FakePool(connection))

    assert await service.update_last_message() is False
    assert await service.deactivate_mapping() is False
    assert await service.update_last_message(phone="+628123") is True
    assert await service.deactivate_mapping(telegram_chat_id=456) is True
    assert connection.execute_calls[0][1] == ("628123",)
    assert connection.execute_calls[1][1] == (456,)


@pytest.mark.asyncio
async def test_get_mappings_for_user_returns_rows_as_dicts() -> None:
    rows = [
        {"id": 1, "channel": "whatsapp", "phone": "628123", "verified": True},
        {"id": 2, "channel": "telegram", "telegram_chat_id": 456, "verified": False},
    ]
    connection = FakeConnection(fetch_result=rows)
    service = MessagingIdentityService(FakePool(connection))

    assert await service.get_mappings_for_user("user-1") == rows
    assert connection.fetch_calls[0][1] == ("user-1",)
