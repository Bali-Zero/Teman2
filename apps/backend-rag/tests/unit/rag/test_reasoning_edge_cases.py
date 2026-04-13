"""Tests for reasoning engine edge cases."""

import pytest

from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score


class TestReasoningEdgeCases:
    def test_early_exit_on_vector_search_sufficient_context(self):
        sources = [{"score": 0.9}, {"score": 0.85}]
        context = ["KITAS visa costs 10M IDR", "KITAS is valid for 1 year"]
        score = calculate_evidence_score(sources, context, "how much does KITAS cost")
        assert score > 0.0
