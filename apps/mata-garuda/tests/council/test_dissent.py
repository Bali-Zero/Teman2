"""
SACRED TEST — Dissent Aggregation.

These tests verify that minority positions are correctly identified,
preserved, and surfaced to the moderator.

DO NOT DELETE OR WEAKEN THESE TESTS.
"""
from __future__ import annotations

import pytest

from mata_garuda.council.models import AgentVote, ConsensusResult, Dissent
from mata_garuda.council.orchestrator import CouncilOrchestrator


def _make_vote(name: str, position: str, **kwargs) -> AgentVote:
    return AgentVote(
        agent_name=name,
        runtime="test",
        position=position,
        confidence=kwargs.get("confidence", 0.7),
        key_arguments=kwargs.get("key_arguments", ["arg"]),
        risks_identified=kwargs.get("risks", ["risk"]),
        elapsed_seconds=kwargs.get("elapsed", 30.0),
        success=True,
    )


class TestDissentIdentification:
    """Test that dissenting positions are correctly identified."""

    def setup_method(self):
        self.orch = CouncilOrchestrator.__new__(CouncilOrchestrator)

    def test_dissent_identified_below_threshold(self):
        """SACRED: Agent with pairwise score < 0.50 is flagged as dissent."""
        votes = [
            _make_vote("claude", "migrate to PostgreSQL"),
            _make_vote("gemini", "migrate to PostgreSQL"),
            _make_vote("deepseek", "keep SQLite, migration is unnecessary"),
        ]

        consensus = ConsensusResult(
            score=0.55,
            method="jaccard",
            pairwise_scores={
                "claude_vs_gemini": 0.90,
                "claude_vs_deepseek": 0.20,
                "gemini_vs_deepseek": 0.25,
            },
        )

        dissents = self.orch._identify_dissents(votes, consensus)

        assert len(dissents) == 1
        assert dissents[0].agent_name == "deepseek"
        assert dissents[0].divergence_score > 0.5

    def test_no_dissent_when_unanimous(self):
        """SACRED: No dissents when all agents agree above 0.80."""
        votes = [
            _make_vote("claude", "refactor the auth"),
            _make_vote("gemini", "refactor the auth"),
            _make_vote("deepseek", "refactor the auth"),
        ]

        consensus = ConsensusResult(
            score=0.90,
            method="jaccard",
            pairwise_scores={
                "claude_vs_gemini": 0.88,
                "claude_vs_deepseek": 0.85,
                "gemini_vs_deepseek": 0.90,
            },
        )

        dissents = self.orch._identify_dissents(votes, consensus)
        assert len(dissents) == 0

    def test_multiple_dissents(self):
        """Two agents can dissent from a third."""
        votes = [
            _make_vote("claude", "approach A"),
            _make_vote("gemini", "approach B"),
            _make_vote("deepseek", "approach C"),
        ]

        consensus = ConsensusResult(
            score=0.30,
            method="jaccard",
            pairwise_scores={
                "claude_vs_gemini": 0.30,
                "claude_vs_deepseek": 0.25,
                "gemini_vs_deepseek": 0.35,
            },
        )

        dissents = self.orch._identify_dissents(votes, consensus)
        # All agents have avg agreement < 0.50, so all dissent
        assert len(dissents) == 3

    def test_dissent_with_empty_pairwise(self):
        """No dissents when pairwise scores are empty."""
        votes = [_make_vote("claude", "pos")]
        consensus = ConsensusResult(score=1.0, method="jaccard")
        dissents = self.orch._identify_dissents(votes, consensus)
        assert len(dissents) == 0

    def test_dissent_preserves_position_text(self):
        """SACRED: Dissent object contains the agent's full position."""
        votes = [
            _make_vote("claude", "yes, migrate immediately"),
            _make_vote("gemini", "yes, migrate soon"),
            _make_vote("deepseek", "no, migration is premature and risky"),
        ]

        consensus = ConsensusResult(
            score=0.55,
            method="jaccard",
            pairwise_scores={
                "claude_vs_gemini": 0.85,
                "claude_vs_deepseek": 0.15,
                "gemini_vs_deepseek": 0.20,
            },
        )

        dissents = self.orch._identify_dissents(votes, consensus)
        assert len(dissents) == 1
        assert "premature" in dissents[0].position
        assert "risky" in dissents[0].position
