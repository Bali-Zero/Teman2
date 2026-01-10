#!/usr/bin/env python3
"""
BALI INTEL SCRAPER - Metrics & Observability
=============================================

Centralized metrics collection, logging, and observability for the intel pipeline.

Features:
- Pipeline execution metrics
- Component latency tracking
- Error rate monitoring
- Prometheus-compatible metrics export
- Structured logging with context

Usage:
    from metrics import MetricsCollector, track_latency, increment_counter

    metrics = MetricsCollector()

    with track_latency(metrics, "llama_scoring"):
        result = await score_article(article)

    metrics.increment("articles_processed")
    metrics.export_prometheus()

Author: BaliZero Team
"""

import time
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from loguru import logger


# =============================================================================
# METRIC TYPES
# =============================================================================


@dataclass
class MetricValue:
    """Single metric value with timestamp"""
    name: str
    value: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class LatencyMetric:
    """Latency tracking metric"""
    name: str
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    success: bool = True
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineMetrics:
    """Aggregated pipeline execution metrics"""
    # Counters
    total_articles_input: int = 0
    total_articles_processed: int = 0
    total_articles_published: int = 0
    total_articles_rejected: int = 0
    total_errors: int = 0

    # Stage-specific counters
    dedup_filtered: int = 0
    llama_scored: int = 0
    llama_filtered: int = 0
    claude_validated: int = 0
    claude_approved: int = 0
    claude_rejected: int = 0
    enriched: int = 0
    images_generated: int = 0
    seo_optimized: int = 0
    pending_approval: int = 0
    pending_human_review: int = 0

    # Latencies (ms)
    avg_llama_latency_ms: float = 0.0
    avg_claude_latency_ms: float = 0.0
    avg_enrichment_latency_ms: float = 0.0
    avg_image_gen_latency_ms: float = 0.0
    avg_seo_latency_ms: float = 0.0
    total_pipeline_duration_ms: float = 0.0

    # Error rates
    llama_error_rate: float = 0.0
    claude_error_rate: float = 0.0
    enrichment_error_rate: float = 0.0
    image_gen_error_rate: float = 0.0

    # Timestamps
    started_at: str = ""
    completed_at: str = ""


# =============================================================================
# METRICS COLLECTOR
# =============================================================================


class MetricsCollector:
    """
    Thread-safe metrics collector for the intel pipeline.

    Tracks counters, gauges, and latencies with labels.
    Exports to Prometheus format and JSON.
    """

    def __init__(self, app_name: str = "bali_intel_scraper"):
        self.app_name = app_name
        self._lock = Lock()

        # Counters (monotonically increasing)
        self._counters: Dict[str, float] = {}

        # Gauges (can go up or down)
        self._gauges: Dict[str, float] = {}

        # Histograms for latency tracking
        self._latencies: Dict[str, List[float]] = {}

        # Error tracking
        self._errors: Dict[str, int] = {}

        # Pipeline-specific metrics
        self._pipeline_metrics = PipelineMetrics()

        # Timing
        self._start_time: Optional[float] = None

        logger.debug(f"MetricsCollector initialized for {app_name}")

    def start_pipeline(self):
        """Mark pipeline start time"""
        self._start_time = time.time()
        self._pipeline_metrics.started_at = datetime.now(timezone.utc).isoformat()
        logger.info("Pipeline metrics collection started")

    def end_pipeline(self):
        """Mark pipeline end and calculate totals"""
        if self._start_time:
            duration = (time.time() - self._start_time) * 1000
            self._pipeline_metrics.total_pipeline_duration_ms = duration
        self._pipeline_metrics.completed_at = datetime.now(timezone.utc).isoformat()
        self._calculate_averages()
        logger.info(f"Pipeline completed in {self._pipeline_metrics.total_pipeline_duration_ms:.0f}ms")

    # -------------------------------------------------------------------------
    # COUNTER OPERATIONS
    # -------------------------------------------------------------------------

    def increment(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter"""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value

        # Update pipeline-specific counters
        self._update_pipeline_counter(name, value)

    def _update_pipeline_counter(self, name: str, value: float):
        """Update pipeline-specific counter fields"""
        counter_mapping = {
            "articles_input": "total_articles_input",
            "articles_processed": "total_articles_processed",
            "articles_published": "total_articles_published",
            "articles_rejected": "total_articles_rejected",
            "errors": "total_errors",
            "dedup_filtered": "dedup_filtered",
            "llama_scored": "llama_scored",
            "llama_filtered": "llama_filtered",
            "claude_validated": "claude_validated",
            "claude_approved": "claude_approved",
            "claude_rejected": "claude_rejected",
            "enriched": "enriched",
            "images_generated": "images_generated",
            "seo_optimized": "seo_optimized",
            "pending_approval": "pending_approval",
            "pending_human_review": "pending_human_review",
        }
        if name in counter_mapping:
            attr = counter_mapping[name]
            current = getattr(self._pipeline_metrics, attr, 0)
            setattr(self._pipeline_metrics, attr, current + int(value))

    def get_counter(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get counter value"""
        key = self._make_key(name, labels)
        with self._lock:
            return self._counters.get(key, 0)

    # -------------------------------------------------------------------------
    # GAUGE OPERATIONS
    # -------------------------------------------------------------------------

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge value"""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get gauge value"""
        key = self._make_key(name, labels)
        with self._lock:
            return self._gauges.get(key, 0)

    # -------------------------------------------------------------------------
    # LATENCY TRACKING
    # -------------------------------------------------------------------------

    def record_latency(self, name: str, duration_ms: float, labels: Dict[str, str] = None):
        """Record a latency measurement"""
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._latencies:
                self._latencies[key] = []
            self._latencies[key].append(duration_ms)

    def get_latency_stats(self, name: str, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get latency statistics for a metric"""
        key = self._make_key(name, labels)
        with self._lock:
            values = self._latencies.get(key, [])
            if not values:
                return {"count": 0, "avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}

            sorted_vals = sorted(values)
            count = len(sorted_vals)
            return {
                "count": count,
                "avg": sum(sorted_vals) / count,
                "min": sorted_vals[0],
                "max": sorted_vals[-1],
                "p50": sorted_vals[int(count * 0.5)],
                "p95": sorted_vals[int(count * 0.95)] if count > 20 else sorted_vals[-1],
                "p99": sorted_vals[int(count * 0.99)] if count > 100 else sorted_vals[-1],
            }

    # -------------------------------------------------------------------------
    # ERROR TRACKING
    # -------------------------------------------------------------------------

    def record_error(self, component: str, error_type: str = "general"):
        """Record an error occurrence"""
        key = f"{component}:{error_type}"
        with self._lock:
            self._errors[key] = self._errors.get(key, 0) + 1
        self.increment("errors")
        logger.debug(f"Error recorded: {key}")

    def get_error_count(self, component: str, error_type: str = None) -> int:
        """Get error count for a component"""
        with self._lock:
            if error_type:
                return self._errors.get(f"{component}:{error_type}", 0)
            # Sum all errors for component
            return sum(v for k, v in self._errors.items() if k.startswith(f"{component}:"))

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create unique key for metric with labels"""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _calculate_averages(self):
        """Calculate average latencies for pipeline metrics"""
        latency_mapping = {
            "llama_scoring": "avg_llama_latency_ms",
            "claude_validation": "avg_claude_latency_ms",
            "enrichment": "avg_enrichment_latency_ms",
            "image_generation": "avg_image_gen_latency_ms",
            "seo_optimization": "avg_seo_latency_ms",
        }

        for metric_name, attr in latency_mapping.items():
            stats = self.get_latency_stats(metric_name)
            setattr(self._pipeline_metrics, attr, stats["avg"])

    # -------------------------------------------------------------------------
    # EXPORT METHODS
    # -------------------------------------------------------------------------

    def get_pipeline_metrics(self) -> PipelineMetrics:
        """Get current pipeline metrics"""
        return self._pipeline_metrics

    def to_dict(self) -> Dict[str, Any]:
        """Export all metrics as dictionary"""
        with self._lock:
            return {
                "app_name": self.app_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "latencies": {k: self.get_latency_stats(k) for k in self._latencies.keys()},
                "errors": dict(self._errors),
                "pipeline": asdict(self._pipeline_metrics),
            }

    def to_json(self, indent: int = 2) -> str:
        """Export metrics as JSON string"""
        return json.dumps(self.to_dict(), indent=indent)

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        prefix = self.app_name

        # Counters
        for key, value in self._counters.items():
            name = key.split("{")[0]
            labels = key[len(name):] if "{" in key else ""
            lines.append(f"# TYPE {prefix}_{name} counter")
            lines.append(f"{prefix}_{name}{labels} {value}")

        # Gauges
        for key, value in self._gauges.items():
            name = key.split("{")[0]
            labels = key[len(name):] if "{" in key else ""
            lines.append(f"# TYPE {prefix}_{name} gauge")
            lines.append(f"{prefix}_{name}{labels} {value}")

        # Latency histograms (simplified - just avg/count)
        for key in self._latencies.keys():
            stats = self.get_latency_stats(key)
            name = key.split("{")[0]
            lines.append(f"# TYPE {prefix}_{name}_duration_ms summary")
            lines.append(f'{prefix}_{name}_duration_ms_count {stats["count"]}')
            lines.append(f'{prefix}_{name}_duration_ms_avg {stats["avg"]:.2f}')
            lines.append(f'{prefix}_{name}_duration_ms_p95 {stats["p95"]:.2f}')

        return "\n".join(lines)

    def save_to_file(self, filepath: str = None):
        """Save metrics to JSON file"""
        if not filepath:
            filepath = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(self.to_json())
        logger.info(f"Metrics saved to {filepath}")

    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._latencies.clear()
            self._errors.clear()
            self._pipeline_metrics = PipelineMetrics()
            self._start_time = None
        logger.debug("Metrics reset")


# =============================================================================
# CONTEXT MANAGERS
# =============================================================================


@contextmanager
def track_latency(collector: MetricsCollector, name: str, labels: Dict[str, str] = None):
    """
    Context manager to track operation latency.

    Usage:
        with track_latency(metrics, "llama_scoring"):
            result = await score_article(article)
    """
    start = time.time()
    error_occurred = False
    try:
        yield
    except Exception as e:
        error_occurred = True
        collector.record_error(name)
        raise
    finally:
        duration_ms = (time.time() - start) * 1000
        collector.record_latency(name, duration_ms, labels)
        if not error_occurred:
            logger.debug(f"{name} completed in {duration_ms:.1f}ms")


# =============================================================================
# STRUCTURED LOGGING
# =============================================================================


class StructuredLogger:
    """
    Structured logging wrapper with context support.

    Adds consistent fields to all log messages.
    """

    def __init__(self, component: str, metrics: MetricsCollector = None):
        self.component = component
        self.metrics = metrics
        self._context: Dict[str, Any] = {}

    def set_context(self, **kwargs):
        """Set context fields for subsequent logs"""
        self._context.update(kwargs)

    def clear_context(self):
        """Clear context fields"""
        self._context.clear()

    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with context"""
        extra = {**self._context, **kwargs}
        if extra:
            extra_str = " | " + " ".join(f"{k}={v}" for k, v in extra.items())
            return f"[{self.component}] {message}{extra_str}"
        return f"[{self.component}] {message}"

    def debug(self, message: str, **kwargs):
        logger.debug(self._format_message(message, **kwargs))

    def info(self, message: str, **kwargs):
        logger.info(self._format_message(message, **kwargs))

    def warning(self, message: str, **kwargs):
        logger.warning(self._format_message(message, **kwargs))

    def error(self, message: str, error: Exception = None, **kwargs):
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_msg"] = str(error)[:100]
        logger.error(self._format_message(message, **kwargs))
        if self.metrics:
            self.metrics.record_error(self.component)

    def success(self, message: str, **kwargs):
        logger.success(self._format_message(message, **kwargs))


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================


# Global metrics collector instance
_global_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics


def reset_metrics():
    """Reset global metrics"""
    global _global_metrics
    if _global_metrics:
        _global_metrics.reset()


# =============================================================================
# CLI TEST
# =============================================================================


if __name__ == "__main__":
    # Demo metrics collection
    metrics = MetricsCollector()
    metrics.start_pipeline()

    # Simulate some operations
    metrics.increment("articles_input", 10)
    metrics.increment("articles_processed", 8)
    metrics.increment("articles_rejected", 2)

    # Simulate latencies
    import random
    for _ in range(5):
        metrics.record_latency("llama_scoring", random.uniform(100, 500))
        metrics.record_latency("claude_validation", random.uniform(500, 2000))

    # Record some errors
    metrics.record_error("llama", "timeout")
    metrics.record_error("claude", "rate_limit")

    metrics.end_pipeline()

    # Log metrics
    logger.info("=" * 60)
    logger.info("METRICS SUMMARY")
    logger.info("=" * 60)
    logger.info(metrics.to_json())

    logger.info("=" * 60)
    logger.info("PROMETHEUS FORMAT")
    logger.info("=" * 60)
    logger.info(metrics.export_prometheus())
