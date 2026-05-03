"""Tests for CellMetricsExporter — Prometheus HTTP endpoint."""
from __future__ import annotations

import pytest

from cell_core.observability._prom_compat import HAS_PROM
from cell_core.observability.exporter import CellMetricsExporter
from cell_core.observability.pulse_metrics import PulseMetrics

pytestmark = pytest.mark.skipif(not HAS_PROM, reason="prometheus_client not installed")


@pytest.fixture
def registry():
    from prometheus_client import CollectorRegistry
    return CollectorRegistry()


class TestExporterScrape:
    def test_scrape_contains_metrics(self, registry):
        """Record some data and verify generate_latest output."""
        metrics = PulseMetrics(registry=registry)
        metrics.record_pulse("test_cell", "green", 0.42)
        metrics.record_phase("test_cell", "sense", 0.01)
        metrics.observe_homeostasis("test_cell", _FakeState(0.3, 0.9, 0.5))

        exporter = CellMetricsExporter(registry=registry)
        output = exporter.scrape()

        assert isinstance(output, bytes)
        text = output.decode("utf-8")

        # Core pulse metrics
        assert "cell_pulse_total" in text
        assert "cell_pulse_duration_seconds" in text
        assert "cell_pulse_outcome_total" in text

        # Phase metrics
        assert "cell_pulse_phase_duration_seconds" in text

        # Homeostasis gauges
        assert "cell_homeostasis_stress" in text
        assert "cell_homeostasis_energy" in text

    def test_scrape_empty_registry(self, registry):
        exporter = CellMetricsExporter(registry=registry)
        output = exporter.scrape()
        # Should return valid bytes even with no data
        assert isinstance(output, bytes)

    def test_exporter_not_started_by_default(self, registry):
        exporter = CellMetricsExporter(registry=registry)
        assert not exporter.is_running


class TestExporterNoOp:
    def test_scrape_without_prom(self):
        """When no registry, scrape returns empty bytes."""
        from cell_core.observability._prom_compat import generate_latest
        # generate_latest with no args should work
        result = generate_latest()
        assert isinstance(result, bytes)


class TestCardinalityInScrape:
    def test_total_series_under_guard(self, registry):
        """Verify that recording 3 cells stays well under 500 series."""
        from cell_core.observability.cardinality import CardinalityGuard

        metrics = PulseMetrics(registry=registry)
        # Simulate 3 cells with full lifecycle
        for cell in ("cell", "mata-garuda", "sentinel"):
            metrics.record_pulse(cell, "green", 0.5)
            for phase in ("safety", "sense", "evaluate", "think", "act", "reflect", "dream", "mature"):
                metrics.record_phase(cell, phase, 0.01)
            metrics.observe_homeostasis(cell, _FakeState(0.3, 0.8, 0.5))
            metrics.observe_trend(cell, _FakeTrend(False, False, False))
            metrics.record_genome_search(cell, hit=True)
            metrics.record_genome_search(cell, hit=False)
            metrics.record_hgt_publish(cell)
            metrics.record_hgt_consume(cell, 2)
            metrics.record_hgt_feedback(cell, accepted=True)

        guard = CardinalityGuard(registry=registry, max_series=500)
        total = guard.total_series()
        assert total < 500, f"Total series {total} exceeds 500 guard"
        assert guard.is_healthy()


# ── Test helpers ─────────────────────────────────────────────────

class _FakeState:
    def __init__(self, stress: float, energy: float, arousal: float):
        self.stress_level = stress
        self.energy_level = energy
        self.arousal = arousal


class _FakeTrend:
    def __init__(self, drift: bool, flap: bool, sustained: bool):
        self.monotonic_drift = drift
        self.flapping = flap
        self.sustained_degraded = sustained
