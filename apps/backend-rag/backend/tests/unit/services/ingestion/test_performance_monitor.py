"""Tests for backend.services.ingestion.performance_monitor"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.services.ingestion import performance_monitor as perf_mon
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
        self,
        mock_logger: MagicMock,
        monitor: PerformanceMonitor,
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
        self,
        mock_logger: MagicMock,
        monitor: PerformanceMonitor,
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
        self,
        mock_logger: MagicMock,
        monitor: PerformanceMonitor,
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
        self,
        mock_logger: MagicMock,
        monitor: PerformanceMonitor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same metric inside the same second collides on `alert_id` and is skipped.

        The clock is FROZEN, and that is the whole point. `_create_alert` builds
        `f"{metric_name}_{int(time.time())}"`, so this test used to make two real calls
        and HOPE no second boundary fell between them; when one did, two alerts existed
        and it failed `assert 2 == 1`. That is the documented `P3 FLAKY` orphan scar, and
        it blocked the required pre-push gate on a loaded machine on 2026-08-02. Racing a
        wall clock is not a test of deduplication — pinning the clock is.
        """
        monkeypatch.setattr(perf_mon.time, "time", lambda: 1_700_000_000.0)

        await monitor._create_alert("parsing_duration", 20.0, 15.0, AlertSeverity.CRITICAL)
        count_before = len(monitor.active_alerts)
        alert_id = next(iter(monitor.active_alerts))

        await monitor._create_alert("parsing_duration", 25.0, 15.0, AlertSeverity.CRITICAL)

        assert len(monitor.active_alerts) == count_before
        # The count alone is VACUOUS and this is the whole reason the line below exists:
        # with the `if alert_id in self.active_alerts: return` guard deleted, the second
        # call re-assigns `active_alerts[alert_id]`, the dict does not grow, and a
        # count-only assertion still passes — it tests a property of dicts, not of the
        # de-duplicator. Mutation-verified 2026-08-02: removing the guard left the whole
        # class green until this assertion was added. "Skipped" means the FIRST alert
        # survives, so that is what gets asserted.
        assert monitor.active_alerts[alert_id].current_value == 20.0, (
            "the duplicate overwrote the original instead of being skipped"
        )

    @pytest.mark.asyncio
    @patch("backend.services.ingestion.performance_monitor.ingestion_logger")
    async def test_alerts_one_second_apart_are_both_kept(
        self,
        mock_logger: MagicMock,
        monitor: PerformanceMonitor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Innocence, which the guilt case above never had.

        With the clock frozen, a de-duplicator that skipped EVERYTHING would satisfy the
        test above — it asserts a count did not grow. This one advances the clock by one
        second and requires the count to grow, so only real per-second de-duplication
        passes both.
        """
        # A HOLDER the test advances, never an iterator of ticks: `_create_alert` is not
        # the only reader of this clock — Python's own `logging` calls `time.time()` for
        # every LogRecord, and `_create_alert` logs a warning. An iterator sized to the
        # number of alerts is exhausted by the first call (measured: `StopIteration`
        # surfacing as `RuntimeError: coroutine raised StopIteration`). A holder is
        # correct for any number of internal reads.
        now = {"t": 1_700_000_000.0}
        monkeypatch.setattr(perf_mon.time, "time", lambda: now["t"])

        await monitor._create_alert("parsing_duration", 20.0, 15.0, AlertSeverity.CRITICAL)
        count_before = len(monitor.active_alerts)
        now["t"] += 1.0
        await monitor._create_alert("parsing_duration", 25.0, 15.0, AlertSeverity.CRITICAL)
        assert len(monitor.active_alerts) == count_before + 1


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
        self,
        mock_logger: MagicMock,
        monitor: PerformanceMonitor,
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
        self,
        mock_logger: MagicMock,
        monitor: PerformanceMonitor,
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
