"""Runner behavior under precheck gating.

Validates that:

1. A detector whose ``precheck`` returns ``ok=False`` produces exactly
   ONE informational alert (never a ClientError warning).
2. Real alerts from passing detectors are unaffected.
3. Ranking places informational alerts strictly AFTER real alerts.
4. No ``detector X failed`` WARNING is logged for preconditioned
   skips — only an INFO line.
"""

from __future__ import annotations

import logging

from osint_nexus.anomaly.alert import Alert, make_alert_id
from osint_nexus.anomaly.base import Detector, PreconditionResult
from osint_nexus.anomaly.runner import AnomalyRunner


class _BlockedDetector(Detector):
    """Detector whose precheck always fails. run() would crash if called."""

    def __init__(self, name: str, reason: str = "no data", stat: dict | None = None):
        super().__init__()
        self.name = name
        self._reason = reason
        self._stat = dict(stat or {"distinct_years": 1, "spread": 0})

    def precheck(self, session):  # noqa: ANN001
        return PreconditionResult(ok=False, reason=self._reason, stat=self._stat)

    def run(self, session):  # noqa: ANN001
        # Must NEVER be called when precheck fails.
        raise AssertionError(
            f"{self.name}.run called despite precheck returning ok=False"
        )


class _PassingDetector(Detector):
    """Detector that precheck-passes and returns a fixed alert."""

    def __init__(self, name: str, score: float):
        super().__init__()
        self.name = name
        self._score = score

    def run(self, session):  # noqa: ANN001
        return [
            Alert(
                alert_id=make_alert_id(self.name, "e", day_bucket="2026-04-12"),
                pattern=self.name,
                primary_entity_id="e",
                score=self._score,
                confidence=0.9,
                evidence_path=["e"],
                rationale_id="R",
                created_at="2026-04-12T00:00:00+00:00",
            )
        ]


class _FakeLiveSession:
    """Minimal non-None session so the runner actually calls precheck."""

    def run(self, query, parameters=None):  # noqa: ANN001
        class _Result:
            def __iter__(self):
                return iter([])

        return _Result()


def test_blocked_detector_yields_one_informational_alert():
    blocked = _BlockedDetector("temporal_burst", reason="spread 3, need 30")
    runner = AnomalyRunner(detectors=[blocked])
    result = runner.run(_FakeLiveSession())
    assert len(result) == 1
    alert = result[0]
    assert alert.informational is True
    assert alert.pattern == "temporal_burst"
    assert alert.score == 0.0
    assert alert.confidence == 0.0
    assert "PRECHECK-BLOCKED" in alert.rationale_id
    assert "spread 3" in alert.rationale_id


def test_blocked_detector_stat_flows_into_evidence_path():
    blocked = _BlockedDetector(
        "angkatan_disjoint",
        reason="angkatan variance too low",
        stat={"distinct_years": 1, "spread": 0, "min_angkatan_gap": 3},
    )
    runner = AnomalyRunner(detectors=[blocked])
    result = runner.run(_FakeLiveSession())
    assert len(result) == 1
    # evidence_path carries sorted key=value strings from the stat dict
    ev = result[0].evidence_path
    assert "distinct_years=1" in ev
    assert "spread=0" in ev
    assert "min_angkatan_gap=3" in ev


def test_informational_alerts_rank_after_real_alerts():
    blocked_a = _BlockedDetector("centrality_jump", reason="spread 3")
    passing_low = _PassingDetector("bridge_outlier", score=0.65)
    passing_high = _PassingDetector("eigenvector_reverse", score=0.95)
    blocked_b = _BlockedDetector("angkatan_disjoint", reason="single cohort")

    runner = AnomalyRunner(
        detectors=[blocked_a, passing_low, passing_high, blocked_b]
    )
    result = runner.run(_FakeLiveSession())

    # 2 real + 2 informational = 4 total
    assert len(result) == 4
    # Real alerts come first, sorted by score DESC
    assert result[0].pattern == "eigenvector_reverse"
    assert result[0].score == 0.95
    assert result[0].informational is False
    assert result[1].pattern == "bridge_outlier"
    assert result[1].score == 0.65
    assert result[1].informational is False
    # Informational come last, order determined by alert_id tiebreak
    assert result[2].informational is True
    assert result[3].informational is True
    informational_patterns = {result[2].pattern, result[3].pattern}
    assert informational_patterns == {"centrality_jump", "angkatan_disjoint"}


def test_blocked_detector_does_not_produce_warning(caplog):
    blocked = _BlockedDetector("temporal_burst", reason="no edges with r.updated_at")
    runner = AnomalyRunner(detectors=[blocked])
    with caplog.at_level(logging.INFO, logger="osint.anomaly.runner"):
        result = runner.run(_FakeLiveSession())
    # One INFO line ("blocked"), NO warning
    messages = [r for r in caplog.records if r.name == "osint.anomaly.runner"]
    info_messages = [m.getMessage() for m in messages if m.levelno == logging.INFO]
    warn_messages = [m.getMessage() for m in messages if m.levelno >= logging.WARNING]
    assert any("blocked" in m for m in info_messages)
    assert not any("failed" in m for m in warn_messages)
    assert len(result) == 1
    assert result[0].informational is True


def test_mixed_run_produces_expected_mix():
    """Smoke: 3 passing, 2 blocked → 3 real + 2 informational."""
    detectors = [
        _PassingDetector("p1", score=0.8),
        _BlockedDetector("b1", reason="narrow spread"),
        _PassingDetector("p2", score=0.7),
        _PassingDetector("p3", score=0.6),
        _BlockedDetector("b2", reason="no cohorts"),
    ]
    runner = AnomalyRunner(detectors=detectors)
    result = runner.run(_FakeLiveSession())
    assert len(result) == 5
    # First 3 are real in score-desc order
    assert [a.score for a in result[:3]] == [0.8, 0.7, 0.6]
    assert all(not a.informational for a in result[:3])
    # Last 2 are informational
    assert all(a.informational for a in result[3:])
