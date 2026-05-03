"""Prometheus compatibility layer — optional import with no-op stubs.

# Organo: cell-core L0 → produces Prometheus metric objects → consumed by PulseMetrics
# If fails: all metrics become no-ops, cell continues without observability (graceful degradation)

cell-core has zero hard dependencies by design. This module attempts to import
prometheus_client; when unavailable it provides stub classes that accept all
method calls and do nothing. Every observability module imports exclusively
from here, never directly from prometheus_client.

Install the real library via: ``pip install cell-core[metrics]``
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cell_core.observability")

try:
    from prometheus_client import (  # type: ignore[import-untyped]
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        start_http_server,
    )

    HAS_PROM = True
except ImportError:
    HAS_PROM = False

    class _NoOpMetric:
        """Stub metric that silently ignores all operations."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def labels(self, *args: Any, **kwargs: Any) -> "_NoOpMetric":
            return self

        def inc(self, amount: float = 1) -> None:
            pass

        def dec(self, amount: float = 1) -> None:
            pass

        def set(self, value: float) -> None:
            pass

        def observe(self, amount: float) -> None:
            pass

        def collect(self) -> list:
            return []

        def describe(self) -> list:
            return []

    # Type aliases so callers can use the same class names
    Counter = _NoOpMetric  # type: ignore[misc,assignment]
    Gauge = _NoOpMetric  # type: ignore[misc,assignment]
    Histogram = _NoOpMetric  # type: ignore[misc,assignment]

    class CollectorRegistry:  # type: ignore[no-redef]
        """Stub registry."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def collect(self) -> list:
            return []

    def generate_latest(registry: Any = None) -> bytes:  # type: ignore[misc]
        return b""

    def start_http_server(port: int, registry: Any = None) -> None:  # type: ignore[misc]
        logger.info(
            f"[observability] prometheus_client not installed — "
            f"metrics server on :{port} is a no-op"
        )


__all__ = [
    "HAS_PROM",
    "CollectorRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "generate_latest",
    "start_http_server",
]
