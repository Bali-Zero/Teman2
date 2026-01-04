"""
Tests for Reasoning Engine context validation.

Tests the new error handling features:
- Context quality validation
- Threshold for relevance score
- Fallback if context insufficient
"""

import pytest

from backend.services.rag.agentic.reasoning import ReasoningEngine, _validate_context_quality


@pytest.fixture
def reasoning_engine():
    """Create ReasoningEngine instance for testing."""
    return ReasoningEngine(tool_map={})


def test_validate_context_quality_empty_context():
    """Test that empty context returns 0.0."""
    score = _validate_context_quality("test query", [])
    assert score == 0.0


def test_validate_context_quality_low_quality(reasoning_engine):
    """Test that low quality context returns low score."""
    low_quality_context = ["unrelated text", "another unrelated"]
    score = reasoning_engine._validate_context_quality("test query", low_quality_context)
    assert score < 0.5


def test_validate_context_quality_high_quality(reasoning_engine):
    """Test that high quality context returns high score."""
    high_quality_context = ["test query result", "query test answer"]
    score = reasoning_engine._validate_context_quality("test query", high_quality_context)
    assert score >= 0.3  # Should be above minimum threshold


def test_validate_context_quality_keyword_matching(reasoning_engine):
    """Test that context with matching keywords gets higher score."""
    query = "Indonesia visa requirements"
    context_with_keywords = [
        "Indonesia visa requirements are complex",
        "You need a visa for Indonesia",
        "Requirements for Indonesia visa",
    ]
    score = reasoning_engine._validate_context_quality(query, context_with_keywords)
    assert score > 0.3


def test_validate_context_quality_item_count_penalty(reasoning_engine):
    """Test that more items improve score."""
    query = "test"
    single_item = ["test result"]
    multiple_items = ["test result", "test answer", "test info", "test data", "test details"]

    single_score = reasoning_engine._validate_context_quality(query, single_item)
    multiple_score = reasoning_engine._validate_context_quality(query, multiple_items)

    # More items should generally improve score (up to a point)
    assert multiple_score >= single_score


def test_reasoning_engine_has_min_context_quality_score(reasoning_engine):
    """Test that ReasoningEngine has min_context_quality_score attribute."""
    assert hasattr(reasoning_engine, "_min_context_quality_score")
    assert reasoning_engine._min_context_quality_score == 0.3


def test_reasoning_engine_has_min_context_items(reasoning_engine):
    """Test that ReasoningEngine has min_context_items attribute."""
    assert hasattr(reasoning_engine, "_min_context_items")
    assert reasoning_engine._min_context_items == 1
