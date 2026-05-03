"""Tests for reasoning edge case fixes."""

import pytest

from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score


class TestCalculateEvidenceScoreCoverage:
    def test_sources_with_low_scores(self):
        sources = [{"score": 0.1}, {"score": 0.05}]
        score = calculate_evidence_score(sources, ["unrelated"], "KITAS visa")
        assert score < 0.6
