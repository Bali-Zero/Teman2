"""Temporal-burst: edge-class volume spike above EWMA baseline."""
from __future__ import annotations

from osint_nexus.anomaly.detectors.temporal_burst import TemporalBurstDetector


def test_fires_on_clear_spike(fake_session):
    det = TemporalBurstDetector(
        thresholds={
            "z_threshold": 3.0,
            "window_days": 7,
            "min_edges_in_window": 3,
            "rel_types": ["MET_WITH"],
        }
    )
    # Teach: a time-series of edge counts per week. The last bucket is
    # far above the EWMA of the previous ones → should fire.
    fake_session.teach(
        "temporal_burst_series",
        [
            {"rel_type": "MET_WITH", "bucket": "2026-01-06", "edge_count": 2},
            {"rel_type": "MET_WITH", "bucket": "2026-01-13", "edge_count": 3},
            {"rel_type": "MET_WITH", "bucket": "2026-01-20", "edge_count": 2},
            {"rel_type": "MET_WITH", "bucket": "2026-01-27", "edge_count": 3},
            {"rel_type": "MET_WITH", "bucket": "2026-02-03", "edge_count": 2},
            {"rel_type": "MET_WITH", "bucket": "2026-02-10", "edge_count": 2},
            {"rel_type": "MET_WITH", "bucket": "2026-02-17", "edge_count": 3},
            {"rel_type": "MET_WITH", "bucket": "2026-02-24", "edge_count": 45},  # burst
        ],
    )
    fake_session.teach(
        "burst_edges",
        [
            {
                "rel_type": "MET_WITH",
                "bucket": "2026-02-24",
                "source_ids": ["s-1", "s-2", "s-3"],
                "target_ids": ["t-1", "t-2", "t-3"],
            }
        ],
    )
    alerts = det.run(fake_session)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.pattern == "temporal_burst"
    assert "MET_WITH" in alert.rationale_id
    # primary entity is a synthetic ID for the burst (rel_type + bucket)
    assert "MET_WITH" in alert.primary_entity_id


def test_silent_on_flat_series(fake_session):
    det = TemporalBurstDetector()
    fake_session.teach(
        "temporal_burst_series",
        [
            {"rel_type": "MET_WITH", "bucket": f"2026-01-{i:02d}", "edge_count": 5}
            for i in (6, 13, 20, 27)
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_when_below_min_edges(fake_session):
    det = TemporalBurstDetector(
        thresholds={"min_edges_in_window": 10, "rel_types": ["MET_WITH"]}
    )
    fake_session.teach(
        "temporal_burst_series",
        [
            {"rel_type": "MET_WITH", "bucket": "2026-01-06", "edge_count": 1},
            {"rel_type": "MET_WITH", "bucket": "2026-01-13", "edge_count": 1},
            {"rel_type": "MET_WITH", "bucket": "2026-01-20", "edge_count": 1},
            {"rel_type": "MET_WITH", "bucket": "2026-01-27", "edge_count": 7},  # "spike" but <10
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_on_empty(fake_session):
    det = TemporalBurstDetector()
    alerts = det.run(fake_session)
    assert alerts == []


def test_excludes_sources_from_batch_ingest(fake_session):
    """Bursts caused by a known batch source should not fire."""
    det = TemporalBurstDetector(
        thresholds={
            "source_exclude": ["lhkpn"],
            "rel_types": ["OWNS"],
            "min_edges_in_window": 3,
        }
    )
    # Teaching: series where the spike is ENTIRELY from excluded source
    fake_session.teach(
        "temporal_burst_series",
        [
            {"rel_type": "OWNS", "bucket": "2026-01-06", "edge_count": 2},
            {"rel_type": "OWNS", "bucket": "2026-01-13", "edge_count": 3},
            {"rel_type": "OWNS", "bucket": "2026-01-20", "edge_count": 2},
            # Spike but is lhkpn — detector should skip
            {
                "rel_type": "OWNS",
                "bucket": "2026-01-27",
                "edge_count": 40,
                "sources": ["lhkpn"],
            },
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []
