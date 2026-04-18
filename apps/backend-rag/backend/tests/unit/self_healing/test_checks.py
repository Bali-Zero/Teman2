"""
Unit tests for individual health checks (system, http_api, cache, db).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.self_healing.checks.cache import CacheCheck
from backend.self_healing.checks.db import DBCheck
from backend.self_healing.checks.http_api import HTTPAPICheck
from backend.self_healing.checks.system import CPUCheck, DiskCheck, MemoryCheck


class TestSystemChecks:
    @pytest.mark.asyncio
    async def test_cpu_healthy_below_threshold(self):
        with patch("backend.self_healing.checks.system.psutil.cpu_percent", return_value=45.0):
            result = await CPUCheck(threshold_percent=90.0).run()
        assert result.healthy is True
        assert result.detail["cpu_percent"] == 45.0

    @pytest.mark.asyncio
    async def test_cpu_unhealthy_above_threshold(self):
        with patch("backend.self_healing.checks.system.psutil.cpu_percent", return_value=95.0):
            result = await CPUCheck(threshold_percent=90.0).run()
        assert result.healthy is False
        assert "95.0%" in (result.error or "")

    @pytest.mark.asyncio
    async def test_cpu_handles_psutil_raises(self):
        with patch(
            "backend.self_healing.checks.system.psutil.cpu_percent",
            side_effect=RuntimeError("no sensor"),
        ):
            result = await CPUCheck().run()
        assert result.healthy is False
        assert "RuntimeError" in (result.error or "")

    @pytest.mark.asyncio
    async def test_memory_healthy_and_unhealthy(self):
        mem_healthy = MagicMock()
        mem_healthy.percent = 30.0
        mem_unhealthy = MagicMock()
        mem_unhealthy.percent = 95.0

        with patch(
            "backend.self_healing.checks.system.psutil.virtual_memory",
            return_value=mem_healthy,
        ):
            assert (await MemoryCheck().run()).healthy

        with patch(
            "backend.self_healing.checks.system.psutil.virtual_memory",
            return_value=mem_unhealthy,
        ):
            assert not (await MemoryCheck().run()).healthy

    @pytest.mark.asyncio
    async def test_disk_handles_psutil_raises(self):
        with patch(
            "backend.self_healing.checks.system.psutil.disk_usage",
            side_effect=OSError("no mount"),
        ):
            result = await DiskCheck().run()
        assert result.healthy is False

    @pytest.mark.asyncio
    async def test_disk_detail_includes_path(self):
        usage = MagicMock()
        usage.percent = 50.0
        with patch(
            "backend.self_healing.checks.system.psutil.disk_usage", return_value=usage,
        ):
            result = await DiskCheck(path="/data").run()
        assert result.detail["path"] == "/data"
        assert result.detail["disk_percent"] == 50.0


class TestHTTPAPICheck:
    @pytest.mark.asyncio
    async def test_returns_healthy_on_200(self):
        client = MagicMock()
        response = MagicMock()
        response.status_code = 200
        client.get = AsyncMock(return_value=response)

        result = await HTTPAPICheck("http://svc/health", client=client).run()
        assert result.healthy is True
        assert result.detail["status_code"] == 200

    @pytest.mark.asyncio
    async def test_returns_unhealthy_on_non_200(self):
        client = MagicMock()
        response = MagicMock()
        response.status_code = 503
        client.get = AsyncMock(return_value=response)

        result = await HTTPAPICheck("http://svc/health", client=client).run()
        assert result.healthy is False
        assert "503" in (result.error or "")

    @pytest.mark.asyncio
    async def test_returns_unhealthy_on_httpx_exception(self):
        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        result = await HTTPAPICheck("http://svc/health", client=client).run()
        assert result.healthy is False
        assert "ConnectError" in (result.error or "")


class TestCacheCheck:
    @pytest.mark.asyncio
    async def test_no_client_configured_is_healthy(self):
        result = await CacheCheck(redis_client=None).run()
        assert result.healthy is True
        assert result.detail["configured"] is False

    @pytest.mark.asyncio
    async def test_ping_success(self):
        client = MagicMock()
        client.ping = MagicMock(return_value=True)
        result = await CacheCheck(redis_client=client).run()
        assert result.healthy is True

    @pytest.mark.asyncio
    async def test_ping_raises(self):
        client = MagicMock()
        client.ping = MagicMock(side_effect=ConnectionError("unreachable"))
        result = await CacheCheck(redis_client=client).run()
        assert result.healthy is False
        assert "ConnectionError" in (result.error or "")


class TestDBCheck:
    @pytest.mark.asyncio
    async def test_no_probe_is_healthy(self):
        result = await DBCheck(connect_callable=None).run()
        assert result.healthy is True
        assert result.detail["probe"] == "not_configured"

    @pytest.mark.asyncio
    async def test_probe_success(self):
        probe = AsyncMock(return_value=None)
        result = await DBCheck(connect_callable=probe).run()
        assert result.healthy is True
        assert probe.await_count == 1

    @pytest.mark.asyncio
    async def test_probe_raises(self):
        probe = AsyncMock(side_effect=TimeoutError("slow pool"))
        result = await DBCheck(connect_callable=probe).run()
        assert result.healthy is False
        assert "TimeoutError" in (result.error or "")
