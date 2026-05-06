"""
SACRED TEST — Groupthink Detection.

These tests verify the most critical feature of Consiglio v1:
detecting when agents agree too quickly or without considering risks.

DO NOT DELETE OR WEAKEN THESE TESTS.
"""
from __future__ import annotations

import pytest

from mata_garuda.council.consensus import (
    GROUPTHINK_CONSENSUS_THRESHOLD,
    GROUPTHINK_TIME_THRESHOLD_S,
    _detect_groupthink,
    _score_jaccard,
)
from mata_garuda.council.models import AgentVote


def _make_vote(
    name: str,
    position: str,
    elapsed: float = 20.0,
    confidence: float = 0.8,
    risks: list[str] | None = None,
) -> AgentVote:
    return AgentVote(
        agent_name=name,
        runtime="test",
        position=position,
        confidence=confidence,
        elapsed_seconds=elapsed,
        key_arguments=["arg1"],
        risks_identified=risks if risks is not None else ["risk1"],
        success=True,
    )


class TestGroupthinkDetection:
    """Test the core groupthink detection logic."""

    def test_groupthink_detected_high_consensus_fast_response(self):
        """SACRED: High consensus + fast response → groupthink."""
        detected, reason = _detect_groupthink(
            consensus_score=0.92,
            avg_response_time=15.0,
            votes=[
                _make_vote("a", "same position", elapsed=10),
                _make_vote("b", "same position", elapsed=15),
                _make_vote("c", "same position", elapsed=20),
            ],
        )
        assert detected is True
        assert "consensus" in reason
        assert "avg_time" in reason

    def test_groupthink_not_detected_moderate_consensus(self):
        """SACRED: Moderate consensus (0.70) does NOT trigger groupthink."""
        detected, _ = _detect_groupthink(
            consensus_score=0.70,
            avg_response_time=15.0,
            votes=[
                _make_vote("a", "position A"),
                _make_vote("b", "position B"),
            ],
        )
        assert detected is False

    def test_groupthink_not_detected_slow_response(self):
        """SACRED: High consensus but slow response does NOT trigger."""
        detected, _ = _detect_groupthink(
            consensus_score=0.92,
            avg_response_time=60.0,
            votes=[
                _make_vote("a", "same", elapsed=60),
                _make_vote("b", "same", elapsed=60),
            ],
        )
        assert detected is False

    def test_groupthink_zero_risks_detected(self):
        """SACRED: All agents with zero risks → groupthink."""
        detected, reason = _detect_groupthink(
            consensus_score=0.60,  # even moderate consensus
            avg_response_time=60.0,  # even slow
            votes=[
                _make_vote("a", "pos A", risks=[]),
                _make_vote("b", "pos B", risks=[]),
                _make_vote("c", "pos C", risks=[]),
            ],
        )
        assert detected is True
        assert "zero risks" in reason

    def test_groupthink_not_triggered_with_risks(self):
        """At least one agent with risks → no zero-risk groupthink."""
        detected, _ = _detect_groupthink(
            consensus_score=0.60,
            avg_response_time=60.0,
            votes=[
                _make_vote("a", "pos A", risks=[]),
                _make_vote("b", "pos B", risks=["some risk"]),
                _make_vote("c", "pos C", risks=[]),
            ],
        )
        assert detected is False

    def test_threshold_boundary_exact(self):
        """At exactly the threshold, should NOT trigger."""
        detected, _ = _detect_groupthink(
            consensus_score=GROUPTHINK_CONSENSUS_THRESHOLD,  # exactly 0.85
            avg_response_time=GROUPTHINK_TIME_THRESHOLD_S,  # exactly 30.0
            votes=[_make_vote("a", "x"), _make_vote("b", "y")],
        )
        assert detected is False  # strict greater-than, not >=

    def test_threshold_just_above(self):
        """Just above threshold → triggers."""
        detected, _ = _detect_groupthink(
            consensus_score=0.851,
            avg_response_time=29.9,
            votes=[_make_vote("a", "x"), _make_vote("b", "y")],
        )
        assert detected is True

    def test_single_vote_no_zero_risks_groupthink(self):
        """Single vote should not trigger zero-risks groupthink (need >= 2)."""
        detected, _ = _detect_groupthink(
            consensus_score=0.5,
            avg_response_time=60.0,
            votes=[_make_vote("a", "pos", risks=[])],
        )
        assert detected is False


class TestJaccardFallback:
    """Test Jaccard similarity scoring (used when Ollama unavailable)."""

    def test_identical_positions(self):
        votes = [
            _make_vote("a", "implement the new feature carefully"),
            _make_vote("b", "implement the new feature carefully"),
        ]
        pairs = [(votes[0], votes[1])]
        scores = _score_jaccard(pairs)
        assert scores["a_vs_b"] == 1.0

    def test_completely_different_positions(self):
        votes = [
            _make_vote("a", "strongly support migration database"),
            _make_vote("b", "absolutely reject frontend refactoring"),
        ]
        pairs = [(votes[0], votes[1])]
        scores = _score_jaccard(pairs)
        assert scores["a_vs_b"] < 0.2

    def test_partially_similar_positions(self):
        votes = [
            _make_vote("a", "refactor authentication system gradually"),
            _make_vote("b", "refactor authentication module completely"),
        ]
        pairs = [(votes[0], votes[1])]
        scores = _score_jaccard(pairs)
        assert 0.3 < scores["a_vs_b"] < 0.8

    def test_empty_positions(self):
        votes = [
            _make_vote("a", ""),
            _make_vote("b", ""),
        ]
        pairs = [(votes[0], votes[1])]
        scores = _score_jaccard(pairs)
        assert scores["a_vs_b"] == 1.0  # both empty = identical
