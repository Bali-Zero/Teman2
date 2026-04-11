"""Centrality-jump: node whose degree spikes in recent edges.

True temporal snapshots are not available; we use a structural proxy
that reads rel.updated_at as a timeline. See detector docstring.
"""
from __future__ import annotations

from osint_nexus.anomaly.detectors.centrality_jump import CentralityJumpDetector


def test_fires_on_sudden_edge_mass(fake_session):
    det = CentralityJumpDetector(
        thresholds={"sigma_multiplier": 2.0, "min_degree": 2}
    )
    # The detector first queries total degree + recent degree per node.
    # We feed it a population where node 'spike-1' has unusually high
    # recent degree vs the baseline.
    fake_session.teach(
        "recent_degree",  # detector query contains this comment marker
        [
            # id, total_degree, recent_degree
            {"node_id": "normal-1", "total_degree": 20, "recent_degree": 2},
            {"node_id": "normal-2", "total_degree": 25, "recent_degree": 3},
            {"node_id": "normal-3", "total_degree": 15, "recent_degree": 1},
            {"node_id": "normal-4", "total_degree": 22, "recent_degree": 2},
            {"node_id": "normal-5", "total_degree": 18, "recent_degree": 2},
            {"node_id": "spike-1", "total_degree": 35, "recent_degree": 30},
        ],
    )
    # Also teach: neighbors of spike-1 for evidence path
    fake_session.teach(
        "spike_neighbors",
        [
            {
                "node_id": "spike-1",
                "neighbor_ids": ["n1", "n2", "n3", "n4", "n5"],
            }
        ],
    )

    alerts = det.run(fake_session)
    assert len(alerts) == 1
    assert alerts[0].primary_entity_id == "spike-1"
    assert alerts[0].pattern == "centrality_jump"
    assert "spike-1" in alerts[0].evidence_path


def test_silent_on_uniform_distribution(fake_session):
    det = CentralityJumpDetector()
    fake_session.teach(
        "recent_degree",
        [
            {"node_id": "a", "total_degree": 20, "recent_degree": 4},
            {"node_id": "b", "total_degree": 20, "recent_degree": 4},
            {"node_id": "c", "total_degree": 20, "recent_degree": 4},
            {"node_id": "d", "total_degree": 20, "recent_degree": 4},
            {"node_id": "e", "total_degree": 20, "recent_degree": 4},
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_ignores_low_degree_nodes(fake_session):
    det = CentralityJumpDetector(thresholds={"min_degree": 5})
    fake_session.teach(
        "recent_degree",
        [
            {"node_id": "low-spike", "total_degree": 3, "recent_degree": 3},
            {"node_id": "normal", "total_degree": 20, "recent_degree": 2},
            {"node_id": "normal-2", "total_degree": 22, "recent_degree": 2},
            {"node_id": "normal-3", "total_degree": 18, "recent_degree": 3},
        ],
    )
    alerts = det.run(fake_session)
    assert alerts == []


def test_silent_on_empty(fake_session):
    det = CentralityJumpDetector()
    alerts = det.run(fake_session)
    assert alerts == []
