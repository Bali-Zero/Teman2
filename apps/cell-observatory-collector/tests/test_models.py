import pytest
from cell_observatory.models import PulseEventV1, ClassificationLabel


def test_pulse_event_v1_minimal():
    event = PulseEventV1(
        _outbox_id=1,
        event_version="v1",
        cell_id="organism",
        cell_kind="innervation",
        pulse_id="01ABC",
        pulse_timestamp="2026-05-01T00:00:00.000Z",
        phase="homeostatic",
        sensors=[],
        pulse_result={"classifier_self": "green", "trend_window_min": 15, "trend_label": "stable"},
        homeostatic_state={"energy_pct": 80, "load_factor": 0.3},
        scar_signals=[],
        metadata={"host": "Nuzantara", "machine_role": "Pro", "cell_core_version": "0.1.4"},
    )
    assert event.cell_id == "organism"
    assert event.outbox_id == 1  # underscore-prefixed alias


def test_classification_label_enum():
    assert ClassificationLabel.NORMAL.value == "normal"
    assert ClassificationLabel.ANOMALY.value == "anomaly"
    assert ClassificationLabel.CRITICAL.value == "critical"
    assert ClassificationLabel.UNCERTAIN.value == "uncertain"


def test_pulse_event_v1_rejects_event_version_mismatch():
    with pytest.raises(ValueError):
        PulseEventV1(
            _outbox_id=1,
            event_version="v2",  # wrong
            cell_id="x", cell_kind="x", pulse_id="x",
            pulse_timestamp="2026-05-01T00:00:00.000Z",
            phase="x", sensors=[], pulse_result={}, homeostatic_state={},
            scar_signals=[], metadata={},
        )
