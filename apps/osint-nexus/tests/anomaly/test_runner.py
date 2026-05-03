"""Tests for the AnomalyRunner — orchestration, dedup, ranking."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector
from osint_nexus.anomaly.runner import AnomalyRunner
from tests.anomaly.conftest import MockResult


# ── Test Detectors ──


class AlwaysFireDetector(Detector):
    """Detector that always produces 2 alerts."""

    pattern_name = "always_fire"

    async def run(self, session: AsyncMock) -> list[Alert]:
        return [
            Alert(
                pattern=self.pattern_name,
                score=0.8,
                evidence_path=["node:4:1", "node:4:2"],
                explanation_id_only="Test alert A",
                confidence=0.9,
            ),
            Alert(
                pattern=self.pattern_name,
                score=0.3,
                evidence_path=["node:4:3"],
                explanation_id_only="Test alert B",
                confidence=0.5,
            ),
        ]


class DuplicateDetector(Detector):
    """Detector that produces an alert with same evidence as AlwaysFireDetector."""

    pattern_name = "always_fire"  # Same pattern = same dedup_key

    async def run(self, session: AsyncMock) -> list[Alert]:
        return [
            Alert(
                pattern=self.pattern_name,
                score=0.9,  # Higher score — should win dedup
                evidence_path=["node:4:1", "node:4:2"],
                explanation_id_only="Duplicate of A with higher score",
                confidence=0.95,
            ),
        ]


class NeverFireDetector(Detector):
    """Detector that produces no alerts."""

    pattern_name = "never_fire"

    async def run(self, session: AsyncMock) -> list[Alert]:
        return []


class FailingDetector(Detector):
    """Detector that raises an exception."""

    pattern_name = "failing"

    async def run(self, session: AsyncMock) -> list[Alert]:
        raise RuntimeError("Detector crashed")


# ── Tests ──


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()

    async def mock_run(query: str, parameters: dict | None = None):
        return MockResult([])

    session.run = mock_run
    return session


async def test_runner_collects_from_multiple_detectors(
    mock_session: AsyncMock,
) -> None:
    runner = AnomalyRunner(
        detectors=[AlwaysFireDetector(), NeverFireDetector()]
    )
    alerts = await runner.run_all(mock_session)
    assert len(alerts) == 2


async def test_dedup_keeps_higher_score(mock_session: AsyncMock) -> None:
    runner = AnomalyRunner(
        detectors=[AlwaysFireDetector(), DuplicateDetector()]
    )
    alerts = await runner.run_all(mock_session)

    # AlwaysFireDetector produces 2 alerts (A at 0.8 + B at 0.3)
    # DuplicateDetector produces 1 alert (dup of A at 0.9)
    # Dedup should keep the 0.9 score version of A + B
    dedup_keys = [a.dedup_key for a in alerts]
    assert len(dedup_keys) == len(set(dedup_keys)), "Dedup keys must be unique"

    # The surviving A-equivalent should have score 0.9 (from DuplicateDetector)
    high_score = next(
        a for a in alerts if set(a.evidence_path) == {"node:4:1", "node:4:2"}
    )
    assert high_score.score == 0.9


async def test_ranking_is_stable(mock_session: AsyncMock) -> None:
    runner = AnomalyRunner(detectors=[AlwaysFireDetector()])
    alerts = await runner.run_all(mock_session)

    # Should be sorted by score * confidence descending
    weighted = [a.score * a.confidence for a in alerts]
    assert weighted == sorted(weighted, reverse=True)


async def test_failing_detector_does_not_crash_runner(
    mock_session: AsyncMock,
) -> None:
    runner = AnomalyRunner(
        detectors=[FailingDetector(), AlwaysFireDetector()]
    )
    alerts = await runner.run_all(mock_session)
    # FailingDetector crashes but AlwaysFireDetector still runs
    assert len(alerts) == 2


async def test_to_dict_serialization(mock_session: AsyncMock) -> None:
    runner = AnomalyRunner(detectors=[AlwaysFireDetector()])
    alerts = await runner.run_all(mock_session)
    dicts = runner.to_dict(alerts)

    assert len(dicts) == 2
    for d in dicts:
        assert "id" in d
        assert "pattern" in d
        assert "score" in d
        assert "confidence" in d
        assert "evidence_path" in d
        assert "explanation" in d
        assert isinstance(d["score"], float)
