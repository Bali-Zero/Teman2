"""
Unit tests for metrics pusher
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.metrics_pusher import MetricsPusher


@pytest.fixture
def metrics_pusher():
    """Create MetricsPusher instance"""
    return MetricsPusher(
        remote_write_url="https://prometheus-prod-01-eu-west-0.grafana.net/api/prom/push",
        username="test-user",
        token="test-token",
        push_interval=15,
        service_name="test-service",
    )


class TestMetricsPusher:
    """Tests for MetricsPusher"""

    def test_init(self, metrics_pusher):
        """Test initialization"""
        assert (
            metrics_pusher.remote_write_url
            == "https://prometheus-prod-01-eu-west-0.grafana.net/api/prom/push"
        )
        assert metrics_pusher.username == "test-user"
        assert metrics_pusher.token == "test-token"
        assert metrics_pusher.push_interval == 15
        assert metrics_pusher.service_name == "test-service"
        assert metrics_pusher._running is False
        assert metrics_pusher._task is None
        assert metrics_pusher.auth_header.startswith("Basic ")

    def test_parse_prometheus_text_simple(self, metrics_pusher):
        """Test parsing simple Prometheus text"""
        text = "test_metric 123.45"
        metrics = metrics_pusher._parse_prometheus_text(text)
        assert len(metrics) == 1
        assert metrics[0]["name"] == "test_metric"
        assert metrics[0]["value"] == 123.45

    def test_parse_prometheus_text_with_labels(self, metrics_pusher):
        """Test parsing Prometheus text with labels"""
        text = 'test_metric{label1="value1",label2="value2"} 123.45'
        metrics = metrics_pusher._parse_prometheus_text(text)
        assert len(metrics) == 1
        assert metrics[0]["name"] == "test_metric"
        assert metrics[0]["labels"]["label1"] == "value1"
        assert metrics[0]["labels"]["label2"] == "value2"

    def test_parse_prometheus_text_comments(self, metrics_pusher):
        """Test parsing Prometheus text with comments"""
        text = "# This is a comment\ntest_metric 123.45\n# Another comment"
        metrics = metrics_pusher._parse_prometheus_text(text)
        assert len(metrics) == 1
        assert metrics[0]["name"] == "test_metric"

    def test_parse_prometheus_text_empty(self, metrics_pusher):
        """Test parsing empty Prometheus text"""
        metrics = metrics_pusher._parse_prometheus_text("")
        assert len(metrics) == 0

    def test_start(self, metrics_pusher):
        """Test starting metrics pusher"""
        with patch("app.services.metrics_pusher.asyncio.create_task") as mock_task:
            mock_task_instance = MagicMock()
            mock_task.return_value = mock_task_instance
            metrics_pusher.start()
            assert metrics_pusher._running is True
            assert metrics_pusher._task == mock_task_instance

    @pytest.mark.asyncio
    async def test_stop(self, metrics_pusher):
        """Test stopping metrics pusher"""
        import asyncio

        async def mock_task_coro():
            await asyncio.sleep(0.1)

        metrics_pusher._running = True
        mock_task = asyncio.create_task(mock_task_coro())
        metrics_pusher._task = mock_task

        await metrics_pusher.stop()
        assert metrics_pusher._running is False

    @pytest.mark.asyncio
    async def test_push_metrics(self, metrics_pusher):
        """Test pushing metrics"""
        with (
            patch.object(
                metrics_pusher, "_collect_metrics", return_value="test_metric 123.45"
            ) as mock_collect,
            patch("app.services.metrics_pusher.httpx.AsyncClient") as mock_client,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await metrics_pusher._push_metrics()

            assert result is True
            mock_collect.assert_called_once()
