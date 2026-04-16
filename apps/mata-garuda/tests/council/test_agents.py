"""
Test — Agent Adapters.

Verifies that each adapter correctly wraps its CLI runtime
and produces valid AgentVote objects.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mata_garuda.council.agents import (
    ClaudeAdapter,
    DeepSeekAdapter,
    GeminiAdapter,
    OllamaAdapter,
    _parse_vote_json,
    get_default_agents,
)
from mata_garuda.council.models import Topic


def _topic() -> Topic:
    return Topic(
        id="test-1",
        title="Test",
        description="Should we do X?",
        category="operational",
    )


class TestParseVoteJson:
    """Test JSON extraction from LLM output."""

    def test_clean_json(self):
        raw = '{"position": "yes", "confidence": 0.8, "key_arguments": ["a"], "risks_identified": ["r"]}'
        result = _parse_vote_json(raw)
        assert result["position"] == "yes"
        assert result["confidence"] == 0.8

    def test_markdown_fenced_json(self):
        raw = 'Here is my answer:\n```json\n{"position": "no", "confidence": 0.3}\n```\nEnd.'
        result = _parse_vote_json(raw)
        assert result["position"] == "no"

    def test_json_in_text(self):
        raw = 'I think {"position": "maybe", "confidence": 0.5} is my answer.'
        result = _parse_vote_json(raw)
        assert result["position"] == "maybe"

    def test_invalid_json(self):
        raw = "This is not JSON at all"
        result = _parse_vote_json(raw)
        assert result == {}

    def test_empty_string(self):
        result = _parse_vote_json("")
        assert result == {}


class TestClaudeAdapter:
    """Test Claude CLI adapter."""

    def test_timeout_is_120(self):
        adapter = ClaudeAdapter()
        assert adapter._cli.timeout == 120

    @pytest.mark.asyncio
    async def test_deliberate_success(self):
        adapter = ClaudeAdapter()
        mock_result = MagicMock()
        mock_result.output = json.dumps({
            "position": "yes, do it",
            "confidence": 0.8,
            "key_arguments": ["a1"],
            "risks_identified": ["r1"],
        })
        mock_result.success = True
        mock_result.elapsed_seconds = 15.0
        mock_result.stderr = ""

        with patch.object(adapter._cli, "invoke", return_value=mock_result):
            vote = await adapter.deliberate(_topic())

        assert vote.success is True
        assert vote.agent_name == "claude"
        assert vote.position == "yes, do it"
        assert vote.confidence == 0.8

    @pytest.mark.asyncio
    async def test_deliberate_failure(self):
        adapter = ClaudeAdapter()
        mock_result = MagicMock()
        mock_result.output = ""
        mock_result.success = False
        mock_result.elapsed_seconds = 5.0
        mock_result.stderr = "rate limited"

        with patch.object(adapter._cli, "invoke", return_value=mock_result):
            vote = await adapter.deliberate(_topic())

        assert vote.success is False
        assert "rate limited" in vote.error


class TestOllamaAdapter:
    """Test Ollama adapter."""

    def test_default_model(self):
        adapter = OllamaAdapter()
        assert adapter._model == "gemma4:26b"

    @pytest.mark.asyncio
    async def test_deliberate_command_not_found(self):
        adapter = OllamaAdapter()
        with patch("mata_garuda.council.agents.subprocess.run", side_effect=FileNotFoundError):
            vote = await adapter.deliberate(_topic())

        assert vote.success is False
        assert "not found" in vote.error.lower() or "FileNotFoundError" in vote.error


class TestDeepSeekAdapter:
    """Test DeepSeek API adapter."""

    def test_no_api_key_fails(self):
        adapter = DeepSeekAdapter()
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="not set"):
                adapter._call_api("test prompt")


class TestGetDefaultAgents:
    """Test agent factory."""

    def test_returns_all_by_default(self):
        agents = get_default_agents()
        assert len(agents) == 4
        names = {a.name for a in agents}
        assert names == {"claude", "gemini", "deepseek", "ollama"}

    def test_filter_by_name(self):
        agents = get_default_agents(agents=["claude", "gemini"])
        assert len(agents) == 2

    def test_unknown_agent_skipped(self):
        agents = get_default_agents(agents=["claude", "nonexistent"])
        assert len(agents) == 1
        assert agents[0].name == "claude"
