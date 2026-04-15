"""Metabolic metric definitions — dataclasses, constants, formatters.

# Organo: cell-core (L0) metabolic module
# Produce: MetricValue, MetabolicSnapshot (consumed by storage, trend, rollup)
# Consuma: niente (pure data definitions)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

# ── Metric type identifiers ────────────────────────────────────────────────────

METRIC_TTR = "ttr"
METRIC_ONTOLOGY_DENSITY = "ontology_density"
METRIC_AUTONOMY_INDEX = "autonomy_index"
METRIC_ESCALATION_FREQ = "escalation_freq"

ALL_METRICS = (METRIC_TTR, METRIC_ONTOLOGY_DENSITY, METRIC_AUTONOMY_INDEX, METRIC_ESCALATION_FREQ)

# ── Trend direction ────────────────────────────────────────────────────────────

DIRECTION_LOWER_BETTER = "lower_better"   # TTR, FE
DIRECTION_HIGHER_BETTER = "higher_better"  # DO, IA

METRIC_DIRECTIONS: dict[str, str] = {
    METRIC_TTR: DIRECTION_LOWER_BETTER,
    METRIC_ONTOLOGY_DENSITY: DIRECTION_HIGHER_BETTER,
    METRIC_AUTONOMY_INDEX: DIRECTION_HIGHER_BETTER,
    METRIC_ESCALATION_FREQ: DIRECTION_LOWER_BETTER,
}

# ── EMA and trend constants ───────────────────────────────────────────────────

EMA_ALPHA = 0.1
TREND_THRESHOLD_PCT = 5.0  # >5% change = improving/degrading
MIN_SNAPSHOTS_FOR_TREND = 7

# ── Metric labels (human-readable) ────────────────────────────────────────────

METRIC_LABELS: dict[str, str] = {
    METRIC_TTR: "Time-to-Resolution",
    METRIC_ONTOLOGY_DENSITY: "Densita' Ontologica",
    METRIC_AUTONOMY_INDEX: "Indice Autonomia",
    METRIC_ESCALATION_FREQ: "Frequenza Escalation",
}

METRIC_UNITS: dict[str, str] = {
    METRIC_TTR: "pulses",
    METRIC_ONTOLOGY_DENSITY: "edges/node",
    METRIC_AUTONOMY_INDEX: "ratio",
    METRIC_ESCALATION_FREQ: "ratio",
}


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class MetricValue:
    """A single metric measurement."""
    metric_type: str
    value: float | None  # None when source unavailable (graceful degradation)
    calculated_at: str   # ISO 8601
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MetricValue:
        return cls(
            metric_type=d["metric_type"],
            value=d.get("value"),
            calculated_at=d["calculated_at"],
            metadata=d.get("metadata", {}),
        )

    @property
    def direction(self) -> str:
        return METRIC_DIRECTIONS.get(self.metric_type, DIRECTION_LOWER_BETTER)

    @property
    def label(self) -> str:
        return METRIC_LABELS.get(self.metric_type, self.metric_type)

    @property
    def unit(self) -> str:
        return METRIC_UNITS.get(self.metric_type, "")


@dataclass
class MetabolicSnapshot:
    """Complete snapshot of all 4 metabolic metrics at a point in time."""
    ttr: MetricValue
    ontology_density: MetricValue
    autonomy_index: MetricValue
    escalation_freq: MetricValue
    calculated_at: str = ""

    def __post_init__(self) -> None:
        if not self.calculated_at:
            self.calculated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "ttr": self.ttr.to_dict(),
            "ontology_density": self.ontology_density.to_dict(),
            "autonomy_index": self.autonomy_index.to_dict(),
            "escalation_freq": self.escalation_freq.to_dict(),
            "calculated_at": self.calculated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MetabolicSnapshot:
        return cls(
            ttr=MetricValue.from_dict(d["ttr"]),
            ontology_density=MetricValue.from_dict(d["ontology_density"]),
            autonomy_index=MetricValue.from_dict(d["autonomy_index"]),
            escalation_freq=MetricValue.from_dict(d["escalation_freq"]),
            calculated_at=d.get("calculated_at", ""),
        )

    def get_metric(self, metric_type: str) -> MetricValue | None:
        """Get a specific metric by type string."""
        mapping = {
            METRIC_TTR: self.ttr,
            METRIC_ONTOLOGY_DENSITY: self.ontology_density,
            METRIC_AUTONOMY_INDEX: self.autonomy_index,
            METRIC_ESCALATION_FREQ: self.escalation_freq,
        }
        return mapping.get(metric_type)

    def format_telegram(self, trends: dict[str, str] | None = None) -> str:
        """Format snapshot as Telegram-friendly text.

        Args:
            trends: Optional dict of {metric_type: "improving"|"stable"|"degrading"|"insufficient_data"}
        """
        trends = trends or {}
        lines = [
            f"=== METABOLIC REPORT ===",
            f"Date: {self.calculated_at[:10]}",
            "",
        ]

        for metric_type, metric in [
            (METRIC_TTR, self.ttr),
            (METRIC_ONTOLOGY_DENSITY, self.ontology_density),
            (METRIC_AUTONOMY_INDEX, self.autonomy_index),
            (METRIC_ESCALATION_FREQ, self.escalation_freq),
        ]:
            label = METRIC_LABELS[metric_type]
            unit = METRIC_UNITS[metric_type]
            trend_str = trends.get(metric_type, "")

            if metric.value is None:
                lines.append(f"M{list(ALL_METRICS).index(metric_type)+1} {label}: N/A")
            else:
                val_str = f"{metric.value:.2f}" if metric.value != 0 else "0.00"
                trend_arrow = ""
                if trend_str == "improving":
                    trend_arrow = " [+]"
                elif trend_str == "degrading":
                    trend_arrow = " [!]"
                elif trend_str == "stable":
                    trend_arrow = " [=]"
                lines.append(f"M{list(ALL_METRICS).index(metric_type)+1} {label}: {val_str} {unit}{trend_arrow}")

                # Add breakdown from metadata if available
                meta_detail = _format_meta_detail(metric_type, metric.metadata)
                if meta_detail:
                    lines.append(f"   {meta_detail}")

        # Trend summary
        if trends:
            improving = sum(1 for t in trends.values() if t == "improving")
            stable = sum(1 for t in trends.values() if t == "stable")
            degrading = sum(1 for t in trends.values() if t == "degrading")
            lines.append("")
            lines.append(f"Trend: {improving} improving, {stable} stable, {degrading} degrading")

        return "\n".join(lines)


def _format_meta_detail(metric_type: str, metadata: dict) -> str:
    """Extract one-line detail from metric metadata."""
    if metric_type == METRIC_TTR:
        ep = metadata.get("episodes_count", 0)
        if ep > 0:
            return f"({ep} episodes, max {metadata.get('max_episode_length', '?')} pulses)"
    elif metric_type == METRIC_ONTOLOGY_DENSITY:
        nodes = metadata.get("nodes")
        edges = metadata.get("edges")
        if nodes and edges:
            return f"({edges:,} edges / {nodes:,} nodes)"
    elif metric_type == METRIC_AUTONOMY_INDEX:
        endo = metadata.get("endogenous", {})
        exo = metadata.get("exogenous", {})
        total = sum(endo.values()) + sum(exo.values()) if isinstance(endo, dict) and isinstance(exo, dict) else 0
        if total > 0:
            return f"({sum(endo.values())} endogenous / {total} total)"
    elif metric_type == METRIC_ESCALATION_FREQ:
        raw = metadata.get("raw_count", 0)
        total = metadata.get("total_actions", 0)
        if total > 0:
            return f"({raw} escalations / {total} actions)"
    return ""
