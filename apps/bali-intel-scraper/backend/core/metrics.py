"""
Prometheus metrics collection.

Tracks key performance indicators for monitoring.
"""

import time
from contextlib import contextmanager
from typing import Any

from backend.core.logger import get_logger

logger = get_logger(__name__, component="metrics")


class MetricsCollector:
    """Collect and expose metrics."""

    def __init__(self, prefix: str = "bali_intel"):
        self.prefix = prefix
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list] = {}
        self._timers: dict[str, list] = {}

    def increment(
        self, name: str, value: int = 1, tags: dict[str, str] | None = None
    ):
        """Increment a counter metric."""
        full_name = self._format_name(name, tags)
        self._counters[full_name] = self._counters.get(full_name, 0) + value

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None):
        """Set a gauge metric."""
        full_name = self._format_name(name, tags)
        self._gauges[full_name] = value

    def timing(self, name: str, seconds: float, tags: dict[str, str] | None = None):
        """Record a timing metric."""
        full_name = self._format_name(name, tags)
        if full_name not in self._timers:
            self._timers[full_name] = []
        self._timers[full_name].append(seconds)

        # Keep only last 1000 measurements
        if len(self._timers[full_name]) > 1000:
            self._timers[full_name] = self._timers[full_name][-1000:]

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None):
        """Record a histogram metric."""
        full_name = self._format_name(name, tags)
        if full_name not in self._histograms:
            self._histograms[full_name] = []
        self._histograms[full_name].append(value)

    def _format_name(self, name: str, tags: dict[str, str] | None) -> str:
        """Format metric name with tags."""
        full_name = f"{self.prefix}_{name}"
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            full_name = f"{full_name}{{{tag_str}}}"
        return full_name

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all current metrics."""
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "timers": {
                name: {
                    "count": len(values),
                    "avg": sum(values) / len(values) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                }
                for name, values in self._timers.items()
            },
        }

    @contextmanager
    def timer(self, name: str, tags: dict[str, str] | None = None):
        """Context manager for timing operations."""
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            self.timing(name, elapsed, tags)


# Global collector
metrics = MetricsCollector()


def get_metrics() -> dict[str, Any]:
    """Get all metrics."""
    return metrics.get_all_metrics()


__all__ = [
    "MetricsCollector",
    "metrics",
    "get_metrics",
]
