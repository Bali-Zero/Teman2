from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.services.ingestion import performance_monitor as monitor_module
from backend.services.ingestion.performance_monitor import (
    AlertSeverity,
    PerformanceMetric,
    PerformanceMonitor,
)


class FakeIngestionLogger:
    def __init__(self) -> None:
        self.alerts: list[dict[str, Any]] = []
        self.recommendations: list[dict[str, Any]] = []

    def performance_alert(self, **kwargs: Any) -> None:
        self.alerts.append(kwargs)

    def optimization_recommendation(self, **kwargs: Any) -> None:
        self.recommendations.append(kwargs)


@pytest.fixture
def fake_ingestion_logger(monkeypatch: pytest.MonkeyPatch) -> FakeIngestionLogger:
    fake = FakeIngestionLogger()
    monkeypatch.setattr(monitor_module, "ingestion_logger", fake)
    return fake


def metric(name: str, value: float, minutes_ago: int = 0) -> PerformanceMetric:
    return PerformanceMetric(
        timestamp=datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_ago),
        metric_name=name,
        value=value,
        labels={"service": "ingestion"},
        threshold=None,
        unit="seconds",
    )


def test_thresholds_rules_and_empty_summary_are_initialized() -> None:
    monitor = PerformanceMonitor()

    assert monitor.performance_thresholds["parsing_duration"]["warning"] == 5.0
    assert monitor.optimization_rules
    assert monitor.get_performance_summary() == {"status": "No data available"}


@pytest.mark.asyncio
async def test_collect_metrics_appends_expected_metrics_and_trims_history() -> None:
    monitor = PerformanceMonitor()
    monitor.metrics_history = [metric("old", 1.0, minutes_ago=10)] * 1000

    await monitor._collect_metrics()

    assert len(monitor.metrics_history) == 1000
    collected_names = {entry.metric_name for entry in monitor.metrics_history[-6:]}
    assert collected_names == set(monitor.performance_thresholds)


@pytest.mark.asyncio
async def test_create_alert_records_active_alert_and_structured_log(
    fake_ingestion_logger: FakeIngestionLogger,
) -> None:
    monitor = PerformanceMonitor()

    await monitor._create_alert(
        "parsing_duration",
        current_value=18.0,
        threshold=15.0,
        severity=AlertSeverity.CRITICAL,
    )

    alerts = monitor.get_active_alerts()
    assert len(alerts) == 1
    assert alerts[0]["metric_name"] == "parsing_duration"
    assert alerts[0]["severity"] == AlertSeverity.CRITICAL
    assert fake_ingestion_logger.alerts[0]["severity"] == "critical"
    assert fake_ingestion_logger.alerts[0]["current_value"] == 18.0


@pytest.mark.asyncio
async def test_check_alerts_uses_critical_before_warning(
    fake_ingestion_logger: FakeIngestionLogger,
) -> None:
    monitor = PerformanceMonitor()
    monitor.metrics_history = [
        metric("parsing_duration", 18.0),
        metric("vector_storage_duration", 6.0),
        metric("embedding_generation_duration", 1.0, minutes_ago=3),
    ]

    await monitor._check_alerts()

    severities = {alert["metric_name"]: alert["severity"] for alert in monitor.get_active_alerts()}
    assert severities["parsing_duration"] == AlertSeverity.CRITICAL
    assert severities["vector_storage_duration"] == AlertSeverity.MEDIUM
    assert "embedding_generation_duration" not in severities
    assert len(fake_ingestion_logger.alerts) == 2


@pytest.mark.asyncio
async def test_analyze_performance_creates_anomaly_alert_for_recent_spikes() -> None:
    monitor = PerformanceMonitor()
    now = datetime.now(tz=timezone.utc)
    monitor.metrics_history = [
        PerformanceMetric(now, "parsing_duration", value, {}, unit="seconds")
        for value in [1.0] * 20 + [10.0]
    ]
    monitor.metrics_history.extend(
        PerformanceMetric(now, "chunking_duration", value, {}, unit="seconds")
        for value in [2.0, 2.1, 2.2]
    )

    await monitor._analyze_performance()

    anomaly_alerts = [
        alert for alert in monitor.active_alerts.values() if alert.id.startswith("anomaly_")
    ]
    assert anomaly_alerts
    assert anomaly_alerts[0].metric_name == "parsing_duration"


@pytest.mark.asyncio
async def test_generate_recommendations_logs_triggered_rules(
    fake_ingestion_logger: FakeIngestionLogger,
) -> None:
    monitor = PerformanceMonitor()
    monitor.metrics_history = [
        metric("parsing_duration", 8.0),
        metric("ingestion_failure_rate", 0.08),
        metric("embedding_generation_duration", 25.0),
    ]

    await monitor._generate_recommendations()

    categories = {entry["category"] for entry in fake_ingestion_logger.recommendations}
    assert categories == {"Parsing Performance", "Reliability", "ML Performance"}


def test_performance_summary_groups_recent_metrics_and_trend() -> None:
    monitor = PerformanceMonitor()
    monitor.metrics_history = [
        metric("parsing_duration", 10.0),
        metric("parsing_duration", 6.0),
        metric("chunking_duration", 3.0),
        metric("vector_storage_duration", 99.0, minutes_ago=90),
    ]

    summary = monitor.get_performance_summary()

    assert summary["monitoring_status"] == "active"
    assert summary["metrics_collected"] == 4
    assert summary["recent_metrics"] == 3
    assert summary["performance_by_metric"]["parsing_duration"]["average"] == 8.0
    assert summary["performance_by_metric"]["parsing_duration"]["trend"] == "improving"
    assert "vector_storage_duration" not in summary["performance_by_metric"]


@pytest.mark.asyncio
async def test_resolve_alert_removes_active_alert() -> None:
    monitor = PerformanceMonitor()
    await monitor._create_alert(
        "chunking_duration",
        current_value=35.0,
        threshold=30.0,
        severity=AlertSeverity.CRITICAL,
    )
    alert_id = next(iter(monitor.active_alerts))

    assert monitor.resolve_alert(alert_id) is True
    assert monitor.get_active_alerts() == []
    assert monitor.resolve_alert(alert_id) is False


def test_get_avg_metric_returns_zero_when_metric_is_absent() -> None:
    monitor = PerformanceMonitor()

    assert monitor._get_avg_metric([metric("parsing_duration", 4.0)], "missing") == 0.0
    assert monitor._get_avg_metric(
        [metric("parsing_duration", 4.0), metric("parsing_duration", 6.0)],
        "parsing_duration",
    ) == 5.0
