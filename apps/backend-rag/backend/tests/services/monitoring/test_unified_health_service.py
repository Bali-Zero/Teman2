import sys
import types

import pytest

from backend.services.monitoring import unified_health_service as health_module
from backend.services.monitoring.unified_health_service import (
    HealthCheckResult,
    SystemMetrics,
    UnifiedHealthService,
)


class FakeHttpClient:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.closed = False
        self.is_closed = False

    async def get(self, url: str, timeout: float) -> object:
        self.url = url
        self.timeout = timeout
        return types.SimpleNamespace(status_code=self.status_code)

    async def aclose(self) -> None:
        self.closed = True
        self.is_closed = True


class FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def ping(self) -> None:
        if self.fail:
            raise RuntimeError("redis down")


def test_get_unified_health_service_reuses_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "_unified_health_service", None)

    assert health_module.get_unified_health_service() is health_module.get_unified_health_service()


@pytest.mark.asyncio
async def test_initialize_registers_redis_component(monkeypatch: pytest.MonkeyPatch) -> None:
    registrations: list[tuple[str, str]] = []

    class FakeRedisManager:
        @classmethod
        def get_instance(cls) -> "FakeRedisManager":
            return cls()

        def get_sync_client(self) -> FakeRedis:
            return FakeRedis()

        def register_component(self, name: str, status: str) -> None:
            registrations.append((name, status))

    fake_module = types.SimpleNamespace(RedisManager=FakeRedisManager)
    monkeypatch.setitem(sys.modules, "backend.core.redis_manager", fake_module)
    service = UnifiedHealthService()

    await service.initialize()

    assert isinstance(service.http_client, health_module.httpx.AsyncClient)
    assert service.redis_client is not None
    assert registrations == [("health_service", "active")]

    await service.close()


@pytest.mark.asyncio
async def test_check_database_success_and_missing_url(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDbConn:
        async def execute(self, query: str) -> str:
            self.query = query
            return "SELECT 1"

        async def close(self) -> None:
            self.closed = True

    async def fake_connect(url: str) -> FakeDbConn:
        assert url == "postgres://example"
        return FakeDbConn()

    service = UnifiedHealthService()
    monkeypatch.setattr(health_module.settings, "database_url", "", raising=False)

    skipped = await service.check_database()

    assert skipped.status == "skipped"

    monkeypatch.setattr(health_module.settings, "database_url", "postgres://example", raising=False)
    monkeypatch.setattr(health_module.asyncpg, "connect", fake_connect)

    result = await service.check_database()

    assert result.status == "ok"
    assert result.name == "database"


@pytest.mark.asyncio
async def test_check_qdrant_uses_configured_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQdrantClient:
        def __init__(self, qdrant_url: str, collection_name: str) -> None:
            self.qdrant_url = qdrant_url
            self.collection_name = collection_name

    fake_module = types.SimpleNamespace(QdrantClient=FakeQdrantClient)
    monkeypatch.setitem(sys.modules, "backend.core.qdrant_db", fake_module)
    monkeypatch.setattr(health_module.settings, "qdrant_url", "http://qdrant", raising=False)

    result = await UnifiedHealthService().check_qdrant()

    assert result.status == "ok"
    assert result.metadata == {"collection": "visa_oracle"}


@pytest.mark.asyncio
async def test_check_redis_reports_ok_warning_or_skipped() -> None:
    service = UnifiedHealthService()

    service.redis_client = FakeRedis()
    assert (await service.check_redis()).status == "ok"

    service.redis_client = FakeRedis(fail=True)
    assert (await service.check_redis()).status == "warning"


@pytest.mark.asyncio
async def test_check_api_uses_existing_http_client() -> None:
    service = UnifiedHealthService()
    service.http_client = FakeHttpClient(status_code=503)

    result = await service.check_api("http://example/health")

    assert result.status == "warning"
    assert result.message == "API returned status 503"
    assert service.http_client.url == "http://example/health"


@pytest.mark.asyncio
async def test_check_crm_models_and_collection_manager_with_fake_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crm_models = types.SimpleNamespace(
        Client=object,
        Practice=object,
        PracticeType=object,
        Interaction=object,
    )

    class FakeCollectionManager:
        def list_collections(self) -> list[str]:
            return ["kbli", "tax"]

    ingestion_module = types.SimpleNamespace(CollectionManager=FakeCollectionManager)
    monkeypatch.setitem(sys.modules, "backend.app.modules.crm.models", crm_models)
    monkeypatch.setitem(
        sys.modules,
        "backend.services.ingestion.collection_manager",
        ingestion_module,
    )

    service = UnifiedHealthService()

    models = await service.check_crm_models()
    collections = await service.check_collection_manager()

    assert models.status == "ok"
    assert models.metadata == {"models": ["Client", "Practice", "PracticeType", "Interaction"]}
    assert collections.status == "ok"
    assert collections.metadata == {"collection_count": 2}


@pytest.mark.asyncio
async def test_get_system_metrics_uses_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module.psutil, "cpu_percent", lambda interval: 12.5)
    monkeypatch.setattr(
        health_module.psutil,
        "virtual_memory",
        lambda: types.SimpleNamespace(percent=33.3),
    )
    monkeypatch.setattr(
        health_module.psutil,
        "disk_usage",
        lambda path: types.SimpleNamespace(percent=44.4),
    )

    metrics = await UnifiedHealthService().get_system_metrics()

    assert metrics.cpu_usage == 12.5
    assert metrics.memory_usage == 33.3
    assert metrics.disk_usage == 44.4


@pytest.mark.asyncio
async def test_run_all_checks_aggregates_status_and_cache() -> None:
    service = UnifiedHealthService()
    calls = {"database": 0}

    async def check_database() -> HealthCheckResult:
        calls["database"] += 1
        return HealthCheckResult("database", "ok", "ok")

    service.check_database = check_database
    service.check_qdrant = lambda: _async_value(HealthCheckResult("qdrant", "warning", "slow"))
    service.check_redis = lambda: _async_value(HealthCheckResult("redis", "skipped", "none"))
    service.check_api = lambda: _async_value(HealthCheckResult("api", "ok", "ok"))
    service.check_crm_models = lambda: _async_value(HealthCheckResult("crm_models", "ok", "ok"))
    service.check_collection_manager = lambda: _async_value(
        HealthCheckResult("collection_manager", "ok", "ok")
    )
    service.get_system_metrics = lambda: _async_value(SystemMetrics(1, 2, 3, 4, 5))

    first = await service.run_all_checks(use_cache=True)
    second = await service.run_all_checks(use_cache=True)

    assert first["overall_status"] == "warning"
    assert second["overall_status"] == "warning"
    assert calls["database"] == 1


def test_format_report_includes_status_metrics_and_check_messages() -> None:
    report = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "overall_status": "warning",
        "system_metrics": {
            "cpu_usage": 1.0,
            "memory_usage": 2.0,
            "disk_usage": 3.0,
            "uptime": 4.0,
            "timestamp": 5.0,
        },
        "checks": {
            "API": {
                "status": "warning",
                "message": "API returned status 503",
                "latency_ms": 10.5,
            }
        },
    }

    formatted = UnifiedHealthService().format_report(report)

    assert "NUZANTARA HEALTH CHECK REPORT" in formatted
    assert "Overall Status: WARNING" in formatted
    assert "CPU: 1.0%" in formatted
    assert "API returned status 503" in formatted


async def _async_value(value: object) -> object:
    return value
