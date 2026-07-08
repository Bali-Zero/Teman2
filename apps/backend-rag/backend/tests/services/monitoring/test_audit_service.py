import json

import pytest

from backend.services.monitoring import audit_service as audit_module
from backend.services.monitoring.audit_service import AuditService


class FakeAcquire:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def __aenter__(self) -> object:
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self, conn: object | None = None) -> None:
        self.conn = conn or FakeConn()
        self.closed = False

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)

    async def close(self) -> None:
        self.closed = True


class FakeConn:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        if self.fail:
            raise RuntimeError("db down")
        self.executed.append((query, args))
        return "INSERT 0 1"


def test_get_audit_service_reuses_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit_module, "_audit_service", None)

    assert audit_module.get_audit_service() is audit_module.get_audit_service()


@pytest.mark.asyncio
async def test_connect_creates_pool_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pool = FakePool()

    async def fake_create_pool(*args: object, **kwargs: object) -> FakePool:
        return fake_pool

    monkeypatch.setattr(audit_module.asyncpg, "create_pool", fake_create_pool)
    service = AuditService(database_url="postgres://example")

    await service.connect()

    assert service.pool is fake_pool
    assert service.enabled is True


@pytest.mark.asyncio
async def test_connect_disables_service_on_pool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create_pool(*args: object, **kwargs: object) -> FakePool:
        raise RuntimeError("cannot connect")

    monkeypatch.setattr(audit_module.asyncpg, "create_pool", fake_create_pool)
    service = AuditService(database_url="postgres://example")

    await service.connect()

    assert service.pool is None
    assert service.enabled is False


@pytest.mark.asyncio
async def test_close_closes_pool() -> None:
    service = AuditService(database_url="postgres://example")
    service.pool = FakePool()

    await service.close()

    assert service.pool.closed is True


@pytest.mark.asyncio
async def test_log_auth_event_persists_serialized_metadata() -> None:
    conn = FakeConn()
    service = AuditService(database_url="postgres://example")
    service.pool = FakePool(conn)

    await service.log_auth_event(
        email="user@example.com",
        action="login",
        success=True,
        user_id="u-1",
        metadata={"ip_country": "ID"},
    )

    args = conn.executed[0][1]
    assert args[:3] == ("u-1", "user@example.com", "login")
    assert json.loads(args[7]) == {"ip_country": "ID"}


@pytest.mark.asyncio
async def test_log_system_event_persists_details_dict() -> None:
    conn = FakeConn()
    service = AuditService(database_url="postgres://example")
    service.pool = FakePool(conn)

    await service.log_system_event(
        event_type="data_access",
        action="read",
        user_id="u-1",
        resource_id="client-1",
        details={"field": "passport"},
    )

    args = conn.executed[0][1]
    assert args[:4] == ("data_access", "u-1", "client-1", "read")
    assert args[4] == {"field": "passport"}
