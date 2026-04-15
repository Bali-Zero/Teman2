"""Tests for metabolic definitions — dataclasses and formatters."""
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


def _make_metric(metric_type: str, value: float | None = 1.0) -> MetricValue:
    return MetricValue(
        metric_type=metric_type,
        value=value,
        calculated_at="2026-04-16T12:00:00+00:00",
        metadata={"test": True},
    )


def _make_snapshot(ttr=3.2, do=2.25, ia=0.17, fe=0.68) -> MetabolicSnapshot:
    return MetabolicSnapshot(
        ttr=_make_metric(METRIC_TTR, ttr),
        ontology_density=_make_metric(METRIC_ONTOLOGY_DENSITY, do),
        autonomy_index=_make_metric(METRIC_AUTONOMY_INDEX, ia),
        escalation_freq=_make_metric(METRIC_ESCALATION_FREQ, fe),
        calculated_at="2026-04-16T12:00:00+00:00",
    )


def test_metric_value_creation():
    mv = _make_metric(METRIC_TTR, 4.5)
    assert mv.metric_type == METRIC_TTR
    assert mv.value == 4.5
    assert mv.metadata == {"test": True}
    assert mv.direction == DIRECTION_LOWER_BETTER
    assert mv.label == "Time-to-Resolution"
    assert mv.unit == "pulses"


def test_metric_value_to_dict_roundtrip():
    mv = _make_metric(METRIC_ONTOLOGY_DENSITY, 2.247)
    d = mv.to_dict()
    assert d["metric_type"] == METRIC_ONTOLOGY_DENSITY
    assert d["value"] == 2.247
    mv2 = MetricValue.from_dict(d)
    assert mv2.value == mv.value
    assert mv2.metric_type == mv.metric_type


def test_snapshot_to_dict():
    snap = _make_snapshot()
    d = snap.to_dict()
    assert "ttr" in d
    assert "ontology_density" in d
    assert "autonomy_index" in d
    assert "escalation_freq" in d
    assert d["calculated_at"] == "2026-04-16T12:00:00+00:00"
    # Roundtrip
    snap2 = MetabolicSnapshot.from_dict(d)
    assert snap2.ttr.value == snap.ttr.value
    assert snap2.ontology_density.value == snap.ontology_density.value


def test_snapshot_format_telegram():
    snap = _make_snapshot(ttr=3.2, do=2.25, ia=0.17, fe=0.68)
    trends = {
        METRIC_TTR: "improving",
        METRIC_ONTOLOGY_DENSITY: "stable",
        METRIC_AUTONOMY_INDEX: "improving",
        METRIC_ESCALATION_FREQ: "degrading",
    }
    text = snap.format_telegram(trends)
    assert "METABOLIC REPORT" in text
    assert "3.20 pulses" in text
    assert "[+]" in text  # improving marker
    assert "[!]" in text  # degrading marker
    assert "[=]" in text  # stable marker
    assert "2 improving" in text


def test_none_values_handled():
    snap = MetabolicSnapshot(
        ttr=_make_metric(METRIC_TTR, None),
        ontology_density=_make_metric(METRIC_ONTOLOGY_DENSITY, None),
        autonomy_index=_make_metric(METRIC_AUTONOMY_INDEX, 0.0),
        escalation_freq=_make_metric(METRIC_ESCALATION_FREQ, 0.0),
        calculated_at="2026-04-16T12:00:00+00:00",
    )
    d = snap.to_dict()
    assert d["ttr"]["value"] is None
    text = snap.format_telegram()
    assert "N/A" in text


def test_get_metric():
    snap = _make_snapshot(ttr=5.0)
    assert snap.get_metric(METRIC_TTR).value == 5.0
    assert snap.get_metric(METRIC_AUTONOMY_INDEX).value == 0.17
    assert snap.get_metric("nonexistent") is None
