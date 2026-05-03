"""Tests for temporal_burst detector."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from osint_nexus.anomaly.detectors.temporal_burst import TemporalBurstDetector
from tests.anomaly.conftest import MockGraph, MockResult


class MockDate:
    """Minimal mock for Neo4j date objects."""

    def __init__(self, year: int, month: int, day: int) -> None:
        self.year = year
        self.month = month
        self.day = day

    def to_native(self):
        from datetime import date

        return date(self.year, self.month, self.day)


@pytest.fixture
def detector() -> TemporalBurstDetector:
    return TemporalBurstDetector({
        "window_days": 7,
        "ewma_span_days": 30,
        "z_threshold": 3.0,
        "min_baseline_days": 14,
        "edge_types": ["MET_WITH"],
    })


def _build_burst_graph() -> AsyncMock:
    """Build a session that returns a clear temporal burst.

    Steady 1 edge/day for 30 days, then 15 edges on day 31.
    """
    records = []
    # 30 days of steady activity: 1 edge per day
    for day in range(1, 31):
        records.append({
            "edge_type": "MET_WITH",
            "edge_date": MockDate(2026, 1, day),
            "rel_ids": [f"5:{day}"],
        })
    # Burst: 15 edges on day 31
    records.append({
        "edge_type": "MET_WITH",
        "edge_date": MockDate(2026, 1, 31),
        "rel_ids": [f"5:burst_{i}" for i in range(15)],
    })

    session = AsyncMock()

    async def mock_run(query: str, parameters: dict | None = None):
        if "edge_types" in query.lower() or "type(r)" in query.lower():
            return MockResult(records)
        return MockResult([])

    session.run = mock_run
    return session


def _build_steady_graph() -> AsyncMock:
    """Build a session with steady activity — no burst."""
    records = []
    for day in range(1, 31):
        records.append({
            "edge_type": "MET_WITH",
            "edge_date": MockDate(2026, 1, day),
            "rel_ids": [f"5:{day}"],
        })

    session = AsyncMock()

    async def mock_run(query: str, parameters: dict | None = None):
        if "edge_types" in query.lower() or "type(r)" in query.lower():
            return MockResult(records)
        return MockResult([])

    session.run = mock_run
    return session


async def test_detects_temporal_burst(detector: TemporalBurstDetector) -> None:
    session = _build_burst_graph()
    alerts = await detector.run(session)

    assert len(alerts) >= 1
    burst_alert = alerts[0]
    assert burst_alert.pattern == "temporal_burst"
    assert burst_alert.score > 0
    assert burst_alert.meta["edge_type"] == "MET_WITH"
    assert burst_alert.meta["z_score"] >= 3.0
    # OPSEC: explanation uses edge type, not names
    assert "MET_WITH" in burst_alert.explanation_id_only


async def test_no_burst_on_steady_graph(detector: TemporalBurstDetector) -> None:
    session = _build_steady_graph()
    alerts = await detector.run(session)
    # Steady 1/day should not trigger z>3
    assert len(alerts) == 0


async def test_ewma_baseline_requires_min_days() -> None:
    """Detector with min_baseline=30 should not fire on 15 days of data."""
    detector = TemporalBurstDetector({
        "window_days": 7,
        "ewma_span_days": 30,
        "z_threshold": 3.0,
        "min_baseline_days": 30,
        "edge_types": ["MET_WITH"],
    })

    records = []
    for day in range(1, 15):
        records.append({
            "edge_type": "MET_WITH",
            "edge_date": MockDate(2026, 1, day),
            "rel_ids": [f"5:{day}"],
        })
    # Big spike at day 14 but not enough baseline
    records.append({
        "edge_type": "MET_WITH",
        "edge_date": MockDate(2026, 1, 15),
        "rel_ids": [f"5:spike_{i}" for i in range(20)],
    })

    session = AsyncMock()

    async def mock_run(query: str, parameters: dict | None = None):
        if "edge_types" in query.lower() or "type(r)" in query.lower():
            return MockResult(records)
        return MockResult([])

    session.run = mock_run
    alerts = await detector.run(session)
    assert len(alerts) == 0
