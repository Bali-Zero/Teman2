"""Cell-core observability — per-cell Prometheus metrics.

# Organo: cell-core L0 → produces Prometheus metrics → consumed by Prometheus scraper
# If fails: cell continues without metrics (graceful degradation via no-op stubs)
"""
from cell_core.observability._prom_compat import HAS_PROM
from cell_core.observability.pulse_metrics import PulseMetrics
from cell_core.observability.exporter import CellMetricsExporter
from cell_core.observability.cardinality import CardinalityGuard

__all__ = [
    "HAS_PROM",
    "PulseMetrics",
    "CellMetricsExporter",
    "CardinalityGuard",
]
