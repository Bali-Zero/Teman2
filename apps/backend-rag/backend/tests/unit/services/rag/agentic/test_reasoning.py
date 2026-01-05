"""
Unit tests for reasoning module
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agentic.reasoning import (
    _validate_context_quality,
    calculate_evidence_score,
    is_valid_tool_call,
)
from services.tools.definitions import ToolCall


class TestReasoningHelpers:
    """Tests for reasoning helper functions"""

    def test_is_valid_tool_call_valid(self):
        """Test validating valid tool call"""
        tool_call = ToolCall(tool_name="test_tool", arguments={"param": "value"})
        assert is_valid_tool_call(tool_call) is True

    def test_is_valid_tool_call_none(self):
        """Test validating None tool call"""
        assert is_valid_tool_call(None) is False

    def test_is_valid_tool_call_no_name(self):
        """Test validating tool call without name"""
        tool_call = MagicMock()
        tool_call.tool_name = None
        tool_call.arguments = {}
        assert is_valid_tool_call(tool_call) is False

    def test_is_valid_tool_call_no_arguments(self):
        """Test validating tool call without arguments"""
        tool_call = MagicMock()
        tool_call.tool_name = "test_tool"
        tool_call.arguments = None
        assert is_valid_tool_call(tool_call) is False

    def test_is_valid_tool_call_empty_arguments(self):
        """Test validating tool call with empty arguments"""
        tool_call = ToolCall(tool_name="test_tool", arguments={})
        assert is_valid_tool_call(tool_call) is True

    def test_calculate_evidence_score_no_sources(self):
        """Test calculating evidence score with no sources"""
        score = calculate_evidence_score(sources=None, context_gathered=[], query="test query")
        assert 0.0 <= score <= 1.0

    def test_calculate_evidence_score_with_sources(self):
        """Test calculating evidence score with sources"""
        sources = [
            {"score": 0.8, "text": "Source 1"},
            {"score": 0.6, "text": "Source 2"},
            {"score": 0.4, "text": "Source 3"},
            {"score": 0.5, "text": "Source 4"},
            {"score": 0.3, "text": "Source 5"},
        ]
        score = calculate_evidence_score(sources=sources, context_gathered=[], query="test query")
        assert 0.0 <= score <= 1.0

    def test_calculate_evidence_score_high_quality(self):
        """Test calculating evidence score with high quality sources"""
        sources = [{"score": 0.9, "text": "Source 1"}, {"score": 0.8, "text": "Source 2"}]
        score = calculate_evidence_score(sources=sources, context_gathered=[], query="test query")
        assert score >= 0.5  # Should have base score from high quality sources

    def test_calculate_evidence_score_with_context(self):
        """Test calculating evidence score with context"""
        context = ["This is a test context with relevant information"]
        score = calculate_evidence_score(sources=None, context_gathered=context, query="test query")
        assert 0.0 <= score <= 1.0

    def test_calculate_evidence_score_keyword_match(self):
        """Test calculating evidence score with keyword match"""
        context = ["This is a test context with relevant information about the query"]
        score = calculate_evidence_score(
            sources=None, context_gathered=context, query="relevant information"
        )
        assert 0.0 <= score <= 1.0

    def test_validate_context_quality(self):
        """Test validating context quality"""
        score = _validate_context_quality(
            query="test query", context_items=["This is test context"]
        )
        assert 0.0 <= score <= 1.0

    def test_validate_context_quality_empty(self):
        """Test validating empty context quality"""
        score = _validate_context_quality(query="test query", context_items=[])
        assert 0.0 <= score <= 1.0

