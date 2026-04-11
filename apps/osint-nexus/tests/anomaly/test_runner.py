"""Runner: orchestrates multiple detectors, dedupes, ranks."""
from __future__ import annotations

from osint_nexus.anomaly.alert import Alert, make_alert_id
from osint_nexus.anomaly.base import Detector
from osint_nexus.anomaly.runner import AnomalyRunner


class _FakeDetector(Detector):
    """Returns a pre-built list of alerts. Never talks to a session."""

    def __init__(self, name: str, alerts: list[Alert]) -> None:
        super().__init__()
        self.name = name
        self._alerts = alerts

    def run(self, session):  # noqa: ANN001 - session unused
        return list(self._alerts)


def _mk(pattern: str, eid: str, score: float, *, informational: bool = False) -> Alert:
    return Alert(
        alert_id=make_alert_id(pattern, eid, day_bucket="2026-04-11"),
        pattern=pattern,
        primary_entity_id=eid,
        score=score,
        confidence=1.0,
        evidence_path=[eid],
        rationale_id="R",
        created_at="2026-04-11T00:00:00+00:00",
        informational=informational,
    )


def test_runner_aggregates_alerts_from_all_detectors():
    d1 = _FakeDetector("p1", [_mk("p1", "a", 0.9)])
    d2 = _FakeDetector("p2", [_mk("p2", "b", 0.7), _mk("p2", "c", 0.5)])
    runner = AnomalyRunner(detectors=[d1, d2])
    result = runner.run(session=None)
    assert len(result) == 3


def test_runner_dedupes_identical_alerts():
    # Same pattern + entity + same day → same alert_id → dedupe
    a1 = _mk("p1", "node-X", 0.8)
    a2 = _mk("p1", "node-X", 0.9)  # different score but same id
    d = _FakeDetector("p1", [a1, a2])
    runner = AnomalyRunner(detectors=[d])
    result = runner.run(session=None)
    # Dedupe keeps the HIGHER-score alert
    assert len(result) == 1
    assert result[0].score == 0.9


def test_runner_ranks_descending_by_score():
    d = _FakeDetector(
        "p1",
        [
            _mk("p1", "a", 0.3),
            _mk("p1", "b", 0.9),
            _mk("p1", "c", 0.6),
        ],
    )
    runner = AnomalyRunner(detectors=[d])
    result = runner.run(session=None)
    scores = [a.score for a in result]
    assert scores == sorted(scores, reverse=True)


def test_runner_ranking_is_stable_for_ties():
    # Same score → sorted by alert_id for determinism
    d = _FakeDetector(
        "p1",
        [
            _mk("p1", "zzz", 0.5),
            _mk("p1", "aaa", 0.5),
            _mk("p1", "mmm", 0.5),
        ],
    )
    runner = AnomalyRunner(detectors=[d])
    r1 = runner.run(session=None)
    r2 = runner.run(session=None)
    assert [a.alert_id for a in r1] == [a.alert_id for a in r2]


def test_runner_survives_detector_exception():
    class _Broken(Detector):
        name = "broken"

        def run(self, session):
            raise RuntimeError("boom")

    d_good = _FakeDetector("p1", [_mk("p1", "a", 0.5)])
    d_bad = _Broken()
    runner = AnomalyRunner(detectors=[d_bad, d_good])
    # Should not crash — logs error, drops broken detector's output
    result = runner.run(session=None)
    assert len(result) == 1
    assert result[0].pattern == "p1"


def test_runner_ranks_informational_after_real_regardless_of_score():
    """Even a high-score informational alert is ranked below a low-score real one."""
    real_low = _mk("real", "a", 0.1)
    info_high = _mk("info", "b", 0.9, informational=True)
    d = _FakeDetector("p1", [real_low, info_high])
    runner = AnomalyRunner(detectors=[d])
    result = runner.run(session=None)
    assert len(result) == 2
    assert result[0].informational is False
    assert result[0].score == 0.1
    assert result[1].informational is True
    assert result[1].score == 0.9


def test_runner_dedupes_real_and_informational_independently():
    """Same alert_id between real and informational: real wins."""
    # Same alert_id — dedupe keeps the higher-scored entry (real one).
    real = _mk("p1", "a", 0.2)
    info = _mk("p1", "a", 0.0, informational=True)
    d = _FakeDetector("p1", [info, real])
    runner = AnomalyRunner(detectors=[d])
    result = runner.run(session=None)
    # Dedupe on alert_id (same pattern+entity+day) keeps the higher
    # score. Real one has score 0.2 > 0.0, so it wins.
    assert len(result) == 1
    assert result[0].informational is False
