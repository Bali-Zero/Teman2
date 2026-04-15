"""metabolic — Metabolic metrics for SYMBIOSIS Pillar 7 (Measure).

Provides the 4 canonical metabolic metrics:
- M1 TTR (Time-to-Resolution): pulse cycles in degraded state
- M2 DO (Ontological Density): KG edges/nodes ratio
- M3 IA (Autonomy Index): endogenous/total action ratio
- M4 FE (Escalation Frequency): normalized escalation rate
"""
from cell_core.metabolic.definitions import (
    DIRECTION_HIGHER_BETTER,
    DIRECTION_LOWER_BETTER,
    METRIC_AUTONOMY_INDEX,
    METRIC_ESCALATION_FREQ,
    METRIC_ONTOLOGY_DENSITY,
    METRIC_TTR,
    MetabolicSnapshot,
    MetricValue,
)
from cell_core.metabolic.storage import MetabolicStore
from cell_core.metabolic.trend import TrendAnalyzer

__all__ = [
    "MetricValue",
    "MetabolicSnapshot",
    "MetabolicStore",
    "TrendAnalyzer",
    "METRIC_TTR",
    "METRIC_ONTOLOGY_DENSITY",
    "METRIC_AUTONOMY_INDEX",
    "METRIC_ESCALATION_FREQ",
    "DIRECTION_LOWER_BETTER",
    "DIRECTION_HIGHER_BETTER",
]
