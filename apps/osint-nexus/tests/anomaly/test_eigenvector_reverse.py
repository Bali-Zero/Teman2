"""Tests for eigenvector_reverse detector."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from osint_nexus.anomaly.detectors.eigenvector_reverse import EigenvectorReverseDetector
from tests.anomaly.conftest import MockGraph, MockResult


@pytest.fixture
def detector() -> EigenvectorReverseDetector:
    return EigenvectorReverseDetector({
        "top_percentile": 0.10,
        "neighbor_max_percentile": 0.25,
        "min_neighbors": 2,
    })


def _build_lone_hub_session() -> AsyncMock:
    """Session where a high-eigenvector node has all-low neighbors.

    The fallback (no GDS) path will:
    1. Fail on gds.version() check → use pagerank proxy
    2. Run the degree-based proxy SET query
    3. Return threshold query results
    4. Return lone hub results
    """
    session = AsyncMock()
    call_count = {"n": 0}

    async def mock_run(query: str, parameters: dict | None = None):
        ql = query.lower().strip()

        # GDS check — fail to trigger fallback
        if "gds.version()" in ql:
            raise Exception("GDS not available")

        # The SET query for degree proxy — just succeed
        if "set n._anomaly_eigen" in ql:
            return MockResult([])

        # Threshold query
        if "high_threshold" in ql and "low_threshold" in ql and "collect(score)" in ql:
            return MockResult([{
                "high_threshold": 0.8,
                "low_threshold": 0.1,
            }])

        # Lone hub query
        if "all(s in neighbor_scores" in ql:
            return MockResult([{
                "node_id": "4:hub",
                "node_score": 0.95,
                "num_neighbors": 5,
                "avg_neighbor_score": 0.02,
                "neighbor_ids": ["4:n1", "4:n2", "4:n3", "4:n4", "4:n5"],
            }])

        # Cleanup
        if "remove n._anomaly_eigen" in ql:
            return MockResult([])

        return MockResult([])

    session.run = mock_run
    return session


def _build_no_anomaly_session() -> AsyncMock:
    """Session with no lone hubs."""
    session = AsyncMock()

    async def mock_run(query: str, parameters: dict | None = None):
        ql = query.lower().strip()

        if "gds.version()" in ql:
            raise Exception("GDS not available")
        if "set n._anomaly_eigen" in ql:
            return MockResult([])
        if "high_threshold" in ql and "low_threshold" in ql and "collect(score)" in ql:
            return MockResult([{
                "high_threshold": 0.8,
                "low_threshold": 0.1,
            }])
        if "all(s in neighbor_scores" in ql:
            return MockResult([])  # No lone hubs
        if "remove n._anomaly_eigen" in ql:
            return MockResult([])
        return MockResult([])

    session.run = mock_run
    return session


async def test_detects_lone_hub(detector: EigenvectorReverseDetector) -> None:
    session = _build_lone_hub_session()
    alerts = await detector.run(session)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.pattern == "eigenvector_reverse"
    assert alert.score > 0
    assert "node:4:hub" in alert.evidence_path
    assert alert.meta["node_score"] == 0.95
    assert alert.meta["avg_neighbor_score"] == 0.02
    assert alert.meta["ratio"] > 10
    # OPSEC
    assert "4:hub" in alert.explanation_id_only


async def test_no_false_positive(detector: EigenvectorReverseDetector) -> None:
    session = _build_no_anomaly_session()
    alerts = await detector.run(session)
    assert len(alerts) == 0


async def test_score_capped_at_one(detector: EigenvectorReverseDetector) -> None:
    """Even extreme ratios should produce score <= 1.0."""
    session = _build_lone_hub_session()
    alerts = await detector.run(session)
    for alert in alerts:
        assert alert.score <= 1.0
