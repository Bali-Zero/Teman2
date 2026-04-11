"""Angkatan-disjoint: two officials from different cohorts linked via
a short non-official path (family / patron / social)."""
from __future__ import annotations

from osint_nexus.anomaly.detectors.angkatan_disjoint import AngkatanDisjointDetector


def test_fires_on_cross_angkatan_short_non_official_path(fake_session):
    det = AngkatanDisjointDetector(
        thresholds={
            "max_path_len": 3,
            "min_angkatan_gap": 3,
            "min_score": 0.5,
        }
    )
    # Detector query returns pairs of officials (a, b) with angkatan A
    # and B, gap years, and the path metadata.
    fake_session.teach(
        "angkatan_disjoint_pairs",
        [
            {
                "a_id": "off-1",
                "b_id": "off-2",
                "a_angkatan": 2001,
                "b_angkatan": 2015,
                "gap": 14,
                "path_len": 2,
                "path_rel_types": ["MARRIED_TO", "PARENT_OF"],
                "path_node_ids": ["off-1", "mid-1", "off-2"],
            }
        ],
    )
    alerts = det.run(fake_session)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.pattern == "angkatan_disjoint"
    # primary_entity_id is a composite key (sorted pair) for dedupe
    assert "off-1" in alert.evidence_path
    assert "off-2" in alert.evidence_path
    assert "mid-1" in alert.evidence_path


def test_silent_when_same_angkatan(fake_session):
    det = AngkatanDisjointDetector()
    fake_session.teach(
        "angkatan_disjoint_pairs",
        [
            {
                "a_id": "a",
                "b_id": "b",
                "a_angkatan": 2001,
                "b_angkatan": 2001,
                "gap": 0,
                "path_len": 2,
                "path_rel_types": ["KNOWS", "KNOWS"],
                "path_node_ids": ["a", "m", "b"],
            }
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_when_path_too_long(fake_session):
    det = AngkatanDisjointDetector(thresholds={"max_path_len": 2})
    fake_session.teach(
        "angkatan_disjoint_pairs",
        [
            {
                "a_id": "a",
                "b_id": "b",
                "a_angkatan": 2001,
                "b_angkatan": 2015,
                "gap": 14,
                "path_len": 5,  # above threshold
                "path_rel_types": ["KNOWS"] * 5,
                "path_node_ids": ["a", "m1", "m2", "m3", "m4", "b"],
            }
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_on_empty(fake_session):
    det = AngkatanDisjointDetector()
    alerts = det.run(fake_session)
    assert alerts == []


def test_dedupes_symmetric_pairs(fake_session):
    """If the query returns (a, b) and (b, a), only one alert fires."""
    det = AngkatanDisjointDetector(thresholds={"min_score": 0.5})
    fake_session.teach(
        "angkatan_disjoint_pairs",
        [
            {
                "a_id": "x",
                "b_id": "y",
                "a_angkatan": 2000,
                "b_angkatan": 2010,
                "gap": 10,
                "path_len": 2,
                "path_rel_types": ["MET_WITH", "KNOWS"],
                "path_node_ids": ["x", "m", "y"],
            },
            {
                "a_id": "y",
                "b_id": "x",
                "a_angkatan": 2010,
                "b_angkatan": 2000,
                "gap": 10,
                "path_len": 2,
                "path_rel_types": ["KNOWS", "MET_WITH"],
                "path_node_ids": ["y", "m", "x"],
            },
        ],
    )
    alerts = det.run(fake_session)
    assert len(alerts) == 1
