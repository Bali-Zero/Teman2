"""Precheck tests for the three data-gated detectors.

The three detectors that carry a semantic precondition on the live
graph are:

* ``temporal_burst``   — needs enough history spread for an EWMA
* ``centrality_jump``  — needs enough history spread for "recent" to
                         differ from "before"
* ``angkatan_disjoint``— needs >= 2 distinct Official.angkatan values

Each test exercises BOTH the ``ok=False`` path (insufficient data)
and the ``ok=True`` path (sufficient data) against a scripted
FakeSession.
"""

from __future__ import annotations

from osint_nexus.anomaly.detectors.angkatan_disjoint import AngkatanDisjointDetector
from osint_nexus.anomaly.detectors.centrality_jump import CentralityJumpDetector
from osint_nexus.anomaly.detectors.temporal_burst import TemporalBurstDetector


# ---------------------------------------------------------------------------
# temporal_burst — min_history_days gate
# ---------------------------------------------------------------------------

def test_temporal_burst_precheck_blocks_on_narrow_spread(fake_session):
    det = TemporalBurstDetector(thresholds={"min_history_days": 30})
    fake_session.teach(
        "temporal_burst_precheck",
        [{"min_ts": "2026-04-07T00:00:00", "max_ts": "2026-04-11T00:00:00",
          "total": 2233, "spread_days": 3}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is False
    assert "3 days" in pre.reason
    assert "need 30" in pre.reason
    assert pre.stat["spread_days"] == 3
    assert pre.stat["min_history_days"] == 30


def test_temporal_burst_precheck_blocks_on_no_edges(fake_session):
    det = TemporalBurstDetector()
    fake_session.teach(
        "temporal_burst_precheck",
        [{"min_ts": None, "max_ts": None, "total": 0, "spread_days": None}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is False
    assert "no edges" in pre.reason


def test_temporal_burst_precheck_passes_on_wide_spread(fake_session):
    det = TemporalBurstDetector(thresholds={"min_history_days": 30})
    fake_session.teach(
        "temporal_burst_precheck",
        [{"min_ts": "2025-10-01T00:00:00", "max_ts": "2026-04-11T00:00:00",
          "total": 50000, "spread_days": 192}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is True
    assert pre.stat["spread_days"] == 192


# ---------------------------------------------------------------------------
# centrality_jump — same temporal-spread gate
# ---------------------------------------------------------------------------

def test_centrality_jump_precheck_blocks_on_narrow_spread(fake_session):
    det = CentralityJumpDetector(thresholds={"min_history_days": 30})
    fake_session.teach(
        "centrality_jump_precheck",
        [{"min_ts": "2026-04-07T00:00:00", "max_ts": "2026-04-11T00:00:00",
          "total": 2233, "spread_days": 3}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is False
    assert "3 days" in pre.reason
    assert pre.stat["total_edges_with_ts"] == 2233


def test_centrality_jump_precheck_passes_on_wide_spread(fake_session):
    det = CentralityJumpDetector(thresholds={"min_history_days": 30})
    fake_session.teach(
        "centrality_jump_precheck",
        [{"min_ts": "2025-01-01T00:00:00", "max_ts": "2026-04-11T00:00:00",
          "total": 100000, "spread_days": 465}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is True


# ---------------------------------------------------------------------------
# angkatan_disjoint — >= 2 distinct cohorts + spread >= min_gap
# ---------------------------------------------------------------------------

def test_angkatan_disjoint_precheck_blocks_on_single_cohort(fake_session):
    det = AngkatanDisjointDetector(thresholds={"min_angkatan_gap": 3})
    fake_session.teach(
        "angkatan_disjoint_precheck",
        [{"distinct_years": 1, "min_y": 2000, "max_y": 2000, "total_officials": 170}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is False
    assert "1 distinct" in pre.reason
    assert "spread 0" in pre.reason
    assert pre.stat["distinct_years"] == 1
    assert pre.stat["spread"] == 0


def test_angkatan_disjoint_precheck_blocks_on_tiny_spread(fake_session):
    """Two cohorts but gap below min_angkatan_gap."""
    det = AngkatanDisjointDetector(thresholds={"min_angkatan_gap": 3})
    fake_session.teach(
        "angkatan_disjoint_precheck",
        [{"distinct_years": 2, "min_y": 2000, "max_y": 2001, "total_officials": 120}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is False
    assert "2 distinct" in pre.reason
    assert pre.stat["spread"] == 1


def test_angkatan_disjoint_precheck_blocks_on_no_officials(fake_session):
    det = AngkatanDisjointDetector()
    # Empty result → no Official nodes with angkatan
    pre = det.precheck(fake_session)
    assert pre.ok is False
    assert "no Official" in pre.reason
    assert pre.stat["distinct_years"] == 0


def test_angkatan_disjoint_precheck_passes_on_multi_cohort(fake_session):
    det = AngkatanDisjointDetector(thresholds={"min_angkatan_gap": 3})
    fake_session.teach(
        "angkatan_disjoint_precheck",
        [{"distinct_years": 8, "min_y": 1990, "max_y": 2015, "total_officials": 170}],
    )
    pre = det.precheck(fake_session)
    assert pre.ok is True
    assert pre.stat["spread"] == 25
    assert pre.stat["distinct_years"] == 8
