"""Tests for angkatan_disjoint_alliance detector."""

from __future__ import annotations

import pytest

from osint_nexus.anomaly.detectors.angkatan_disjoint import AngkatanDisjointDetector
from tests.anomaly.conftest import MockGraph


@pytest.fixture
def detector() -> AngkatanDisjointDetector:
    return AngkatanDisjointDetector({
        "max_path_length": 3,
        "non_official_edge_types": [
            "MARRIED_TO",
            "PARENT_OF",
            "SIBLING_OF",
            "PATRON_OF",
        ],
        "min_angkatan_gap": 1,
    })


@pytest.fixture
def graph_with_alliance(mock_graph: MockGraph) -> MockGraph:
    """Two officials from angkatan 2001 and 2010 connected by 2-hop family path."""
    mock_graph.set_query_result(
        "shortestpath",
        [
            {
                "node_a_id": "4:off1",
                "angkatan_a": "2001",
                "node_b_id": "4:off2",
                "angkatan_b": "2010",
                "path_length": 2,
                "edge_types": ["MARRIED_TO", "PARENT_OF"],
                "path_node_ids": ["4:off1", "4:bridge", "4:off2"],
            },
        ],
    )
    return mock_graph


@pytest.fixture
def graph_without_alliance(mock_graph: MockGraph) -> MockGraph:
    """No cross-angkatan short paths exist."""
    mock_graph.set_query_result("shortestpath", [])
    return mock_graph


async def test_detects_cross_angkatan_alliance(
    detector: AngkatanDisjointDetector,
    graph_with_alliance: MockGraph,
) -> None:
    session = graph_with_alliance.get_session()
    alerts = await detector.run(session)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.pattern == "angkatan_disjoint_alliance"
    assert alert.score == 0.5  # 1/path_length = 1/2
    assert len(alert.evidence_path) == 3  # 3 nodes in path
    assert alert.meta["angkatan_a"] == "2001"
    assert alert.meta["angkatan_b"] == "2010"
    assert alert.meta["angkatan_gap"] == 9
    # OPSEC: only IDs in explanation
    assert "4:off1" in alert.explanation_id_only
    assert "4:off2" in alert.explanation_id_only


async def test_no_false_positive_clean_graph(
    detector: AngkatanDisjointDetector,
    graph_without_alliance: MockGraph,
) -> None:
    session = graph_without_alliance.get_session()
    alerts = await detector.run(session)
    assert len(alerts) == 0


async def test_confidence_higher_for_bigger_gap(
    detector: AngkatanDisjointDetector,
    mock_graph: MockGraph,
) -> None:
    """Wider angkatan gap should produce higher confidence."""
    mock_graph.set_query_result(
        "shortestpath",
        [
            {
                "node_a_id": "4:a",
                "angkatan_a": "2001",
                "node_b_id": "4:b",
                "angkatan_b": "2003",
                "path_length": 2,
                "edge_types": ["MARRIED_TO", "SIBLING_OF"],
                "path_node_ids": ["4:a", "4:x", "4:b"],
            },
            {
                "node_a_id": "4:c",
                "angkatan_a": "1995",
                "node_b_id": "4:d",
                "angkatan_b": "2015",
                "path_length": 2,
                "edge_types": ["PATRON_OF", "PARENT_OF"],
                "path_node_ids": ["4:c", "4:y", "4:d"],
            },
        ],
    )
    session = mock_graph.get_session()
    alerts = await detector.run(session)

    assert len(alerts) == 2
    small_gap = next(a for a in alerts if a.meta["angkatan_gap"] == 2)
    large_gap = next(a for a in alerts if a.meta["angkatan_gap"] == 20)
    assert large_gap.confidence > small_gap.confidence
