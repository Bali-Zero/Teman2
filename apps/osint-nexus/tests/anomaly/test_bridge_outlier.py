"""Tests for bridge_outlier detector."""

from __future__ import annotations

import pytest

from osint_nexus.anomaly.detectors.bridge_outlier import BridgeOutlierDetector
from tests.anomaly.conftest import MockGraph


@pytest.fixture
def detector() -> BridgeOutlierDetector:
    return BridgeOutlierDetector({
        "min_community_size": 2,
        "bridge_score_threshold": 0.3,
    })


@pytest.fixture
def graph_with_bridge(mock_graph: MockGraph) -> MockGraph:
    """Graph where a node bridges 3 communities — should trigger."""
    # The pure Cypher fallback query uses network_diversity
    mock_graph.set_query_result(
        "bridge_score",
        [
            {
                "node_id": "4:bridge",
                "node_labels": ["Official"],
                "communities_bridged": 3,
                "degree": 6,
                "bridge_score": 1.22,
            },
        ],
    )
    return mock_graph


@pytest.fixture
def graph_without_bridge(mock_graph: MockGraph) -> MockGraph:
    """Graph with no bridge nodes above threshold."""
    mock_graph.set_query_result("bridge_score", [])
    return mock_graph


async def test_detects_bridge_outlier(
    detector: BridgeOutlierDetector,
    graph_with_bridge: MockGraph,
) -> None:
    session = graph_with_bridge.get_session()
    alerts = await detector.run(session)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.pattern == "bridge_outlier"
    assert alert.score > 0
    assert "node:4:bridge" in alert.evidence_path
    assert alert.meta["communities_bridged"] == 3


async def test_no_bridge_on_clean_graph(
    detector: BridgeOutlierDetector,
    graph_without_bridge: MockGraph,
) -> None:
    session = graph_without_bridge.get_session()
    alerts = await detector.run(session)
    assert len(alerts) == 0


async def test_bridge_score_normalized(
    detector: BridgeOutlierDetector,
    mock_graph: MockGraph,
) -> None:
    """Bridge score above 1.0 should be capped at 1.0 in alert.score."""
    mock_graph.set_query_result(
        "bridge_score",
        [
            {
                "node_id": "4:super",
                "node_labels": ["Official"],
                "communities_bridged": 10,
                "degree": 4,
                "bridge_score": 5.0,
            },
        ],
    )
    session = mock_graph.get_session()
    alerts = await detector.run(session)

    assert len(alerts) == 1
    assert alerts[0].score <= 1.0
