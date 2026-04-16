"""PulseMetrics — per-cell Prometheus metrics for the cell-core lifecycle.

# Organo: cell-core L0 → produces Prometheus counters/gauges/histograms
#   → consumed by Prometheus scraper via CellMetricsExporter
# If fails: no-op stubs from _prom_compat ensure zero impact on cell operation

Tracks:
- Pulse lifecycle (duration, phase latency, outcome, action, thought tier)
- Homeostasis state (stress, energy, arousal)
- Genome effectiveness (active/silenced counts, confidence avg, tier, search hit rate)
- HGT throughput (publish, consume, reject, feedback)
- Trend anomalies (drift, flapping, sustained degraded)

Label cardinality: ~117 series for 3 cells — well under 500 guard.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from cell_core.observability._prom_compat import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    HAS_PROM,
)

logger = logging.getLogger("cell_core.observability")

# Histogram buckets tuned for cell-core workloads
_PULSE_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)
_PHASE_DURATION_BUCKETS = (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 30)

# Valid phase names (8 phases in PulseLoop.single_pulse)
PHASES = ("safety", "sense", "evaluate", "think", "act", "reflect", "dream", "mature")

# Valid pulse outcomes
OUTCOMES = ("green", "yellow", "red", "halted")


class PulseMetrics:
    """Prometheus metrics exporter for a single cell or shared across cells.

    Usage::

        metrics = PulseMetrics()
        pulse = PulseLoop(config, ..., metrics=metrics)

    All methods are safe to call even when prometheus_client is not installed
    (no-op stubs from _prom_compat handle everything silently).
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if registry is not None:
            kwargs["registry"] = registry

        # ── Pulse lifecycle ──────────────────────────────────────
        self.pulse_duration = Histogram(
            "cell_pulse_duration_seconds",
            "Total wall time for one complete pulse",
            ["cell"],
            buckets=_PULSE_DURATION_BUCKETS,
            **kwargs,
        )
        self.phase_duration = Histogram(
            "cell_pulse_phase_duration_seconds",
            "Duration of each phase within a pulse",
            ["cell", "phase"],
            buckets=_PHASE_DURATION_BUCKETS,
            **kwargs,
        )
        self.pulse_outcome = Counter(
            "cell_pulse_outcome",
            "Pulse outcomes by health status",
            ["cell", "outcome"],
            **kwargs,
        )
        self.pulse_action = Counter(
            "cell_pulse_action",
            "Pulses where an action was taken",
            ["cell"],
            **kwargs,
        )
        self.pulse_thought_tier = Counter(
            "cell_pulse_thought_tier",
            "Reasoning tier invocations",
            ["cell", "tier"],
            **kwargs,
        )
        self.pulse_total = Counter(
            "cell_pulse",
            "Total pulses executed",
            ["cell"],
            **kwargs,
        )
        self.pulse_last_timestamp = Gauge(
            "cell_pulse_last_timestamp",
            "Unix timestamp of last completed pulse (for NoPulse alert)",
            ["cell"],
            **kwargs,
        )

        # ── Homeostasis ──────────────────────────────────────────
        self.homeostasis_stress = Gauge(
            "cell_homeostasis_stress",
            "Current stress level (0.0-1.0)",
            ["cell"],
            **kwargs,
        )
        self.homeostasis_energy = Gauge(
            "cell_homeostasis_energy",
            "Current energy level (0.0-1.0)",
            ["cell"],
            **kwargs,
        )
        self.homeostasis_arousal = Gauge(
            "cell_homeostasis_arousal",
            "Current arousal level (0.0-1.0)",
            ["cell"],
            **kwargs,
        )

        # ── Genome ───────────────────────────────────────────────
        self.genome_active = Gauge(
            "cell_genome_active",
            "Number of active genome entries",
            ["cell"],
            **kwargs,
        )
        self.genome_silenced = Gauge(
            "cell_genome_silenced",
            "Number of silenced genome entries",
            ["cell"],
            **kwargs,
        )
        self.genome_confidence_avg = Gauge(
            "cell_genome_confidence_avg",
            "Average confidence by entry type",
            ["cell", "entry_type"],
            **kwargs,
        )
        self.genome_tier_count = Gauge(
            "cell_genome_tier_count",
            "Skill count by promotion tier",
            ["cell", "tier"],
            **kwargs,
        )
        self.genome_search = Counter(
            "cell_genome_search",
            "Genome FTS5 search calls",
            ["cell", "result"],
            **kwargs,
        )

        # ── HGT ──────────────────────────────────────────────────
        self.hgt_published = Counter(
            "cell_hgt_published",
            "Skills published to cell:skills stream",
            ["cell"],
            **kwargs,
        )
        self.hgt_consumed = Counter(
            "cell_hgt_consumed",
            "Skills consumed from cell:skills stream",
            ["cell"],
            **kwargs,
        )
        self.hgt_rejected = Counter(
            "cell_hgt_rejected",
            "Skills rejected by domain/confidence filter",
            ["cell"],
            **kwargs,
        )
        self.hgt_feedback = Counter(
            "cell_hgt_feedback",
            "Vertical feedback proposals",
            ["cell", "outcome"],
            **kwargs,
        )

        # ── Trend anomalies (binary 0/1 for alert rules) ────────
        self.trend_monotonic_drift = Gauge(
            "cell_trend_monotonic_drift",
            "1 if response time is monotonically drifting up",
            ["cell"],
            **kwargs,
        )
        self.trend_flapping = Gauge(
            "cell_trend_flapping",
            "1 if health status is flapping",
            ["cell"],
            **kwargs,
        )
        self.trend_sustained_degraded = Gauge(
            "cell_trend_sustained_degraded",
            "1 if cell is in sustained degraded state",
            ["cell"],
            **kwargs,
        )

    # ── Recording methods ────────────────────────────────────────

    def record_phase(self, cell: str, phase: str, duration_s: float) -> None:
        """Record the duration of a single phase within a pulse."""
        self.phase_duration.labels(cell=cell, phase=phase).observe(duration_s)

    def record_pulse(
        self,
        cell: str,
        health_status: str,
        total_duration_s: float,
        action_taken: str | None = None,
        thought_tier: int | None = None,
        halted: bool = False,
    ) -> None:
        """Record a completed pulse with all its metadata."""
        self.pulse_total.labels(cell=cell).inc()
        self.pulse_duration.labels(cell=cell).observe(total_duration_s)
        self.pulse_last_timestamp.labels(cell=cell).set(time.time())

        # Outcome
        if halted:
            outcome = "halted"
        else:
            outcome = health_status if health_status in OUTCOMES else "green"
        self.pulse_outcome.labels(cell=cell, outcome=outcome).inc()

        # Action
        if action_taken:
            self.pulse_action.labels(cell=cell).inc()

        # Thought tier
        if thought_tier is not None:
            self.pulse_thought_tier.labels(cell=cell, tier=str(thought_tier)).inc()

    def observe_homeostasis(self, cell: str, state: Any) -> None:
        """Update homeostasis gauges from a HomeostaticState object."""
        self.homeostasis_stress.labels(cell=cell).set(state.stress_level)
        self.homeostasis_energy.labels(cell=cell).set(state.energy_level)
        self.homeostasis_arousal.labels(cell=cell).set(state.arousal)

    def observe_trend(self, cell: str, trend: Any) -> None:
        """Update trend anomaly gauges from a TrendResult object."""
        self.trend_monotonic_drift.labels(cell=cell).set(
            1.0 if trend.monotonic_drift else 0.0
        )
        self.trend_flapping.labels(cell=cell).set(
            1.0 if trend.flapping else 0.0
        )
        self.trend_sustained_degraded.labels(cell=cell).set(
            1.0 if trend.sustained_degraded else 0.0
        )

    def observe_genome(self, cell: str, genome: Any) -> None:
        """Update genome gauges by calling genome.stats().

        Call this periodically (e.g., every 10 pulses) — genome stats
        are slow-changing and the SQLite queries are fast but unnecessary
        on every 60s tick.
        """
        try:
            stats = genome.stats(cell=cell)
        except Exception as e:
            logger.warning(f"[observability] genome.stats() failed: {e}")
            return

        self.genome_active.labels(cell=cell).set(stats.get("active", 0))
        self.genome_silenced.labels(cell=cell).set(stats.get("silenced", 0))

        for entry in stats.get("by_type", []):
            self.genome_confidence_avg.labels(
                cell=cell, entry_type=entry["type"]
            ).set(entry.get("avg_confidence", 0))

    def observe_genome_tiers(self, cell: str, genome: Any) -> None:
        """Update genome tier counts. Separate from observe_genome for flexibility."""
        try:
            conn = genome._get_conn()
            rows = conn.execute(
                "SELECT tier, COUNT(*) c FROM genome "
                "WHERE cell_origin = ? AND tier IS NOT NULL "
                "AND (valid_to IS NULL OR valid_to > date('now')) "
                "GROUP BY tier",
                (cell,),
            ).fetchall()
            for row in rows:
                self.genome_tier_count.labels(cell=cell, tier=row["tier"]).set(row["c"])
        except Exception as e:
            logger.warning(f"[observability] genome tier query failed: {e}")

    def record_genome_search(self, cell: str, hit: bool) -> None:
        """Record a genome.search() call result."""
        result = "hit" if hit else "miss"
        self.genome_search.labels(cell=cell, result=result).inc()

    def record_hgt_publish(self, cell: str) -> None:
        """Record a successful HGT skill publication."""
        self.hgt_published.labels(cell=cell).inc()

    def record_hgt_consume(self, cell: str, count: int) -> None:
        """Record HGT skill consumption."""
        self.hgt_consumed.labels(cell=cell).inc(count)

    def record_hgt_reject(self, cell: str) -> None:
        """Record an HGT skill rejection (domain/confidence filter)."""
        self.hgt_rejected.labels(cell=cell).inc()

    def record_hgt_feedback(self, cell: str, accepted: bool) -> None:
        """Record a vertical feedback proposal outcome."""
        outcome = "accepted" if accepted else "rejected"
        self.hgt_feedback.labels(cell=cell, outcome=outcome).inc()
