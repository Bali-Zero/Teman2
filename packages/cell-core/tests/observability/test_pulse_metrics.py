"""Tests for PulseMetrics — per-cell Prometheus metrics."""
from __future__ import annotations

import pytest

from cell_core.observability._prom_compat import HAS_PROM
from cell_core.observability.pulse_metrics import PulseMetrics, PHASES, OUTCOMES


# ── Skip if prometheus_client not installed ──────────────────────
pytestmark = pytest.mark.skipif(not HAS_PROM, reason="prometheus_client not installed")


@pytest.fixture
def registry():
    """Fresh isolated registry per test to avoid metric re-registration."""
    from prometheus_client import CollectorRegistry
    return CollectorRegistry()


@pytest.fixture
def metrics(registry):
    return PulseMetrics(registry=registry)


# ── record_pulse ─────────────────────────────────────────────────

class TestRecordPulse:
    def test_increments_total(self, metrics, registry):
        metrics.record_pulse("test_cell", "green", 0.5)
        value = _get_counter(registry, "cell_pulse_total", {"cell": "test_cell"})
        assert value == 1.0

    def test_observes_duration(self, metrics, registry):
        metrics.record_pulse("test_cell", "green", 1.5)
        # Histogram sum should reflect the observed value
        h_sum = _get_histogram_sum(registry, "cell_pulse_duration_seconds", {"cell": "test_cell"})
        assert h_sum == pytest.approx(1.5)

    def test_outcome_counter(self, metrics, registry):
        metrics.record_pulse("test_cell", "yellow", 0.1)
        value = _get_counter(registry, "cell_pulse_outcome_total", {"cell": "test_cell", "outcome": "yellow"})
        assert value == 1.0

    def test_halted_outcome(self, metrics, registry):
        metrics.record_pulse("test_cell", "green", 0.1, halted=True)
        value = _get_counter(registry, "cell_pulse_outcome_total", {"cell": "test_cell", "outcome": "halted"})
        assert value == 1.0

    def test_action_counter(self, metrics, registry):
        metrics.record_pulse("test_cell", "red", 0.1, action_taken="restart_service")
        value = _get_counter(registry, "cell_pulse_action_total", {"cell": "test_cell"})
        assert value == 1.0

    def test_no_action_no_increment(self, metrics, registry):
        metrics.record_pulse("test_cell", "green", 0.1)
        value = _get_counter(registry, "cell_pulse_action_total", {"cell": "test_cell"})
        assert value == 0.0

    def test_thought_tier(self, metrics, registry):
        metrics.record_pulse("test_cell", "red", 0.1, thought_tier=1)
        value = _get_counter(registry, "cell_pulse_thought_tier_total", {"cell": "test_cell", "tier": "1"})
        assert value == 1.0

    def test_last_timestamp_set(self, metrics, registry):
        metrics.record_pulse("test_cell", "green", 0.1)
        ts = _get_gauge(registry, "cell_pulse_last_timestamp", {"cell": "test_cell"})
        assert ts > 0


# ── record_phase ─────────────────────────────────────────────────

class TestRecordPhase:
    def test_all_phases_valid(self, metrics, registry):
        for phase in PHASES:
            metrics.record_phase("test_cell", phase, 0.01)
        # Should have 8 phase observations
        for phase in PHASES:
            h_sum = _get_histogram_sum(
                registry, "cell_pulse_phase_duration_seconds",
                {"cell": "test_cell", "phase": phase},
            )
            assert h_sum == pytest.approx(0.01)

    def test_accumulates_duration(self, metrics, registry):
        metrics.record_phase("test_cell", "sense", 0.1)
        metrics.record_phase("test_cell", "sense", 0.2)
        h_sum = _get_histogram_sum(
            registry, "cell_pulse_phase_duration_seconds",
            {"cell": "test_cell", "phase": "sense"},
        )
        assert h_sum == pytest.approx(0.3)


# ── observe_homeostasis ──────────────────────────────────────────

class TestObserveHomeostasis:
    def test_sets_gauges(self, metrics, registry):
        class _FakeState:
            stress_level = 0.42
            energy_level = 0.88
            arousal = 0.55
        metrics.observe_homeostasis("test_cell", _FakeState())
        assert _get_gauge(registry, "cell_homeostasis_stress", {"cell": "test_cell"}) == pytest.approx(0.42)
        assert _get_gauge(registry, "cell_homeostasis_energy", {"cell": "test_cell"}) == pytest.approx(0.88)
        assert _get_gauge(registry, "cell_homeostasis_arousal", {"cell": "test_cell"}) == pytest.approx(0.55)


# ── observe_trend ────────────────────────────────────────────────

class TestObserveTrend:
    def test_sets_binary_gauges(self, metrics, registry):
        class _FakeTrend:
            monotonic_drift = True
            flapping = False
            sustained_degraded = True
        metrics.observe_trend("test_cell", _FakeTrend())
        assert _get_gauge(registry, "cell_trend_monotonic_drift", {"cell": "test_cell"}) == 1.0
        assert _get_gauge(registry, "cell_trend_flapping", {"cell": "test_cell"}) == 0.0
        assert _get_gauge(registry, "cell_trend_sustained_degraded", {"cell": "test_cell"}) == 1.0


# ── genome metrics ───────────────────────────────────────────────

class TestGenomeMetrics:
    def test_search_hit(self, metrics, registry):
        metrics.record_genome_search("test_cell", hit=True)
        assert _get_counter(registry, "cell_genome_search_total", {"cell": "test_cell", "result": "hit"}) == 1.0

    def test_search_miss(self, metrics, registry):
        metrics.record_genome_search("test_cell", hit=False)
        assert _get_counter(registry, "cell_genome_search_total", {"cell": "test_cell", "result": "miss"}) == 1.0


# ── HGT metrics ──────────────────────────────────────────────────

class TestHGTMetrics:
    def test_publish(self, metrics, registry):
        metrics.record_hgt_publish("test_cell")
        assert _get_counter(registry, "cell_hgt_published_total", {"cell": "test_cell"}) == 1.0

    def test_consume(self, metrics, registry):
        metrics.record_hgt_consume("test_cell", 3)
        assert _get_counter(registry, "cell_hgt_consumed_total", {"cell": "test_cell"}) == 3.0

    def test_reject(self, metrics, registry):
        metrics.record_hgt_reject("test_cell")
        assert _get_counter(registry, "cell_hgt_rejected_total", {"cell": "test_cell"}) == 1.0

    def test_feedback_accepted(self, metrics, registry):
        metrics.record_hgt_feedback("test_cell", accepted=True)
        assert _get_counter(registry, "cell_hgt_feedback_total", {"cell": "test_cell", "outcome": "accepted"}) == 1.0

    def test_feedback_rejected(self, metrics, registry):
        metrics.record_hgt_feedback("test_cell", accepted=False)
        assert _get_counter(registry, "cell_hgt_feedback_total", {"cell": "test_cell", "outcome": "rejected"}) == 1.0


# ── Multi-cell isolation ─────────────────────────────────────────

class TestMultiCell:
    def test_cells_isolated(self, metrics, registry):
        metrics.record_pulse("cell_a", "green", 0.1)
        metrics.record_pulse("cell_b", "red", 0.2)
        assert _get_counter(registry, "cell_pulse_outcome_total", {"cell": "cell_a", "outcome": "green"}) == 1.0
        assert _get_counter(registry, "cell_pulse_outcome_total", {"cell": "cell_b", "outcome": "red"}) == 1.0
        # cell_a should not have a red outcome
        assert _get_counter(registry, "cell_pulse_outcome_total", {"cell": "cell_a", "outcome": "red"}) == 0.0


# ── Helpers ──────────────────────────────────────────────────────

def _get_counter(registry, name: str, labels: dict) -> float:
    """Get a counter value from a custom registry.

    prometheus_client strips _total from family name but keeps it on samples.
    So Counter("cell_pulse") → family.name="cell_pulse", sample.name="cell_pulse_total".
    We accept either form for the `name` argument.
    """
    base = name.removesuffix("_total")
    for metric_family in registry.collect():
        if metric_family.name == base:
            for sample in metric_family.samples:
                if sample.name == f"{base}_total" and _labels_match(sample.labels, labels):
                    return sample.value
    return 0.0


def _get_gauge(registry, name: str, labels: dict) -> float:
    """Get a gauge value from a custom registry."""
    for metric_family in registry.collect():
        if metric_family.name == name:
            for sample in metric_family.samples:
                if sample.name == name and _labels_match(sample.labels, labels):
                    return sample.value
    return 0.0


def _get_histogram_sum(registry, name: str, labels: dict) -> float:
    """Get a histogram sum from a custom registry."""
    for metric_family in registry.collect():
        if metric_family.name == name:
            for sample in metric_family.samples:
                if sample.name == f"{name}_sum" and _labels_match(sample.labels, labels):
                    return sample.value
    return 0.0


def _labels_match(sample_labels: dict, expected: dict) -> bool:
    """Check if sample labels contain all expected labels."""
    return all(sample_labels.get(k) == v for k, v in expected.items())
