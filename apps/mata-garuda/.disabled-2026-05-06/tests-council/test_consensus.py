"""
Test — Consensus Scoring.

Tests both LLM-as-judge and Jaccard fallback scoring paths.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from mata_garuda.council.consensus import (
    _score_jaccard,
    _tokenize,
    score_consensus,
)
from mata_garuda.council.models import AgentVote


def _vote(name: str, position: str, elapsed: float = 30.0) -> AgentVote:
    return AgentVote(
        agent_name=name, runtime="test",
        position=position, confidence=0.7,
        key_arguments=["a"], risks_identified=["r"],
        elapsed_seconds=elapsed, success=True,
    )


class TestTokenize:
    """Test text tokenization for Jaccard."""

    def test_removes_stopwords(self):
        tokens = _tokenize("the quick brown fox is running")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens

    def test_lowercase(self):
        tokens = _tokenize("PostgreSQL Migration")
        assert "postgresql" in tokens

    def test_removes_short_words(self):
        tokens = _tokenize("a b cd efg")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" not in tokens  # <= 2 chars
        assert "efg" in tokens


class TestJaccardScoring:
    """Test Jaccard similarity computation."""

    def test_identical_texts(self):
        scores = _score_jaccard([
            (_vote("a", "implement feature"), _vote("b", "implement feature")),
        ])
        assert scores["a_vs_b"] == 1.0

    def test_disjoint_texts(self):
        scores = _score_jaccard([
            (_vote("a", "database migration planning"), _vote("b", "frontend redesign colors")),
        ])
        assert scores["a_vs_b"] < 0.15

    def test_three_agents_pairwise(self):
        votes = [
            _vote("a", "refactor auth system"),
            _vote("b", "refactor auth module"),
            _vote("c", "keep current auth"),
        ]
        import itertools
        pairs = list(itertools.combinations(votes, 2))
        scores = _score_jaccard(pairs)
        assert len(scores) == 3
        # a and b should agree more than a and c
        assert scores["a_vs_b"] > scores["a_vs_c"]


class TestScoreConsensus:
    """Test the main score_consensus function."""

    def test_single_vote(self):
        result = asyncio.run(score_consensus([_vote("a", "pos")]))
        assert result.score == 1.0

    def test_empty_votes(self):
        result = asyncio.run(score_consensus([]))
        assert result.score == 0.0

    def test_falls_back_to_jaccard_when_ollama_unavailable(self):
        votes = [_vote("a", "position"), _vote("b", "different view")]
        with patch("mata_garuda.council.consensus._score_llm_judge", side_effect=RuntimeError("ollama not found")):
            result = asyncio.run(score_consensus(votes))
        assert result.method == "jaccard"

    def test_groupthink_flag_propagated(self):
        votes = [
            _vote("a", "same thing here", elapsed=10),
            _vote("b", "same thing here", elapsed=10),
        ]
        # Force Jaccard (to avoid Ollama dependency)
        with patch("mata_garuda.council.consensus._score_llm_judge", side_effect=RuntimeError):
            result = asyncio.run(score_consensus(votes))
        # Both have identical text + fast response → may trigger
        if result.score > 0.85 and result.avg_response_time < 30:
            assert result.groupthink_detected is True
