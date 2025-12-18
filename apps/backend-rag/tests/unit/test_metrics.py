"""
Unit tests for metrics.py
Tests observability and metrics collection
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestMetrics:
    """Unit tests for metrics module"""

    def test_metrics_module_imports(self):
        """Test that metrics module can be imported"""
        from app.metrics import MetricsCollector

        assert MetricsCollector is not None

    def test_metrics_collector_init(self):
        """Test MetricsCollector initialization"""
        from app.metrics import MetricsCollector

        collector = MetricsCollector()
        assert collector is not None

    def test_metrics_collector_update_session_count(self):
        """Test metrics collector update_session_count method"""
        from app.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.update_session_count(5)

        assert collector.session_count == 5

    def test_metrics_collector_update_system_metrics(self):
        """Test metrics collector update_system_metrics method"""
        from app.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.update_system_metrics()

        # Should update system metrics without error
        assert collector is not None
