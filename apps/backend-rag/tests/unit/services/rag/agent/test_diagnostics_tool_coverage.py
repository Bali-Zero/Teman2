import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

services_pkg = types.ModuleType("services")
rag_pkg = types.ModuleType("services.rag")
rag_pkg.__path__ = []
agent_pkg = types.ModuleType("services.rag.agent")
agent_pkg.__path__ = []
structures_module = types.ModuleType("services.rag.agent.structures")


class BaseTool:
    pass


structures_module.BaseTool = BaseTool
sys.modules.update(
    {
        "services": services_pkg,
        "services.rag": rag_pkg,
        "services.rag.agent": agent_pkg,
        "services.rag.agent.structures": structures_module,
    }
)

module_path = (
    Path(__file__).resolve().parents[5]
    / "backend"
    / "services"
    / "rag"
    / "agent"
    / "diagnostics_tool.py"
)
spec = importlib.util.spec_from_file_location("services.rag.agent.diagnostics_tool", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
DiagnosticsTool = module.DiagnosticsTool


@pytest.mark.asyncio
async def test_execute_routes_checks(monkeypatch):
    tool = DiagnosticsTool()
    monkeypatch.setattr(tool, "_check_database", AsyncMock(return_value="db"))
    monkeypatch.setattr(tool, "_check_redis", AsyncMock(return_value="redis"))
    monkeypatch.setattr(tool, "_check_qdrant", AsyncMock(return_value="qdrant"))
    monkeypatch.setattr(tool, "_check_internet", AsyncMock(return_value="internet"))

    result = await tool.execute(check_type="redis")
    assert result == "redis"

    result_all = await tool.execute(check_type="all")
    assert "db" in result_all
    assert "redis" in result_all
    assert "qdrant" in result_all
    assert "internet" in result_all


@pytest.mark.asyncio
async def test_check_database_paths(monkeypatch):
    tool = DiagnosticsTool()
    monkeypatch.setattr(module, "settings", SimpleNamespace(database_url=""))
    assert await tool._check_database() == "❌ Database: URL not configured"

    conn = SimpleNamespace(fetchval=AsyncMock(return_value="PostgreSQL 15"), close=AsyncMock())
    monkeypatch.setattr(module, "settings", SimpleNamespace(database_url="postgres://test"))
    monkeypatch.setattr(module.asyncpg, "connect", AsyncMock(return_value=conn))
    result = await tool._check_database()
    assert result.startswith("✅ Database: Connected")

    monkeypatch.setattr(module.asyncpg, "connect", AsyncMock(side_effect=RuntimeError("boom")))
    result = await tool._check_database()
    assert "Connection failed - boom" in result


@pytest.mark.asyncio
async def test_check_redis_paths(monkeypatch):
    tool = DiagnosticsTool()
    monkeypatch.setattr(module, "settings", SimpleNamespace(redis_url=""))
    assert await tool._check_redis() == "❌ Redis: URL not configured"

    redis_client = SimpleNamespace(ping=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr(module, "settings", SimpleNamespace(redis_url="redis://test"))
    monkeypatch.setattr(module.Redis, "from_url", lambda *_a, **_k: redis_client)
    result = await tool._check_redis()
    assert result == "✅ Redis: Connected & Ready"

    redis_client = SimpleNamespace(
        ping=AsyncMock(side_effect=RuntimeError("boom")), close=AsyncMock()
    )
    monkeypatch.setattr(module.Redis, "from_url", lambda *_a, **_k: redis_client)
    result = await tool._check_redis()
    assert "Connection failed - boom" in result


@pytest.mark.asyncio
async def test_check_qdrant_paths(monkeypatch):
    tool = DiagnosticsTool()
    monkeypatch.setattr(module, "settings", SimpleNamespace(qdrant_url="", qdrant_api_key=None))
    assert await tool._check_qdrant() == "❌ Qdrant: URL not configured"

    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "result": {
                    "collections": [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}]
                }
            }

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            return DummyResponse()

    monkeypatch.setattr(
        module, "settings", SimpleNamespace(qdrant_url="http://q", qdrant_api_key="k")
    )
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda timeout=5.0: DummyClient())
    result = await tool._check_qdrant()
    assert "Connected (4 collections" in result

    class ErrorResponse:
        status_code = 500
        text = "fail"

        def json(self):
            return {}

    class ErrorClient(DummyClient):
        async def get(self, url, headers=None):
            return ErrorResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda timeout=5.0: ErrorClient())
    result = await tool._check_qdrant()
    assert "Error 500 - fail" in result

    class BoomClient(DummyClient):
        async def get(self, url, headers=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda timeout=5.0: BoomClient())
    result = await tool._check_qdrant()
    assert "Connection failed - boom" in result


@pytest.mark.asyncio
async def test_check_internet_paths(monkeypatch):
    tool = DiagnosticsTool()

    class OkResponse:
        status_code = 200

    class OkClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            return OkResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda timeout=3.0: OkClient())
    result = await tool._check_internet()
    assert result == "✅ Internet: Connected"

    class WarnResponse:
        status_code = 503

    class WarnClient(OkClient):
        async def get(self, url):
            return WarnResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda timeout=3.0: WarnClient())
    result = await tool._check_internet()
    assert "Status 503" in result

    class BoomClient(OkClient):
        async def get(self, url):
            raise RuntimeError("boom")

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda timeout=3.0: BoomClient())
    result = await tool._check_internet()
    assert "Unreachable - boom" in result
