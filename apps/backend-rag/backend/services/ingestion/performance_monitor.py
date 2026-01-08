"""
Advanced Performance Monitoring Service
Provides comprehensive monitoring, alerting, and optimization for ingestion services
"""

import asyncio
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .ingestion_logger import ingestion_logger

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Performance metric data point"""

    timestamp: datetime
    metric_name: str
    value: float
    labels: dict[str, str]
    threshold: float | None = None
    unit: str = "seconds"


@dataclass
class Alert:
    """Performance alert"""

    id: str
    severity: AlertSeverity
    metric_name: str
    current_value: float
    threshold: float
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: datetime | None = None


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation"""

    category: str
    priority: str
    description: str
    expected_improvement: str
    implementation_effort: str
    metrics_impacted: list[str]


class PerformanceMonitor:
    """
    Advanced performance monitoring and optimization service

    Features:
    - Real-time performance tracking
    - Automatic alerting on threshold breaches
    - Performance trend analysis
    - Optimization recommendations
    - Resource utilization monitoring
    """

    def __init__(self):
        self.metrics_history: list[PerformanceMetric] = []
        self.active_alerts: dict[str, Alert] = {}
        self.performance_thresholds: dict[str, dict[str, float]] = self._initialize_thresholds()
        self.optimization_rules: list[dict[str, Any]] = self._initialize_optimization_rules()

        logger.info("PerformanceMonitor initialized")

    def _initialize_thresholds(self) -> dict[str, dict[str, float]]:
        """Initialize performance thresholds for monitoring"""
        return {
            "parsing_duration": {
                "warning": 5.0,  # 5 seconds
                "critical": 15.0,  # 15 seconds
                "unit": "seconds",
            },
            "document_processing_duration": {
                "warning": 30.0,  # 30 seconds
                "critical": 120.0,  # 2 minutes
                "unit": "seconds",
            },
            "ingestion_failure_rate": {
                "warning": 0.05,  # 5% failure rate
                "critical": 0.15,  # 15% failure rate
                "unit": "percentage",
            },
            "chunking_duration": {
                "warning": 10.0,  # 10 seconds
                "critical": 30.0,  # 30 seconds
                "unit": "seconds",
            },
            "embedding_generation_duration": {
                "warning": 20.0,  # 20 seconds
                "critical": 60.0,  # 1 minute
                "unit": "seconds",
            },
            "vector_storage_duration": {
                "warning": 5.0,  # 5 seconds
                "critical": 15.0,  # 15 seconds
                "unit": "seconds",
            },
        }

    def _initialize_optimization_rules(self) -> list[dict[str, Any]]:
        """Initialize optimization rule engine"""
        return [
            {
                "name": "High Parsing Time",
                "condition": lambda metrics: self._get_avg_metric(metrics, "parsing_duration")
                > 5.0,
                "recommendation": OptimizationRecommendation(
                    category="Parsing Performance",
                    priority="HIGH",
                    description="Consider implementing document preprocessing or using faster parsing libraries",
                    expected_improvement="20-40% faster parsing",
                    implementation_effort="Medium",
                    metrics_impacted=["parsing_duration", "document_processing_duration"],
                ),
            },
            {
                "name": "High Failure Rate",
                "condition": lambda metrics: self._get_avg_metric(metrics, "ingestion_failure_rate")
                > 0.05,
                "recommendation": OptimizationRecommendation(
                    category="Reliability",
                    priority="CRITICAL",
                    description="Implement better error handling and input validation",
                    expected_improvement="50-80% reduction in failures",
                    implementation_effort="Low",
                    metrics_impacted=["ingestion_failure_rate"],
                ),
            },
            {
                "name": "Slow Embedding Generation",
                "condition": lambda metrics: self._get_avg_metric(
                    metrics, "embedding_generation_duration"
                )
                > 20.0,
                "recommendation": OptimizationRecommendation(
                    category="ML Performance",
                    priority="MEDIUM",
                    description="Consider batch processing or model optimization",
                    expected_improvement="15-30% faster embeddings",
                    implementation_effort="High",
                    metrics_impacted=["embedding_generation_duration"],
                ),
            },
        ]

    async def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous performance monitoring"""
        logger.info(f"Starting performance monitoring with {interval_seconds}s interval")

        while True:
            try:
                await self._collect_metrics()
                await self._analyze_performance()
                await self._check_alerts()
                await self._generate_recommendations()

                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)

    async def _collect_metrics(self):
        """Collect current performance metrics"""
        current_time = datetime.now()

        # Simulate collecting metrics from Prometheus
        metrics_to_collect = [
            "parsing_duration",
            "document_processing_duration",
            "ingestion_failure_rate",
            "chunking_duration",
            "embedding_generation_duration",
            "vector_storage_duration",
        ]

        for metric_name in metrics_to_collect:
            # In real implementation, this would query Prometheus
            # For now, we'll simulate with random values
            import random

            base_value = {
                "parsing_duration": 2.0,
                "document_processing_duration": 15.0,
                "ingestion_failure_rate": 0.02,
                "chunking_duration": 5.0,
                "embedding_generation_duration": 10.0,
                "vector_storage_duration": 3.0,
            }.get(metric_name, 1.0)

            value = base_value * (0.5 + random.random())

            metric = PerformanceMetric(
                timestamp=current_time,
                metric_name=metric_name,
                value=value,
                labels={"service": "ingestion"},
                threshold=self.performance_thresholds.get(metric_name, {}).get("warning"),
                unit=self.performance_thresholds.get(metric_name, {}).get("unit", "seconds"),
            )

            self.metrics_history.append(metric)

        # Keep only last 1000 data points
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

    async def _analyze_performance(self):
        """Analyze performance trends and patterns"""
        if len(self.metrics_history) < 10:
            return

        current_time = datetime.now()
        recent_metrics = [
            m for m in self.metrics_history if current_time - m.timestamp < timedelta(minutes=5)
        ]

        if not recent_metrics:
            return

        # Analyze each metric
        for metric_name in set(m.metric_name for m in recent_metrics):
            metric_values = [m.value for m in recent_metrics if m.metric_name == metric_name]

            if len(metric_values) < 3:
                continue

            # Calculate statistics
            avg_value = statistics.mean(metric_values)
            std_dev = statistics.stdev(metric_values) if len(metric_values) > 1 else 0

            # Detect anomalies (values > 2 std dev from mean)
            threshold = avg_value + 2 * std_dev
            anomalies = [v for v in metric_values if v > threshold]

            if anomalies:
                await self._create_anomaly_alert(metric_name, avg_value, anomalies)

    async def _check_alerts(self):
        """Check for threshold breaches and create alerts"""
        current_time = datetime.now()
        recent_metrics = [
            m for m in self.metrics_history if current_time - m.timestamp < timedelta(minutes=1)
        ]

        for metric in recent_metrics:
            thresholds = self.performance_thresholds.get(metric.metric_name, {})

            if not thresholds:
                continue

            # Check critical threshold
            critical_threshold = thresholds.get("critical")
            if critical_threshold and metric.value > critical_threshold:
                await self._create_alert(
                    metric.metric_name, metric.value, critical_threshold, AlertSeverity.CRITICAL
                )
            # Check warning threshold
            elif thresholds.get("warning") and metric.value > thresholds["warning"]:
                await self._create_alert(
                    metric.metric_name, metric.value, thresholds["warning"], AlertSeverity.MEDIUM
                )

    async def _create_alert(
        self, metric_name: str, current_value: float, threshold: float, severity: AlertSeverity
    ):
        """Create a performance alert"""
        alert_id = f"{metric_name}_{int(time.time())}"

        if alert_id in self.active_alerts:
            return  # Alert already exists

        alert = Alert(
            id=alert_id,
            severity=severity,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
            message=f"{metric_name} exceeded threshold: {current_value:.2f} > {threshold:.2f}",
            timestamp=datetime.now(),
        )

        self.active_alerts[alert_id] = alert

        # Log the alert
        logger.warning(f"Performance Alert: {alert.message}")

        # Send to structured logging
        ingestion_logger.performance_alert(
            document_id="system_monitor",
            alert_id=alert_id,
            severity=severity.value,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
        )

    async def _create_anomaly_alert(
        self, metric_name: str, avg_value: float, anomalies: list[float]
    ):
        """Create anomaly detection alert"""
        alert_id = f"anomaly_{metric_name}_{int(time.time())}"

        alert = Alert(
            id=alert_id,
            severity=AlertSeverity.MEDIUM,
            metric_name=metric_name,
            current_value=max(anomalies),
            threshold=avg_value,
            message=f"Anomaly detected in {metric_name}: {len(anomalies)} anomalous values",
            timestamp=datetime.now(),
        )

        self.active_alerts[alert_id] = alert
        logger.warning(f"Anomaly Alert: {alert.message}")

    async def _generate_recommendations(self):
        """Generate performance optimization recommendations"""
        recent_metrics = [
            m for m in self.metrics_history if datetime.now() - m.timestamp < timedelta(hours=1)
        ]

        recommendations = []

        for rule in self.optimization_rules:
            if rule["condition"](recent_metrics):
                recommendations.append(rule["recommendation"])

        if recommendations:
            await self._log_recommendations(recommendations)

    async def _log_recommendations(self, recommendations: list[OptimizationRecommendation]):
        """Log optimization recommendations"""
        for rec in recommendations:
            logger.info(f"Optimization Recommendation: {rec.description}")

            ingestion_logger.optimization_recommendation(
                document_id="system_optimizer",
                category=rec.category,
                priority=rec.priority,
                description=rec.description,
                expected_improvement=rec.expected_improvement,
            )

    def get_performance_summary(self) -> dict[str, Any]:
        """Get comprehensive performance summary"""
        if not self.metrics_history:
            return {"status": "No data available"}

        current_time = datetime.now()
        recent_metrics = [
            m for m in self.metrics_history if current_time - m.timestamp < timedelta(hours=1)
        ]

        summary = {
            "monitoring_status": "active",
            "metrics_collected": len(self.metrics_history),
            "active_alerts": len(self.active_alerts),
            "recent_metrics": len(recent_metrics),
            "performance_by_metric": {},
        }

        # Calculate performance for each metric
        for metric_name in set(m.metric_name for m in recent_metrics):
            values = [m.value for m in recent_metrics if m.metric_name == metric_name]

            if values:
                summary["performance_by_metric"][metric_name] = {
                    "current": values[-1] if values else 0,
                    "average": statistics.mean(values),
                    "min": min(values),
                    "max": max(values),
                    "trend": "improving"
                    if len(values) > 1 and values[-1] < values[0]
                    else "degrading",
                }

        return summary

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get list of active alerts"""
        return [asdict(alert) for alert in self.active_alerts.values()]

    def resolve_alert(self, alert_id: str):
        """Resolve an active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now()
            del self.active_alerts[alert_id]

            logger.info(f"Alert resolved: {alert_id}")
            return True
        return False

    def _get_avg_metric(self, metrics: list[PerformanceMetric], metric_name: str) -> float:
        """Get average value for a specific metric"""
        values = [m.value for m in metrics if m.metric_name == metric_name]
        return statistics.mean(values) if values else 0.0


# Global performance monitor instance
performance_monitor = PerformanceMonitor()
