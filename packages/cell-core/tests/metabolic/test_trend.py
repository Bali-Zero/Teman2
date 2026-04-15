"""Tests for TrendAnalyzer — EMA, classification, weekly delta."""
import pytest

from cell_core.metabolic.definitions import (
    METRIC_AUTONOMY_INDEX,
    METRIC_ESCALATION_FREQ,
    METRIC_ONTOLOGY_DENSITY,
    METRIC_TTR,
    MetabolicSnapshot,
    MetricValue,
)
from cell_core.metabolic.storage import MetabolicStore
from cell_core.metabolic.trend import (
    TREND_DEGRADING,
    TREND_IMPROVING,
    TREND_INSUFFICIENT,
    TREND_STABLE,
    TrendAnalyzer,
)


def _store_series(store: MetabolicStore, metric_type: str, values: list[float]) -> None:
    """Store a series of snapshots with a given metric changing."""
    for i, val in enumerate(values):
        day = i + 1
        ts = f"2026-04-{day:02d}T12:00:00+00:00"
        snap = MetabolicSnapshot(
            ttr=MetricValue(METRIC_TTR, val if metric_type == METRIC_TTR else 1.0, ts, {}),
            ontology_density=MetricValue(METRIC_ONTOLOGY_DENSITY, val if metric_type == METRIC_ONTOLOGY_DENSITY else 1.0, ts, {}),
            autonomy_index=MetricValue(METRIC_AUTONOMY_INDEX, val if metric_type == METRIC_AUTONOMY_INDEX else 0.5, ts, {}),
            escalation_freq=MetricValue(METRIC_ESCALATION_FREQ, val if metric_type == METRIC_ESCALATION_FREQ else 0.5, ts, {}),
            calculated_at=ts,
        )
        store.store(snap)


@pytest.fixture
def store(tmp_path):
    return MetabolicStore(db_path=str(tmp_path / "trend_test.db"))


def test_ema_basic(store):
    """Known sequence produces expected EMA."""
    _store_series(store, METRIC_TTR, [10.0, 9.0, 8.0, 7.0, 6.0, 5.0])
    analyzer = TrendAnalyzer(store)
    ema = analyzer.ema(METRIC_TTR)
    assert ema is not None
    # With alpha=0.1, EMA should be close to the average but weighted toward recent
    assert 5.0 < ema < 10.0


def test_ema_insufficient_data(store):
    """Fewer than 2 non-null values returns None."""
    _store_series(store, METRIC_TTR, [5.0])
    analyzer = TrendAnalyzer(store)
    assert analyzer.ema(METRIC_TTR) is None


def test_classify_improving_ttr(store):
    """TTR decreasing over time should be classified as improving."""
    # 14 values: first 7 high, last 7 low (TTR = lower_better)
    values = [10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0, 5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0]
    _store_series(store, METRIC_TTR, values)
    analyzer = TrendAnalyzer(store)
    result = analyzer.classify(METRIC_TTR)
    assert result == TREND_IMPROVING


def test_classify_degrading_fe(store):
    """FE increasing over time should be classified as degrading."""
    values = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]
    _store_series(store, METRIC_ESCALATION_FREQ, values)
    analyzer = TrendAnalyzer(store)
    result = analyzer.classify(METRIC_ESCALATION_FREQ)
    assert result == TREND_DEGRADING


def test_classify_stable(store):
    """Small fluctuations should be classified as stable."""
    values = [5.0, 5.01, 4.99, 5.02, 4.98, 5.01, 4.99, 5.0, 5.01, 4.99, 5.0, 5.01, 4.99, 5.0]
    _store_series(store, METRIC_TTR, values)
    analyzer = TrendAnalyzer(store)
    result = analyzer.classify(METRIC_TTR)
    assert result == TREND_STABLE


def test_classify_insufficient(store):
    """Too few snapshots returns insufficient_data."""
    _store_series(store, METRIC_TTR, [5.0, 4.5, 4.0])
    analyzer = TrendAnalyzer(store)
    result = analyzer.classify(METRIC_TTR)
    assert result == TREND_INSUFFICIENT


def test_weekly_delta(store):
    """Two weeks of data should produce a percentage delta."""
    # Week 1: avg ~5.0, Week 2: avg ~3.0 => delta = (3-5)/5 * 100 = -40%
    values = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0]
    _store_series(store, METRIC_TTR, values)
    analyzer = TrendAnalyzer(store)
    delta = analyzer.weekly_delta(METRIC_TTR)
    assert delta is not None
    assert delta < 0  # TTR went down


def test_direction_correctness(store):
    """DO improving = increasing, TTR improving = decreasing."""
    # DO increasing: should be improving
    values_do = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0]
    _store_series(store, METRIC_ONTOLOGY_DENSITY, values_do)
    analyzer = TrendAnalyzer(store)
    assert analyzer.classify(METRIC_ONTOLOGY_DENSITY) == TREND_IMPROVING
