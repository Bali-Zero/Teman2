"""Tests for centrality_jump detector."""

from __future__ import annotations

import pytest

from osint_nexus.anomaly.detectors.centrality_jump import CentralityJumpDetector
from tests.anomaly.conftest import MockGraph


@pytest.fixture
def detector() -> CentralityJumpDetector:
    return CentralityJumpDetector({
        "window_days": 30,
        "recent_edge_fraction_threshold": 0.40,
        "min_degree": 3,
        "min_recent_edges": 2,
    })


@pytest.fixture
def graph_with_jump(mock_graph: MockGraph) -> MockGraph:
    """Graph where node has 80% recent edges (4/5) — should trigger."""
    mock_graph.set_query_result(
        "recent_fraction",
        [
            {
                "node_id": "4:1",
                "node_labels": ["Official"],
                "total_degree": 5,
                "recent_edges": 4,
                "recent_fraction": 0.80,
            },
        ],
    )
    return mock_graph


@pytest.fixture
def graph_without_jump(mock_graph: MockGraph) -> MockGraph:
    """Graph where no node exceeds recent fraction threshold."""
    mock_graph.set_query_result("recent_fraction", [])
    return mock_graph


async def test_detects_centrality_jump(
    detector: CentralityJumpDetector,
    graph_with_jump: MockGraph,
) -> None:
    session = graph_with_jump.get_session()
    alerts = await detector.run(session)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.pattern == "centrality_jump"
    assert alert.score == 0.80
    assert "node:4:1" in alert.evidence_path
    assert alert.confidence > 0
    # OPSEC: no names in explanation
    assert "4:1" in alert.explanation_id_only
    assert alert.meta["recent_edges"] == 4
    assert alert.meta["total_degree"] == 5


async def test_no_false_positive_on_clean_graph(
    detector: CentralityJumpDetector,
    graph_without_jump: MockGraph,
) -> None:
    session = graph_without_jump.get_session()
    alerts = await detector.run(session)
    assert len(alerts) == 0


async def test_confidence_scales_with_degree(
    detector: CentralityJumpDetector,
    mock_graph: MockGraph,
) -> None:
    """Higher degree nodes should get higher confidence."""
    mock_graph.set_query_result(
        "recent_fraction",
        [
            {
                "node_id": "4:low",
                "node_labels": ["Official"],
                "total_degree": 4,
                "recent_edges": 3,
                "recent_fraction": 0.75,
            },
            {
                "node_id": "4:high",
                "node_labels": ["Official"],
                "total_degree": 30,
                "recent_edges": 15,
                "recent_fraction": 0.50,
            },
        ],
    )
    session = mock_graph.get_session()
    alerts = await detector.run(session)

    assert len(alerts) == 2
    low_deg = next(a for a in alerts if a.meta["total_degree"] == 4)
    high_deg = next(a for a in alerts if a.meta["total_degree"] == 30)
    assert high_deg.confidence > low_deg.confidence
