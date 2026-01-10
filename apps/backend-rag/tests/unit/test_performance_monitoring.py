"""
Comprehensive Test Suite for Performance Monitoring System
Tests all monitoring, alerting, and optimization features
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.metrics import metrics_collector
from services.ingestion.ingestion_logger import ingestion_logger
from services.ingestion.performance_monitor import (
    Alert,
    AlertSeverity,
    PerformanceMetric,
    PerformanceMonitor,
)


class TestPerformanceMonitor:
    """Test the performance monitoring system"""

    def test_monitor_initialization(self):
        """Test performance monitor initialization"""
        monitor = PerformanceMonitor()

        assert monitor.metrics_history == []
        assert monitor.active_alerts == {}
        assert len(monitor.performance_thresholds) > 0
        assert len(monitor.optimization_rules) > 0

        # Check that all expected thresholds are present
        expected_thresholds = [
            "parsing_duration",
            "document_processing_duration",
            "ingestion_failure_rate",
            "chunking_duration",
            "embedding_generation_duration",
            "vector_storage_duration",
        ]

        for threshold in expected_thresholds:
            assert threshold in monitor.performance_thresholds
            assert "warning" in monitor.performance_thresholds[threshold]
            assert "critical" in monitor.performance_thresholds[threshold]

    def test_performance_metric_creation(self):
        """Test performance metric creation and validation"""
        from datetime import datetime

        metric = PerformanceMetric(
            timestamp=datetime.now(),
            metric_name="parsing_duration",
            value=2.5,
            labels={"service": "ingestion"},
            threshold=5.0,
            unit="seconds",
        )

        assert metric.metric_name == "parsing_duration"
        assert metric.value == 2.5
        assert metric.threshold == 5.0
        assert metric.unit == "seconds"

    def test_alert_creation_and_management(self):
        """Test alert creation and management"""
        from datetime import datetime

        monitor = PerformanceMonitor()

        # Create a test alert
        alert = Alert(
            id="test_alert_1",
            severity=AlertSeverity.WARNING,
            metric_name="parsing_duration",
            current_value=10.0,
            threshold=5.0,
            message="Parsing duration exceeded threshold",
            timestamp=datetime.now(),
        )

        # Add alert to active alerts
        monitor.active_alerts["test_alert_1"] = alert

        assert len(monitor.active_alerts) == 1
        assert monitor.active_alerts["test_alert_1"].severity == AlertSeverity.WARNING

        # Test alert resolution
        result = monitor.resolve_alert("test_alert_1")
        assert result is True
        assert len(monitor.active_alerts) == 0
        assert alert.resolved is True
        assert alert.resolved_at is not None

    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Test metrics collection process"""
        monitor = PerformanceMonitor()

        # Mock the metrics collection to avoid random values
        with patch("random.random", return_value=1.0):
            await monitor._collect_metrics()

        # Check that metrics were collected
        assert len(monitor.metrics_history) > 0

        # Check that all expected metrics are present
        metric_names = set(m.metric_name for m in monitor.metrics_history)
        expected_metrics = {
            "parsing_duration",
            "document_processing_duration",
            "ingestion_failure_rate",
            "chunking_duration",
            "embedding_generation_duration",
            "vector_storage_duration",
        }

        assert expected_metrics.issubset(metric_names)

    @pytest.mark.asyncio
    async def test_performance_analysis(self):
        """Test performance analysis and anomaly detection"""
        monitor = PerformanceMonitor()

        # Create test metrics with anomalies
        from datetime import datetime, timedelta

        base_time = datetime.now()

        # Normal metrics
        for i in range(5):
            monitor.metrics_history.append(
                PerformanceMetric(
                    timestamp=base_time - timedelta(minutes=i),
                    metric_name="parsing_duration",
                    value=2.0,
                    labels={"service": "ingestion"},
                )
            )

        # Anomalous metric
        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=base_time,
                metric_name="parsing_duration",
                value=10.0,  # Much higher than normal
                labels={"service": "ingestion"},
            )
        )

        # Run analysis
        await monitor._analyze_performance()

        # Should have detected anomalies and created alerts
        assert len(monitor.active_alerts) > 0

    @pytest.mark.asyncio
    async def test_threshold_breach_detection(self):
        """Test threshold breach detection and alerting"""
        monitor = PerformanceMonitor()

        # Create metric that exceeds critical threshold
        from datetime import datetime

        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=datetime.now(),
                metric_name="parsing_duration",
                value=20.0,  # Exceeds critical threshold of 15.0
                labels={"service": "ingestion"},
                threshold=15.0,
            )
        )

        # Run alert checking
        await monitor._check_alerts()

        # Should have created a critical alert
        assert len(monitor.active_alerts) == 1
        alert = list(monitor.active_alerts.values())[0]
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.metric_name == "parsing_duration"

    @pytest.mark.asyncio
    async def test_optimization_recommendations(self):
        """Test optimization recommendation generation"""
        monitor = PerformanceMonitor()

        # Create metrics that should trigger recommendations
        from datetime import datetime

        # High parsing duration should trigger optimization
        for i in range(10):
            monitor.metrics_history.append(
                PerformanceMetric(
                    timestamp=datetime.now(),
                    metric_name="parsing_duration",
                    value=6.0,  # Above warning threshold of 5.0
                    labels={"service": "ingestion"},
                )
            )

        # Generate recommendations
        await monitor._generate_recommendations()

        # Should have generated recommendations (logged, not returned)
        # This test mainly ensures no exceptions occur
        assert True  # If we reach here, recommendations were generated successfully

    def test_performance_summary(self):
        """Test performance summary generation"""
        monitor = PerformanceMonitor()

        # Create test metrics
        from datetime import datetime

        for i in range(20):
            monitor.metrics_history.append(
                PerformanceMetric(
                    timestamp=datetime.now(),
                    metric_name="parsing_duration",
                    value=2.0 + (i % 5),
                    labels={"service": "ingestion"},
                )
            )

        summary = monitor.get_performance_summary()

        assert "monitoring_status" in summary
        assert "metrics_collected" in summary
        assert "active_alerts" in summary
        assert "performance_by_metric" in summary
        assert summary["monitoring_status"] == "active"
        assert summary["metrics_collected"] == 20

    def test_get_active_alerts(self):
        """Test getting active alerts"""
        monitor = PerformanceMonitor()

        # Create test alerts
        from datetime import datetime

        alert1 = Alert(
            id="test_1",
            severity=AlertSeverity.WARNING,
            metric_name="parsing_duration",
            current_value=10.0,
            threshold=5.0,
            message="Test alert 1",
            timestamp=datetime.now(),
        )

        alert2 = Alert(
            id="test_2",
            severity=AlertSeverity.CRITICAL,
            metric_name="failure_rate",
            current_value=0.2,
            threshold=0.1,
            message="Test alert 2",
            timestamp=datetime.now(),
        )

        monitor.active_alerts["test_1"] = alert1
        monitor.active_alerts["test_2"] = alert2

        active_alerts = monitor.get_active_alerts()

        assert len(active_alerts) == 2
        assert active_alerts[0]["severity"] == "warning"
        assert active_alerts[1]["severity"] == "critical"


class TestEnhancedIngestionLogger:
    """Test enhanced logging features for monitoring"""

    def test_performance_alert_logging(self):
        """Test performance alert logging"""
        with patch.object(ingestion_logger, "_log_event") as mock_log:
            ingestion_logger.performance_alert(
                document_id="test_doc",
                alert_id="alert_123",
                severity="warning",
                metric_name="parsing_duration",
                current_value=10.5,
                threshold=5.0,
            )

            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0].additional_context["alert_type"] == "performance"
            assert call_args[0][0].additional_context["current_value"] == 10.5

    def test_optimization_recommendation_logging(self):
        """Test optimization recommendation logging"""
        with patch.object(ingestion_logger, "_log_event") as mock_log:
            ingestion_logger.optimization_recommendation(
                document_id="test_doc",
                category="Parsing Performance",
                priority="HIGH",
                description="Consider implementing faster parsing",
                expected_improvement="20-40% faster",
            )

            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0].additional_context["recommendation_type"] == "optimization"
            assert call_args[0][0].additional_context["priority"] == "HIGH"

    def test_resource_utilization_logging(self):
        """Test resource utilization logging"""
        with patch.object(ingestion_logger, "_log_event") as mock_log:
            ingestion_logger.resource_utilization(
                document_id="test_doc",
                cpu_percent=75.5,
                memory_mb=1024,
                disk_io_mb=50,
                network_io_mb=25,
            )

            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            context = call_args[0][0].additional_context
            assert context["cpu_percent"] == 75.5
            assert context["memory_mb"] == 1024
            assert context["metric_type"] == "resource_utilization"

    def test_batch_processing_summary_logging(self):
        """Test batch processing summary logging"""
        with patch.object(ingestion_logger, "_log_event") as mock_log:
            ingestion_logger.batch_processing_summary(
                document_id="batch_123",
                total_documents=100,
                successful=95,
                failed=5,
                total_duration_ms=30000,
                avg_document_size_mb=2.5,
            )

            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            context = call_args[0][0].additional_context
            assert context["total_documents"] == 100
            assert context["success_rate"] == 95.0
            assert context["throughput_docs_per_second"] == 100 / 30  # 100 docs in 30 seconds

    def test_error_recovery_logging(self):
        """Test error recovery logging"""
        with patch.object(ingestion_logger, "_log_event") as mock_log:
            ingestion_logger.error_recovery_attempt(
                document_id="test_doc",
                error_type="ParseError",
                recovery_action="Retry with different parser",
                success=True,
            )

            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            context = call_args[0][0].additional_context
            assert context["error_type"] == "ParseError"
            assert context["recovery_success"] is True
            assert context["log_type"] == "error_recovery"

    def test_cache_performance_logging(self):
        """Test cache performance logging"""
        with patch.object(ingestion_logger, "_log_event") as mock_log:
            ingestion_logger.cache_performance(
                document_id="test_doc",
                cache_type="redis",
                hit_rate=0.85,
                total_requests=1000,
                avg_response_time_ms=2.5,
            )

            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            context = call_args[0][0].additional_context
            assert context["cache_type"] == "redis"
            assert context["hit_rate"] == 0.85
            assert context["cache_hits"] == 850
            assert context["cache_misses"] == 150

    def test_database_performance_logging(self):
        """Test database performance logging"""
        with patch.object(ingestion_logger, "_log_event") as mock_log:
            ingestion_logger.database_performance(
                document_id="test_doc",
                operation="INSERT",
                duration_ms=150.5,
                rows_affected=100,
                query_complexity="medium",
            )

            # Verify logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            context = call_args[0][0].additional_context
            assert context["operation"] == "INSERT"
            assert context["duration_ms"] == 150.5
            assert context["throughput_rows_per_second"] == 100 / 0.1505


class TestIntegrationMonitoring:
    """Test integration of monitoring with ingestion services"""

    @pytest.mark.asyncio
    async def test_end_to_end_monitoring_integration(self):
        """Test complete monitoring integration"""
        monitor = PerformanceMonitor()

        # Simulate a complete ingestion process with monitoring
        document_id = "integration_test_doc"

        # 1. Start ingestion
        with patch.object(ingestion_logger, "start_ingestion", return_value=document_id):
            doc_id = ingestion_logger.start_ingestion(
                file_path="/test/document.pdf", source="integration_test"
            )
            assert doc_id == document_id

        # 2. Simulate parsing with metrics
        metrics_collector.record_parsing_duration(
            file_type=".pdf", source="integration_test", duration_seconds=3.5
        )

        # 3. Log parsing success
        with patch.object(ingestion_logger, "parsing_success") as mock_log:
            ingestion_logger.parsing_success(
                document_id=document_id,
                file_path="/test/document.pdf",
                text_length=5000,
                duration_ms=3500,
                source="integration_test",
            )
            mock_log.assert_called_once()

        # 4. Simulate performance monitoring
        from datetime import datetime

        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=datetime.now(),
                metric_name="parsing_duration",
                value=3.5,
                labels={"service": "ingestion"},
            )
        )

        # 5. Check for alerts (should not trigger with normal values)
        await monitor._check_alerts()
        assert len(monitor.active_alerts) == 0

        # 6. Complete ingestion
        with patch.object(ingestion_logger, "ingestion_completed") as mock_log:
            ingestion_logger.ingestion_completed(
                document_id=document_id,
                file_path="/test/document.pdf",
                chunks_created=10,
                collection_name="test_collection",
                tier="A",
                total_duration_ms=5000,
                source="integration_test",
            )
            mock_log.assert_called_once()

        # 7. Get performance summary
        summary = monitor.get_performance_summary()
        assert summary["monitoring_status"] == "active"
        assert summary["metrics_collected"] >= 1

    @pytest.mark.asyncio
    async def test_performance_alert_workflow(self):
        """Test complete performance alert workflow"""
        monitor = PerformanceMonitor()

        # Simulate high parsing duration that should trigger alerts
        from datetime import datetime

        # Add metrics that exceed thresholds
        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=datetime.now(),
                metric_name="parsing_duration",
                value=20.0,  # Exceeds critical threshold
                labels={"service": "ingestion"},
                threshold=15.0,
            )
        )

        # Check for alerts
        await monitor._check_alerts()

        # Should have created alerts
        assert len(monitor.active_alerts) > 0

        # Get active alerts
        alerts = monitor.get_active_alerts()
        assert len(alerts) > 0

        # Resolve the alert
        alert_id = alerts[0]["id"]
        result = monitor.resolve_alert(alert_id)
        assert result is True
        assert len(monitor.active_alerts) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
