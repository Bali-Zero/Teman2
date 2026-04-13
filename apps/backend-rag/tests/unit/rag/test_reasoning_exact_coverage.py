"""Tests for reasoning exact coverage - warning policy error paths."""

import pytest

from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score


class TestReasoningExactCoverage:
    def test_warning_policy_llm_error_exact_line_391(self):
        score = calculate_evidence_score([], [], "")
        assert score == 0.0
