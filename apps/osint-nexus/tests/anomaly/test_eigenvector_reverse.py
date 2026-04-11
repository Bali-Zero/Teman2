"""Eigenvector-reverse: a highly-central hub whose neighbors are all low.

Semantic: compartmentalized power — the hub is important but nobody
they talk to is. Classic cut-out / handler pattern.
"""
from __future__ import annotations

from osint_nexus.anomaly.detectors.eigenvector_reverse import EigenvectorReverseDetector


def test_fires_on_compartmentalized_hub(fake_session):
    """Graph with one lone hub → one alert."""
    det = EigenvectorReverseDetector()

    # Detector runs a GDS eigenvector, then for each top-decile node
    # fetches 1-hop neighbors' eigenvector ranks. We teach the fake
    # session to return both.
    fake_session.teach(
        "gds.eigenvector.stream",
        [
            {"node_id": "hub-1", "score": 0.95, "percentile": 0.98},
            {"node_id": "neighbor-a", "score": 0.05, "percentile": 0.12},
            {"node_id": "neighbor-b", "score": 0.08, "percentile": 0.18},
            {"node_id": "neighbor-c", "score": 0.03, "percentile": 0.08},
            {"node_id": "neighbor-d", "score": 0.06, "percentile": 0.15},
            # And some ordinary mid-graph noise
            {"node_id": "normal-1", "score": 0.40, "percentile": 0.60},
            {"node_id": "normal-2", "score": 0.35, "percentile": 0.55},
        ],
    )
    fake_session.teach(
        "MATCH (hub)-[]-(neighbor)",
        [
            {
                "hub_id": "hub-1",
                "neighbor_ids": ["neighbor-a", "neighbor-b", "neighbor-c", "neighbor-d"],
            },
        ],
    )

    alerts = det.run(fake_session)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.pattern == "eigenvector_reverse"
    assert alert.primary_entity_id == "hub-1"
    assert "hub-1" in alert.evidence_path
    # All neighbors are in evidence
    for n in ["neighbor-a", "neighbor-b", "neighbor-c", "neighbor-d"]:
        assert n in alert.evidence_path
    assert alert.score >= 0.6


def test_silent_on_normal_hub_with_high_neighbors(fake_session):
    """If the hub's neighbors are themselves well-connected → no alert."""
    det = EigenvectorReverseDetector()
    fake_session.teach(
        "gds.eigenvector.stream",
        [
            {"node_id": "hub-1", "score": 0.95, "percentile": 0.98},
            {"node_id": "neighbor-a", "score": 0.8, "percentile": 0.85},
            {"node_id": "neighbor-b", "score": 0.75, "percentile": 0.80},
            {"node_id": "neighbor-c", "score": 0.70, "percentile": 0.78},
            {"node_id": "neighbor-d", "score": 0.65, "percentile": 0.72},
        ],
    )
    fake_session.teach(
        "MATCH (hub)-[]-(neighbor)",
        [
            {
                "hub_id": "hub-1",
                "neighbor_ids": ["neighbor-a", "neighbor-b", "neighbor-c", "neighbor-d"],
            },
        ],
    )

    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_on_hub_with_too_few_neighbors(fake_session):
    """Hub with < min_neighbors is not flagged (noise floor)."""
    det = EigenvectorReverseDetector(thresholds={"min_neighbors": 4})
    fake_session.teach(
        "gds.eigenvector.stream",
        [
            {"node_id": "hub-1", "score": 0.95, "percentile": 0.98},
            {"node_id": "neighbor-a", "score": 0.05, "percentile": 0.10},
        ],
    )
    fake_session.teach(
        "MATCH (hub)-[]-(neighbor)",
        [
            {"hub_id": "hub-1", "neighbor_ids": ["neighbor-a"]},
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_on_empty_graph(fake_session):
    det = EigenvectorReverseDetector()
    # No rules taught — fake_session returns [] for everything
    alerts = det.run(fake_session)
    assert alerts == []
