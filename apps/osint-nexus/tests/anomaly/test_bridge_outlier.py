"""Bridge-outlier detector: finds cut vertices that split communities.

Semantic: one node sits between two otherwise-disjoint communities.
Removing it disconnects the graph. In OSINT, the classic 'broker'
who controls the ONLY channel between two cliques.
"""
from __future__ import annotations

from osint_nexus.anomaly.detectors.bridge_outlier import BridgeOutlierDetector


def test_fires_on_cut_vertex_between_two_communities(fake_session):
    det = BridgeOutlierDetector()

    # Teach session: Louvain returns two distinct communities, and
    # articulation points returns one cut vertex on the boundary.
    fake_session.teach(
        "gds.louvain.stream",
        [
            {"node_id": "bridge-1", "community_id": 0},
            {"node_id": "left-a", "community_id": 0},
            {"node_id": "left-b", "community_id": 0},
            {"node_id": "left-c", "community_id": 0},
            {"node_id": "right-a", "community_id": 1},
            {"node_id": "right-b", "community_id": 1},
            {"node_id": "right-c", "community_id": 1},
        ],
    )
    fake_session.teach(
        "gds.articulationPoints.stream",
        [
            {"node_id": "bridge-1"},
        ],
    )
    fake_session.teach(
        "MATCH (cut)-[]-(nbr)",
        [
            {
                "cut_id": "bridge-1",
                "neighbor_communities": [0, 0, 1, 1],  # spans two
                "neighbor_ids": ["left-a", "left-b", "right-a", "right-b"],
            }
        ],
    )

    alerts = det.run(fake_session)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.primary_entity_id == "bridge-1"
    assert alert.pattern == "bridge_outlier"
    assert "bridge-1" in alert.evidence_path


def test_silent_when_cut_vertex_only_touches_one_community(fake_session):
    det = BridgeOutlierDetector()
    fake_session.teach(
        "gds.louvain.stream",
        [
            {"node_id": "n1", "community_id": 0},
            {"node_id": "n2", "community_id": 0},
            {"node_id": "n3", "community_id": 0},
            {"node_id": "n4", "community_id": 0},
            {"node_id": "n5", "community_id": 0},
        ],
    )
    fake_session.teach(
        "gds.articulationPoints.stream",
        [{"node_id": "n3"}],
    )
    fake_session.teach(
        "MATCH (cut)-[]-(nbr)",
        [
            {
                "cut_id": "n3",
                "neighbor_communities": [0, 0, 0, 0],
                "neighbor_ids": ["n1", "n2", "n4", "n5"],
            }
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_when_tiny_communities(fake_session):
    det = BridgeOutlierDetector(thresholds={"min_community_size": 3})
    # A cut with one-node "communities" on each side should not alert
    fake_session.teach(
        "gds.louvain.stream",
        [
            {"node_id": "bridge-1", "community_id": 0},
            {"node_id": "lone-left", "community_id": 1},
            {"node_id": "lone-right", "community_id": 2},
        ],
    )
    fake_session.teach(
        "gds.articulationPoints.stream",
        [{"node_id": "bridge-1"}],
    )
    fake_session.teach(
        "MATCH (cut)-[]-(nbr)",
        [
            {
                "cut_id": "bridge-1",
                "neighbor_communities": [1, 2],
                "neighbor_ids": ["lone-left", "lone-right"],
            }
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_on_empty_graph(fake_session):
    det = BridgeOutlierDetector()
    alerts = det.run(fake_session)
    assert alerts == []
