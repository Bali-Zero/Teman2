"""Tests for CuriosityGrader — evidence validation for KG proposals."""
from __future__ import annotations

import pytest

from nuzantara_graph.curiosity.grader import (
    CuriosityGrader,
    MORE_RESEARCH_THRESHOLD,
    PROPOSE_THRESHOLD,
)
from nuzantara_graph.curiosity.models import ResearchEvidence


class TestCuriosityGrader:
    """Test CuriosityGrader scoring and decisions."""

    def setup_method(self) -> None:
        self.grader = CuriosityGrader()

    def test_good_evidence_proposes(self, good_evidence: list[ResearchEvidence]) -> None:
        """Good evidence with citations should score >= 0.60 → propose."""
        result = self.grader.grade(
            gap_topic="KITAS requirements",
            domain="immigration",
            evidence=good_evidence,
        )
        assert result.score >= PROPOSE_THRESHOLD
        assert result.decision == "propose"

    def test_weak_evidence_abstains(self, weak_evidence: list[ResearchEvidence]) -> None:
        """Weak evidence (too short, no citations) should score < 0.15 → abstain."""
        result = self.grader.grade(
            gap_topic="KITAS requirements",
            domain="immigration",
            evidence=weak_evidence,
        )
        assert result.score < MORE_RESEARCH_THRESHOLD
        assert result.decision == "abstain"

    def test_marginal_evidence_more_research(self, marginal_evidence: list[ResearchEvidence]) -> None:
        """Marginal evidence should score 0.15-0.60 → more_research."""
        result = self.grader.grade(
            gap_topic="KITAS requirements",
            domain="immigration",
            evidence=marginal_evidence,
        )
        assert MORE_RESEARCH_THRESHOLD <= result.score < PROPOSE_THRESHOLD
        assert result.decision == "more_research"

    def test_empty_evidence_abstains(self) -> None:
        """Empty evidence list should always abstain."""
        result = self.grader.grade(
            gap_topic="any topic",
            domain="any",
            evidence=[],
        )
        assert result.score == 0.0
        assert result.decision == "abstain"
        assert "No evidence" in result.reason

    def test_multiple_good_evidence_higher_score(self) -> None:
        """Multiple high-quality evidence should boost score."""
        evidence = [
            ResearchEvidence(
                content="PP 48/2021 regulates KITAS applications. " * 5,
                source_type="ollama",
                citations=["PP 48/2021"],
                confidence=0.8,
            ),
            ResearchEvidence(
                content="Permenkumham No 22/2023 updated the requirements. " * 5,
                source_type="ollama",
                citations=["Permenkumham 22/2023"],
                confidence=0.7,
            ),
        ]
        result = self.grader.grade(
            gap_topic="KITAS requirements",
            domain="immigration",
            evidence=evidence,
        )
        assert result.score >= PROPOSE_THRESHOLD
        assert result.decision == "propose"

    def test_score_clamped_0_1(self) -> None:
        """Score must be clamped between 0.0 and 1.0."""
        evidence = [
            ResearchEvidence(
                content="X" * 200,
                source_type="ollama",
                citations=["A", "B", "C"],
                confidence=1.5,  # Intentionally over 1.0
            ),
        ]
        result = self.grader.grade("test", "test", evidence)
        assert 0.0 <= result.score <= 1.0

    def test_citation_quality_affects_score(self) -> None:
        """Evidence with citations should score higher than without."""
        base_content = "KITAS requires passport, sponsor letter, RPTKA approval. " * 3

        with_citations = ResearchEvidence(
            content=base_content,
            source_type="ollama",
            citations=["PP 48/2021"],
            confidence=0.6,
        )
        without_citations = ResearchEvidence(
            content=base_content,
            source_type="ollama",
            citations=[],
            confidence=0.6,
        )

        score_with = self.grader.grade("test", "immigration", [with_citations]).score
        score_without = self.grader.grade("test", "immigration", [without_citations]).score

        assert score_with > score_without
