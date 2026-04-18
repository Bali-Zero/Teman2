"""
Unit tests for remediation actions (gc, reconnect_cache, restart_service).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.self_healing.actions.gc import GCAction
from backend.self_healing.actions.reconnect_cache import ReconnectCacheAction
from backend.self_healing.actions.restart_service import RestartServiceAction


class TestGCAction:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("backend.self_healing.actions.gc.gc.collect", return_value=42):
            result = await GCAction().run()
        assert result.success
        assert "42" in (result.detail or "")

    @pytest.mark.asyncio
    async def test_collect_raises(self):
        with patch(
            "backend.self_healing.actions.gc.gc.collect",
            side_effect=MemoryError("OOM"),
        ):
            result = await GCAction().run()
        assert result.success is False
        assert "MemoryError" in (result.error or "")


class TestReconnectCacheAction:
    @pytest.mark.asyncio
    async def test_no_url_returns_failure(self):
        result = await ReconnectCacheAction(redis_url=None).run()
        assert result.success is False
        assert "not configured" in (result.error or "")

    @pytest.mark.asyncio
    async def test_reconnect_success(self):
        fake_client = MagicMock()
        fake_client.ping = MagicMock(return_value=True)
        with patch(
            "backend.self_healing.actions.reconnect_cache.redis.from_url",
            return_value=fake_client,
        ):
            action = ReconnectCacheAction(redis_url="redis://localhost:6379/0")
            result = await action.run()
        assert result.success is True
        assert action.redis_client is fake_client

    @pytest.mark.asyncio
    async def test_reconnect_ping_fails(self):
        fake_client = MagicMock()
        fake_client.ping = MagicMock(side_effect=ConnectionError("refused"))
        with patch(
            "backend.self_healing.actions.reconnect_cache.redis.from_url",
            return_value=fake_client,
        ):
            result = await ReconnectCacheAction(redis_url="redis://nowhere/0").run()
        assert result.success is False
        assert "ConnectionError" in (result.error or "")


class TestRestartServiceAction:
    @pytest.mark.asyncio
    async def test_returns_manual_escalation(self):
        result = await RestartServiceAction().run()
        # By design: never auto-kill the process — escalate instead.
        assert result.success is False
        assert "manual" in (result.detail or "")
