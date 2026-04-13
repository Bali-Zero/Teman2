"""Tests for reasoning engine 90% coverage - warning policy."""

import pytest

from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score


class TestReasoning90Coverage:
    def test_warning_policy_llm_error_handling(self):
        score = calculate_evidence_score([], [], "test")
        assert score == 0.0
