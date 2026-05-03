"""Tests for backend.services.ingestion.performance_monitor"""

from __future__ import annotations

import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.ingestion.performance_monitor import (
    Alert,
    AlertSeverity,
    OptimizationRecommendation,
    PerformanceMetric,
    PerformanceMonitor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def monitor() -> PerformanceMonitor:
    """Fresh PerformanceMonitor with empty state."""
    return PerformanceMonitor()


def _make_metric(
    name: str = "parsing_duration",
    value: float = 2.0,
    age_seconds: int = 0,
) -> PerformanceMetric:
    ts = datetime.now(tz=timezone.utc) - timedelta(seconds=age_seconds)
    return PerformanceMetric(
        timestamp=ts,
        metric_name=name,
        value=value,
        labels={"service": "ingestion"},
        threshold=5.0,
        unit="seconds",
    )


# ---------------------------------------------------------------------------
# Dataclass / Enum tests
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_alert_severity_values(self) -> None:
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_performance_metric_defaults(self) -> None:
        m = _make_metric()
        assert m.unit == "seconds"
        assert m.metric_name == "parsing_duration"

    def test_alert_defaults(self) -> None:
        a = Alert(
            id="test_1",
            severity=AlertSeverity.HIGH,
            metric_name="parsing_duration",
            current_value=10.0,
            threshold=5.0,
            message="exceeded",
            timestamp=datetime.now(tz=timezone.utc),
        )
        assert a.resolved is False
        assert a.resolved_at is None

    def test_optimization_recommendation_fields(self) -> None:
        rec = OptimizationRecommendation(
            category="Parsing",
            priority="HIGH",
            description="Optimize parsing",
            expected_improvement="20%",
            implementation_effort="Low",
            metrics_impacted=["parsing_duration"],
        )
        assert rec.category == "Parsing"
        assert "parsing_duration" in rec.metrics_impacted


# ---------------------------------------------------------------------------
# PerformanceMonitor.__init__ and thresholds
# ---------------------------------------------------------------------------

class TestInit:
    def test_initial_state(self, monitor: PerformanceMonitor) -> None:
        assert monitor.metrics_history == []
        assert monitor.active_alerts == {}

    def test_thresholds_initialized(self, monitor: PerformanceMonitor) -> None:
        thresholds = monitor.performance_thresholds
        assert "parsing_duration" in thresholds
        assert "document_processing_duration" in thresholds
        assert "ingestion_failure_rate" in thresholds
        assert thresholds["parsing_duration"]["warning"] == 5.0
        assert thresholds["parsing_duration"]["critical"] == 15.0

    def test_optimization_rules_initialized(self, monitor: PerformanceMonitor) -> None:
        assert len(monitor.optimization_rules) == 3
        assert monitor.optimization_rules[0]["name"] == "High Parsing Time"


# ---------------------------------------------------------------------------
# _get_avg_metric
# ---------------------------------------------------------------------------

class TestGetAvgMetric:
    def test_avg_with_values(self, monitor: PerformanceMonitor) -> None:
        metrics = [
            _make_metric("parsing_duration", 2.0),
            _make_metric("parsing_duration", 4.0),
            _make_metric("parsing_duration", 6.0),
        ]
        assert monitor._get_avg_metric(metrics, "parsing_duration") == pytest.approx(4.0)

    def test_avg_empty_returns_zero(self, monitor: PerformanceMonitor) -> None:
        assert monitor._get_avg_metric([], "parsing_duration") == 0.0

    def test_avg_no_matching_metric(self, monitor: PerformanceMonitor) -> None:
        metrics = [_make_metric("other_metric", 5.0)]
        assert monitor._get_avg_metric(metrics, "parsing_duration") == 0.0


# ---------------------------------------------------------------------------
# _collect_metrics
# ---------------------------------------------------------------------------

class TestCollectMetrics:
    @pytest.mark.asyncio
    async def test_collect_adds_metrics(self, monitor: PerformanceMonitor) -> None:
        assert len(monitor.metrics_history) == 0
        await monitor._collect_metrics()
        # 6 metric types collected per call
        assert len(monitor.metrics_history) == 6

    @pytest.mark.asyncio
    async def test_collect_trims_to_1000(self, monitor: PerformanceMonitor) -> None:
        # Pre-fill with 998 metrics
        monitor.metrics_history = [_make_metric() for _ in range(998)]
        await monitor._collect_metrics()  # adds 6 → 1004
        assert len(monitor.metrics_history) == 1000

    @pytest.mark.asyncio
    async def test_metric_labels(self, monitor: PerformanceMonitor) -> None:
        await monitor._collect_metrics()
        for m in monitor.metrics_history:
            assert m.labels == {"service": "ingestion"}


# ---------------------------------------------------------------------------
# _analyze_performance
# ---------------------------------------------------------------------------

class TestAnalyzePerformance:
    @pytest.mark.asyncio
    async def test_skips_when_insufficient_data(self, monitor: PerformanceMonitor) -> None:
        monitor.metrics_history = [_make_metric() for _ in range(5)]
        # Should not raise even with < 10 data points
        await monitor._analyze_performance()
        assert len(monitor.active_alerts) == 0

    @pytest.mark.asyncio
    async def test_detects_anomaly(self, monitor: PerformanceMonitor) -> None:
        now = datetime.now(tz=timezone.utc)
        # Create 10 normal values and 1 extreme outlier
        for i in range(10):
            monitor.metrics_history.append(
                PerformanceMetric(
                    timestamp=now - timedelta(seconds=i * 5),
                    metric_name="parsing_duration",
                    value=2.0,
                    labels={"service": "ingestion"},
                )
            )
        # Add extreme outlier
        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=now,
                metric_name="parsing_duration",
                value=100.0,
                labels={"service": "ingestion"},
            )
        )
        await monitor._analyze_performance()
        # Should have created an anomaly alert
        anomaly_alerts = [a for a in monitor.active_alerts.values() if "anomaly" in a.id]
        assert len(anomaly_alerts) >= 1


# ---------------------------------------------------------------------------
# _check_alerts
# ---------------------------------------------------------------------------

class TestCheckAlerts:
    @pytest.mark.asyncio
    @patch("backend.services.ingestion.performance_monitor.ingestion_logger")
    async def test_critical_alert_created(
        self, mock_logger: MagicMock, monitor: PerformanceMonitor,
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        # Value exceeds critical threshold (15.0)
        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=now,
                metric_name="parsing_duration",
                value=20.0,
                labels={"service": "ingestion"},
            )
        )
        await monitor._check_alerts()
        assert len(monitor.active_alerts) >= 1
        alert = list(monitor.active_alerts.values())[0]
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    @patch("backend.services.ingestion.performance_monitor.ingestion_logger")
    async def test_warning_alert_created(
        self, mock_logger: MagicMock, monitor: PerformanceMonitor,
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        # Value exceeds warning (5.0) but not critical (15.0)
        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=now,
                metric_name="parsing_duration",
                value=8.0,
                labels={"service": "ingestion"},
            )
        )
        await monitor._check_alerts()
        assert len(monitor.active_alerts) >= 1
        alert = list(monitor.active_alerts.values())[0]
        assert alert.severity == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_no_alert_below_threshold(self, monitor: PerformanceMonitor) -> None:
        now = datetime.now(tz=timezone.utc)
        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=now,
                metric_name="parsing_duration",
                value=1.0,
                labels={"service": "ingestion"},
            )
        )
        await monitor._check_alerts()
        assert len(monitor.active_alerts) == 0

    @pytest.mark.asyncio
    async def test_old_metrics_ignored(self, monitor: PerformanceMonitor) -> None:
        old = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
        monitor.metrics_history.append(
            PerformanceMetric(
                timestamp=old,
                metric_name="parsing_duration",
                value=20.0,
                labels={"service": "ingestion"},
            )
        )
        await monitor._check_alerts()
        assert len(monitor.active_alerts) == 0


# ---------------------------------------------------------------------------
# _create_alert
# ---------------------------------------------------------------------------

class TestCreateAlert:
    @pytest.mark.asyncio
    @patch("backend.services.ingestion.performance_monitor.ingestion_logger")
    async def test_create_alert_stores_and_logs(
        self, mock_logger: MagicMock, monitor: PerformanceMonitor,
    ) -> None:
        await monitor._create_alert("parsing_duration", 20.0, 15.0, AlertSeverity.CRITICAL)
        assert len(monitor.active_alerts) == 1
        alert = list(monitor.active_alerts.values())[0]
        assert alert.metric_name == "parsing_duration"
        assert alert.current_value == 20.0
        assert alert.threshold == 15.0
        mock_logger.performance_alert.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.services.ingestion.performance_monitor.ingestion_logger")
    async def test_duplicate_alert_id_skipped(
        self, mock_logger: MagicMock, monitor: PerformanceMonitor,
    ) -> None:
        # Create alert with known timestamp
        await monitor._create_alert("parsing_duration", 20.0, 15.0, AlertSeverity.CRITICAL)
        count_before = len(monitor.active_alerts)
        # Same metric + same second → same alert_id → skip
        await monitor._create_alert("parsing_duration", 25.0, 15.0, AlertSeverity.CRITICAL)
        assert len(monitor.active_alerts) == count_before


# ---------------------------------------------------------------------------
# _create_anomaly_alert
# ---------------------------------------------------------------------------

class TestCreateAnomalyAlert:
    @pytest.mark.asyncio
    async def test_anomaly_alert_created(self, monitor: PerformanceMonitor) -> None:
        await monitor._create_anomaly_alert("parsing_duration", 2.0, [10.0, 12.0])
        anomaly_alerts = [a for a in monitor.active_alerts.values() if "anomaly" in a.id]
        assert len(anomaly_alerts) == 1
        alert = anomaly_alerts[0]
        assert alert.severity == AlertSeverity.MEDIUM
        assert alert.current_value == 12.0  # max of anomalies


# ---------------------------------------------------------------------------
# _generate_recommendations / _log_recommendations
# ---------------------------------------------------------------------------

class TestGenerateRecommendations:
    @pytest.mark.asyncio
    @patch("backend.services.ingestion.performance_monitor.ingestion_logger")
    async def test_generates_when_rule_matches(
        self, mock_logger: MagicMock, monitor: PerformanceMonitor,
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        # Add metrics that trigger "High Parsing Time" rule (avg > 5.0)
        for _ in range(5):
            monitor.metrics_history.append(
                PerformanceMetric(
                    timestamp=now,
                    metric_name="parsing_duration",
                    value=10.0,
                    labels={"service": "ingestion"},
                )
            )
        await monitor._generate_recommendations()
        mock_logger.optimization_recommendation.assert_called()

    @pytest.mark.asyncio
    @patch("backend.services.ingestion.performance_monitor.ingestion_logger")
    async def test_no_recommendations_when_healthy(
        self, mock_logger: MagicMock, monitor: PerformanceMonitor,
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        for _ in range(5):
            monitor.metrics_history.append(
                PerformanceMetric(
                    timestamp=now,
                    metric_name="parsing_duration",
                    value=1.0,
                    labels={"service": "ingestion"},
                )
            )
        await monitor._generate_recommendations()
        mock_logger.optimization_recommendation.assert_not_called()


# ---------------------------------------------------------------------------
# get_performance_summary
# ---------------------------------------------------------------------------

class TestGetPerformanceSummary:
    def test_no_data(self, monitor: PerformanceMonitor) -> None:
        summary = monitor.get_performance_summary()
        assert summary == {"status": "No data available"}

    def test_with_recent_metrics(self, monitor: PerformanceMonitor) -> None:
        now = datetime.now(tz=timezone.utc)
        monitor.metrics_history = [
            PerformanceMetric(
                timestamp=now - timedelta(seconds=i),
                metric_name="parsing_duration",
                value=float(5 - i),
                labels={"service": "ingestion"},
            )
            for i in range(5)
        ]
        summary = monitor.get_performance_summary()
        assert summary["monitoring_status"] == "active"
        assert summary["metrics_collected"] == 5
        assert "parsing_duration" in summary["performance_by_metric"]
        pd = summary["performance_by_metric"]["parsing_duration"]
        assert pd["min"] == 1.0
        assert pd["max"] == 5.0

    def test_trend_improving(self, monitor: PerformanceMonitor) -> None:
        now = datetime.now(tz=timezone.utc)
        # First metric higher, last metric lower → improving
        monitor.metrics_history = [
            PerformanceMetric(
                timestamp=now - timedelta(seconds=10),
                metric_name="parsing_duration",
                value=10.0,
                labels={"service": "ingestion"},
            ),
            PerformanceMetric(
                timestamp=now,
                metric_name="parsing_duration",
                value=2.0,
                labels={"service": "ingestion"},
            ),
        ]
        summary = monitor.get_performance_summary()
        assert summary["performance_by_metric"]["parsing_duration"]["trend"] == "improving"

    def test_trend_degrading(self, monitor: PerformanceMonitor) -> None:
        now = datetime.now(tz=timezone.utc)
        monitor.metrics_history = [
            PerformanceMetric(
                timestamp=now - timedelta(seconds=10),
                metric_name="parsing_duration",
                value=2.0,
                labels={"service": "ingestion"},
            ),
            PerformanceMetric(
                timestamp=now,
                metric_name="parsing_duration",
                value=10.0,
                labels={"service": "ingestion"},
            ),
        ]
        summary = monitor.get_performance_summary()
        assert summary["performance_by_metric"]["parsing_duration"]["trend"] == "degrading"


# ---------------------------------------------------------------------------
# get_active_alerts / resolve_alert
# ---------------------------------------------------------------------------

class TestAlertManagement:
    def test_get_active_alerts_empty(self, monitor: PerformanceMonitor) -> None:
        assert monitor.get_active_alerts() == []

    def test_get_active_alerts_returns_dicts(self, monitor: PerformanceMonitor) -> None:
        alert = Alert(
            id="test_1",
            severity=AlertSeverity.HIGH,
            metric_name="parsing_duration",
            current_value=10.0,
            threshold=5.0,
            message="exceeded",
            timestamp=datetime.now(tz=timezone.utc),
        )
        monitor.active_alerts["test_1"] = alert
        result = monitor.get_active_alerts()
        assert len(result) == 1
        assert result[0]["id"] == "test_1"
        assert isinstance(result[0], dict)

    def test_resolve_existing_alert(self, monitor: PerformanceMonitor) -> None:
        alert = Alert(
            id="test_1",
            severity=AlertSeverity.HIGH,
            metric_name="parsing_duration",
            current_value=10.0,
            threshold=5.0,
            message="exceeded",
            timestamp=datetime.now(tz=timezone.utc),
        )
        monitor.active_alerts["test_1"] = alert
        result = monitor.resolve_alert("test_1")
        assert result is True
        assert "test_1" not in monitor.active_alerts

    def test_resolve_nonexistent_alert(self, monitor: PerformanceMonitor) -> None:
        result = monitor.resolve_alert("nonexistent")
        assert result is False
