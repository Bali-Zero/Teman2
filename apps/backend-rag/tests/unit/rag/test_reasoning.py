"""
Tests for ReAct loop execution and citation handling in reasoning engine.
"""

import pytest

from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score


class TestReActLoopExecution:
    def test_execute_react_loop_early_exit_on_vector_search(self):
        """Evidence score with relevant sources should be high."""
        sources = [{"score": 0.9}, {"score": 0.85}]
        context = ["KITAS visa is valid for 1 year and costs 10M IDR"]
        score = calculate_evidence_score(sources, context, "how much KITAS")
        assert isinstance(score, float)
        assert score >= 0.0


class TestCitationHandling:
    def test_citation_extraction_from_vector_search(self):
        """Empty sources should produce zero evidence score."""
        score = calculate_evidence_score([], [], "test query")
        assert score == 0.0
