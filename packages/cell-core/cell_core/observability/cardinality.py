"""CardinalityGuard — runtime check for Prometheus label explosion.

# Organo: cell-core L0 → consumes CollectorRegistry → produces warnings
# If fails: warning logged, cell continues (graceful degradation)

Counts unique label combinations per metric family. Logs a warning if any
single metric exceeds MAX_SERIES. Call periodically (e.g., every 100 pulses).
"""
from __future__ import annotations

import logging
from typing import Any

from cell_core.observability._prom_compat import CollectorRegistry, HAS_PROM

logger = logging.getLogger("cell_core.observability")

MAX_SERIES: int = 500


class CardinalityGuard:
    """Checks that no metric family exceeds MAX_SERIES unique label combos."""

    def __init__(
        self,
        registry: CollectorRegistry | None = None,
        max_series: int = MAX_SERIES,
    ) -> None:
        self._registry = registry
        self._max_series = max_series

    def check(self) -> dict[str, int]:
        """Return a dict of {metric_name: series_count} for all families.

        Logs a warning for any metric exceeding the threshold.
        Returns empty dict when prometheus_client is not installed.
        """
        if not HAS_PROM or self._registry is None:
            return {}

        counts: dict[str, int] = {}
        violations: list[str] = []

        for metric_family in self._registry.collect():
            name = metric_family.name
            n_samples = len(metric_family.samples)
            counts[name] = n_samples

            if n_samples > self._max_series:
                violations.append(f"{name}={n_samples}")

        if violations:
            logger.warning(
                f"[observability] CARDINALITY VIOLATION — "
                f"metrics exceeding {self._max_series} series: "
                f"{', '.join(violations)}"
            )

        return counts

    def total_series(self) -> int:
        """Return total series count across all metrics."""
        return sum(self.check().values())

    def is_healthy(self) -> bool:
        """Return True if no metric exceeds the threshold."""
        counts = self.check()
        return all(v <= self._max_series for v in counts.values())
