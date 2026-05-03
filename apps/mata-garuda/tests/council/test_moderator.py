"""
Test — Moderator LLM.

Tests synthesis logic and fallback behavior.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from mata_garuda.council.models import AgentVote, ConsensusResult, Dissent
from mata_garuda.council.moderator import ModeratorLLM


def _vote(name: str, position: str) -> AgentVote:
    return AgentVote(
        agent_name=name, runtime="test",
        position=position, confidence=0.7,
        key_arguments=["arg"], risks_identified=["risk"],
        elapsed_seconds=30.0, success=True,
    )


class TestModeratorParsing:
    """Test JSON parsing from moderator output."""

    def test_parse_clean_json(self):
        mod = ModeratorLLM()
        result = mod._parse_synthesis(json.dumps({
            "synthesis": "test",
            "action_items": ["a"],
            "confidence": 8,
            "requires_zero_approval": False,
            "escalation_reason": "",
        }))
        assert result["synthesis"] == "test"
        assert result["confidence"] == 8

    def test_parse_markdown_wrapped(self):
        mod = ModeratorLLM()
        raw = '```json\n{"synthesis": "wrapped", "action_items": [], "confidence": 6}\n```'
        result = mod._parse_synthesis(raw)
        assert result["synthesis"] == "wrapped"

    def test_parse_unparseable_returns_raw(self):
        mod = ModeratorLLM()
        raw = "This is just plain text without JSON"
        result = mod._parse_synthesis(raw)
        assert "synthesis" in result
        assert result["requires_zero_approval"] is True  # safety default


class TestModeratorFallback:
    """Test fallback when Ollama is unavailable."""

    def test_fallback_synthesis(self):
        mod = ModeratorLLM()
        votes = [_vote("claude", "position A"), _vote("gemini", "position B")]
        consensus = ConsensusResult(score=0.70, method="jaccard")
        result = mod._fallback_synthesis(votes, consensus, [])

        assert "[FALLBACK]" in result["synthesis"]
        assert result["requires_zero_approval"] is True
        assert result["confidence"] == 3


class TestModeratorSynthesize:
    """Test the full synthesis flow."""

    @pytest.mark.asyncio
    async def test_synthesis_with_mock_ollama(self):
        mod = ModeratorLLM()
        mock_output = json.dumps({
            "synthesis": "After review, adopt approach A",
            "action_items": ["implement A", "monitor"],
            "confidence": 8,
            "requires_zero_approval": False,
            "escalation_reason": "",
        })

        with patch.object(mod, "_invoke_ollama", return_value=mock_output):
            result = await mod.synthesize(
                topic_title="Test",
                topic_description="Should we do X?",
                votes=[_vote("claude", "A"), _vote("gemini", "B")],
                consensus=ConsensusResult(score=0.70, method="jaccard"),
                dissents=[],
            )

        assert result["synthesis"] == "After review, adopt approach A"
        assert len(result["action_items"]) == 2

    @pytest.mark.asyncio
    async def test_synthesis_includes_dissent_in_prompt(self):
        """Verify dissent is passed to the moderator prompt."""
        mod = ModeratorLLM()
        called_with_prompt = []

        def mock_invoke(prompt):
            called_with_prompt.append(prompt)
            return json.dumps({
                "synthesis": "s", "action_items": [], "confidence": 7,
                "requires_zero_approval": False, "escalation_reason": "",
            })

        with patch.object(mod, "_invoke_ollama", side_effect=mock_invoke):
            await mod.synthesize(
                topic_title="Test",
                topic_description="desc",
                votes=[_vote("claude", "A")],
                consensus=ConsensusResult(score=0.5, method="jaccard"),
                dissents=[Dissent(
                    agent_name="deepseek",
                    position="I disagree because X",
                    divergence_score=0.7,
                )],
            )

        assert len(called_with_prompt) == 1
        assert "deepseek" in called_with_prompt[0]
        assert "disagree" in called_with_prompt[0]

    @pytest.mark.asyncio
    async def test_ollama_failure_uses_fallback(self):
        mod = ModeratorLLM()
        with patch.object(mod, "_invoke_ollama", side_effect=RuntimeError("ollama down")):
            result = await mod.synthesize(
                topic_title="Test",
                topic_description="desc",
                votes=[_vote("claude", "A")],
                consensus=ConsensusResult(score=0.5, method="jaccard"),
                dissents=[],
            )

        assert "[FALLBACK]" in result["synthesis"]
