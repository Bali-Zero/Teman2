"""
Unit tests for app/main_cloud.py
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main_cloud import (
    _allowed_origins,
    _parse_history,
    _safe_endpoint_label,
    app,
    on_shutdown,
    on_startup,
)


class TestMainCloud:
    """Tests for main_cloud.py"""

    def test_app_exists(self):
        """Test that app instance exists"""
        assert app is not None

    @pytest.mark.asyncio
    async def test_on_startup(self):
        """Test startup handler"""
        with patch("app.main_cloud.initialize_services") as mock_init_services, \
             patch("app.main_cloud.initialize_plugins") as mock_init_plugins, \
             patch("app.main_cloud.AlertService") as mock_alert:
            mock_init_services.return_value = None
            mock_init_plugins.return_value = None

            await on_startup()

            mock_init_services.assert_called_once()
            mock_init_plugins.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_shutdown(self):
        """Test shutdown handler"""
        # Mock app.state attributes
        app.state.redis_listener_task = None
        app.state.health_monitor = None
        app.state.compliance_monitor = None
        app.state.autonomous_scheduler = None

        await on_shutdown()
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_on_shutdown_with_redis_task(self):
        """Test shutdown with Redis task"""
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()

        app.state.redis_listener_task = mock_task
        app.state.health_monitor = None
        app.state.compliance_monitor = None
        app.state.autonomous_scheduler = None

        await on_shutdown()
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_shutdown_with_health_monitor(self):
        """Test shutdown with health monitor"""
        mock_monitor = AsyncMock()
        mock_monitor.stop = AsyncMock()

        app.state.redis_listener_task = None
        app.state.health_monitor = mock_monitor
        app.state.compliance_monitor = None
        app.state.autonomous_scheduler = None

        await on_shutdown()
        mock_monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_shutdown_with_compliance_monitor(self):
        """Test shutdown with compliance monitor"""
        mock_monitor = AsyncMock()
        mock_monitor.stop = AsyncMock()

        app.state.redis_listener_task = None
        app.state.health_monitor = None
        app.state.compliance_monitor = mock_monitor
        app.state.autonomous_scheduler = None

        await on_shutdown()
        mock_monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_shutdown_with_scheduler(self):
        """Test shutdown with autonomous scheduler"""
        mock_scheduler = AsyncMock()
        mock_scheduler.stop = AsyncMock()

        app.state.redis_listener_task = None
        app.state.health_monitor = None
        app.state.compliance_monitor = None
        app.state.autonomous_scheduler = mock_scheduler

        await on_shutdown()
        mock_scheduler.stop.assert_called_once()

    def test_parse_history_valid_json(self):
        """Test parsing valid JSON history"""
        history = '[{"role": "user", "content": "test"}]'
        result = _parse_history(history)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_parse_history_empty(self):
        """Test parsing empty history"""
        assert _parse_history(None) == []
        assert _parse_history("") == []

    def test_parse_history_invalid_json(self):
        """Test parsing invalid JSON"""
        result = _parse_history("invalid json")
        assert result == []

    def test_parse_history_not_list(self):
        """Test parsing JSON that's not a list"""
        result = _parse_history('{"not": "a list"}')
        assert result == []

    def test_allowed_origins(self):
        """Test getting allowed origins"""
        origins = _allowed_origins()
        assert isinstance(origins, list)

    def test_safe_endpoint_label_with_url(self):
        """Test safe endpoint label with URL"""
        label = _safe_endpoint_label("https://example.com/path")
        assert label == "example.com"

    def test_safe_endpoint_label_with_path(self):
        """Test safe endpoint label with path only"""
        label = _safe_endpoint_label("/api/test")
        assert label == "/api/test"

    def test_safe_endpoint_label_none(self):
        """Test safe endpoint label with None"""
        label = _safe_endpoint_label(None)
        assert label == "unknown"

    def test_safe_endpoint_label_empty(self):
        """Test safe endpoint label with empty string"""
        label = _safe_endpoint_label("")
        assert label == "unknown"




