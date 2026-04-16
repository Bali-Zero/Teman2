"""CellMetricsExporter — lightweight HTTP server for Prometheus scraping.

# Organo: cell-core L0 → produces HTTP /metrics endpoint → consumed by Prometheus scraper
# If fails: no metrics exposed, cell continues (graceful degradation)

Default port: 9102 (avoids 9090 Prometheus, 9100 node_exporter, 9101 cron_exporter).
"""
from __future__ import annotations

import logging
from typing import Any

from cell_core.observability._prom_compat import (
    CollectorRegistry,
    HAS_PROM,
    generate_latest,
    start_http_server,
)

logger = logging.getLogger("cell_core.observability")

DEFAULT_PORT = 9102


class CellMetricsExporter:
    """Manages Prometheus metrics HTTP exposure.

    Usage::

        registry = CollectorRegistry()
        metrics = PulseMetrics(registry=registry)
        exporter = CellMetricsExporter(registry=registry, port=9102)
        exporter.start()  # non-blocking background thread
    """

    def __init__(
        self,
        registry: CollectorRegistry | None = None,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._registry = registry
        self._port = port
        self._started = False

    def start(self) -> bool:
        """Start the HTTP metrics server in a background daemon thread.

        Returns True if started, False if prometheus_client is not available
        or server was already started.
        """
        if self._started:
            return False
        if not HAS_PROM:
            logger.info(
                "[observability] prometheus_client not installed — "
                "metrics exporter is a no-op"
            )
            return False

        try:
            kwargs: dict[str, Any] = {}
            if self._registry is not None:
                kwargs["registry"] = self._registry
            start_http_server(self._port, **kwargs)
            self._started = True
            logger.info(f"[observability] Prometheus metrics server on :{self._port}")
            return True
        except OSError as e:
            logger.warning(
                f"[observability] Failed to start metrics server on :{self._port}: {e}"
            )
            return False

    @property
    def is_running(self) -> bool:
        return self._started

    def scrape(self) -> bytes:
        """Generate metrics output (Prometheus text format).

        Useful for testing or embedding in other HTTP servers.
        """
        if self._registry is not None:
            return generate_latest(self._registry)
        return generate_latest()
