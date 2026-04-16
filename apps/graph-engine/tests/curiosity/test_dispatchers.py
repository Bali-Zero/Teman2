"""Tests for tier dispatchers — Simple, Medium, Complex."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nuzantara_graph.curiosity.dispatchers.complex import ComplexDispatcher
from nuzantara_graph.curiosity.dispatchers.medium import MediumDispatcher
from nuzantara_graph.curiosity.dispatchers.simple import SimpleDispatcher
from nuzantara_graph.curiosity.models import ResearchEvidence


class TestSimpleDispatcher:
    """Tier 1: Ollama-based regulatory research."""

    def setup_method(self) -> None:
        self.dispatcher = SimpleDispatcher()

    @pytest.mark.asyncio
    async def test_returns_evidence_on_ollama_success(self) -> None:
        """Should return parsed evidence when Ollama responds with JSON."""
        ollama_response = json.dumps({
            "summary": "KITAS requires passport, sponsor, RPTKA.",
            "citations": ["PP 48/2021"],
            "key_facts": ["Valid for 1 year", "Fee: Rp 2M"],
            "confidence": 0.75,
        })

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": ollama_response},
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("nuzantara_graph.curiosity.dispatchers.simple.urllib.request.urlopen", return_value=mock_response):
            evidence = await self.dispatcher.dispatch("KITAS requirements", "immigration")

        assert len(evidence) == 1
        assert evidence[0].source_type == "ollama"
        assert evidence[0].confidence >= 0.5
        assert "PP 48/2021" in evidence[0].citations

    @pytest.mark.asyncio
    async def test_graceful_fallback_on_ollama_failure(self) -> None:
        """Should return template evidence when Ollama is unavailable."""
        with patch(
            "nuzantara_graph.curiosity.dispatchers.simple.urllib.request.urlopen",
            side_effect=Exception("Connection refused"),
        ):
            evidence = await self.dispatcher.dispatch("KITAS requirements", "immigration")

        assert len(evidence) == 1
        assert evidence[0].source_type == "template"
        assert evidence[0].confidence <= 0.2


class TestMediumDispatcher:
    """Tier 2: HyDE expansion + synthesis."""

    def setup_method(self) -> None:
        self.dispatcher = MediumDispatcher()

    @pytest.mark.asyncio
    async def test_generates_hyde_fragments(self) -> None:
        """Should generate HyDE fragments and synthesize."""
        hyde_response = "KITAS in Indonesia requires a valid passport and sponsor letter."
        synthesis_response = json.dumps({
            "summary": "Synthesized: KITAS requires passport + sponsor.",
            "citations": ["PP 48/2021"],
            "confidence": 0.7,
            "contradictions": [],
        })

        call_count = 0

        def mock_urlopen(req, timeout=60):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            # First calls are HyDE, last is synthesis
            content = hyde_response if call_count <= 1 else synthesis_response
            resp.read.return_value = json.dumps({
                "message": {"content": content},
            }).encode()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("nuzantara_graph.curiosity.dispatchers.medium.urllib.request.urlopen", side_effect=mock_urlopen):
            evidence = await self.dispatcher.dispatch(
                "KITAS requirements", "immigration",
                follow_up_queries=["What documents needed for KITAS?"],
            )

        assert len(evidence) >= 1
        # Should have at least 1 hyde fragment
        hyde_fragments = [e for e in evidence if e.source_type == "hyde"]
        assert len(hyde_fragments) >= 1

    @pytest.mark.asyncio
    async def test_graceful_fallback_on_hyde_failure(self) -> None:
        """Should return fallback evidence when HyDE generation fails."""
        with patch(
            "nuzantara_graph.curiosity.dispatchers.medium.urllib.request.urlopen",
            side_effect=Exception("Connection refused"),
        ):
            evidence = await self.dispatcher.dispatch("KITAS requirements", "immigration")

        assert len(evidence) == 1
        assert evidence[0].source_type == "hyde_fallback"


class TestComplexDispatcher:
    """Tier 3: Background deep research dispatch."""

    @pytest.mark.asyncio
    async def test_dispatches_to_redis_queue(self) -> None:
        """Should queue a job in Redis when available."""
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.set = AsyncMock()

        dispatcher = ComplexDispatcher(redis_client=mock_redis)
        evidence = await dispatcher.dispatch("Novel regulatory gap", "immigration")

        assert len(evidence) == 1
        assert evidence[0].source_type == "complex_async"
        assert "job_id" in evidence[0].metadata
        mock_redis.rpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_without_redis(self) -> None:
        """Should return placeholder when Redis is unavailable."""
        dispatcher = ComplexDispatcher(redis_client=None)
        evidence = await dispatcher.dispatch("Novel gap", "immigration")

        assert len(evidence) == 1
        assert evidence[0].source_type == "complex_placeholder"
        assert evidence[0].confidence <= 0.2

    @pytest.mark.asyncio
    async def test_check_result_returns_none_without_redis(self) -> None:
        """check_result should return None when Redis unavailable."""
        dispatcher = ComplexDispatcher(redis_client=None)
        result = await dispatcher.check_result("nonexistent-id")
        assert result is None
