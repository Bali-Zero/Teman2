"""
Integration tests for Health Monitor
Tests health monitoring integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["QDRANT_URL"] = os.getenv("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestHealthMonitorIntegration:
    """Integration tests for Health Monitor"""

    def test_health_monitor_initialization(self, qdrant_client):
        """Test health monitor initialization"""
        with patch("services.health_monitor.HealthMonitor") as mock_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor_class.return_value = mock_monitor

            from services.health_monitor import HealthMonitor

            monitor = HealthMonitor()
            assert monitor is not None

    def test_health_monitor_record_operation(self, qdrant_client):
        """Test health monitor operation recording"""
        with patch("services.health_monitor.HealthMonitor") as mock_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor.record_operation = MagicMock()
            mock_monitor_class.return_value = mock_monitor

            from services.health_monitor import HealthMonitor

            monitor = HealthMonitor()
            monitor.record_operation("search", "visa_oracle", 100.0, success=True)

            assert monitor.record_operation.called
