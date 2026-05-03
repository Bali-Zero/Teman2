"""cell-core — Biological lifecycle engine for Nuzantara agents."""
from cell_core.genome import Genome
from cell_core.hgt import CANONICAL_DOMAINS, HGTConsumer, HGTPublisher, VerticalFeedback, validate_domain
from cell_core.homeostasis import HomeostaticController, TrendDetector, TrendResult
from cell_core.identity import SelfModel, SelfModelManager
from cell_core.lifecycle import Maturation
from cell_core.protocols import Actor, EpisodicStore, LTMStore, Sensor, STMStore, Thinker
from cell_core.pulse import PulseLoop
from cell_core.reasoner import ReasonerFramework, TierConfig
from cell_core.safety import DNAInterpreter, DNAIntegrityError, DNALoader, SafetyGate
from cell_core.metabolic import MetabolicSnapshot, MetabolicStore, MetricValue, TrendAnalyzer
from cell_core.observability import CardinalityGuard, CellMetricsExporter, PulseMetrics
from cell_core import observatory  # noqa: F401 — opt-in emit module
from cell_core.types import (
    CellConfig,
    DNAConfig,
    DNARule,
    Episode,
    HomeostaticState,
    LearnedRule,
    Phase,
    Proposal,
    PulseResult,
    SafetyCheckResult,
    SensorReading,
)

__all__ = [
    "Genome",
    "HGTPublisher", "HGTConsumer", "VerticalFeedback",
    "CANONICAL_DOMAINS", "validate_domain",
    "CellConfig", "DNAConfig", "DNARule", "Episode", "HomeostaticState",
    "LearnedRule", "Phase", "Proposal", "PulseResult", "SafetyCheckResult",
    "SensorReading",
    "Actor", "EpisodicStore", "LTMStore", "Sensor", "STMStore", "Thinker",
    "PulseLoop", "Maturation", "HomeostaticController", "TrendDetector", "TrendResult",
    "SafetyGate", "DNALoader", "DNAInterpreter", "DNAIntegrityError",
    "SelfModel", "SelfModelManager",
    "ReasonerFramework", "TierConfig",
    "MetabolicSnapshot", "MetabolicStore", "MetricValue", "TrendAnalyzer",
    "PulseMetrics", "CellMetricsExporter", "CardinalityGuard",
    "observatory",
]
