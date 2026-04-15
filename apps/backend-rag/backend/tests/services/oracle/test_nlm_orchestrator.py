"""Tests for NLM Orchestrator — unified NLM routing.

# Organo: backend-rag/oracle → produce NLMResult → consuma da orchestrator_core
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.oracle.nlm_orchestrator import (
    DOMAIN_NOTEBOOK_MAP_V2,
    NLMOrchestrator,
    NLMResult,
)


class TestNLMOrchestrator:
    """NLM Orchestrator routes to correct notebooks, handles failures."""

    def setup_method(self) -> None:
        self.mock_enrichment = AsyncMock()
        self.mock_cache = AsyncMock()
        self.mock_redis = AsyncMock()
        self.orch = NLMOrchestrator(
            enrichment_service=self.mock_enrichment,
            cache_service=self.mock_cache,
            redis_client=self.mock_redis,
        )

    # ── Single notebook queries ──

    @pytest.mark.asyncio
    async def test_visa_query_routes_to_nb2(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = {
            "answer": "KITAS requires RPTKA",
            "citations": [{"source": "nb-2"}],
        }

        result = await self.orch.query("What is KITAS?", domain="visa")

        assert result is not None
        assert result.answer == "KITAS requires RPTKA"
        assert result.domain == "visa"
        expected_nb = DOMAIN_NOTEBOOK_MAP_V2["visa"][0]
        self.mock_enrichment.query.assert_called_once_with(
            expected_nb, "What is KITAS?", timeout=10.0
        )

    @pytest.mark.asyncio
    async def test_tax_query_routes_to_nb4(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = {
            "answer": "PPh 21 is employee income tax",
            "citations": [],
        }

        result = await self.orch.query("What is PPh 21?", domain="tax")

        assert result is not None
        expected_nb = DOMAIN_NOTEBOOK_MAP_V2["tax"][0]
        self.mock_enrichment.query.assert_called_once_with(
            expected_nb, "What is PPh 21?", timeout=10.0
        )

    # ── Cache behavior ──

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self) -> None:
        self.mock_redis.get.return_value = None
        self.mock_cache.get.return_value = {
            "answer": "Cached KITAS answer",
            "citations": [],
        }

        result = await self.orch.query("KITAS?", domain="visa")

        assert result is not None
        assert result.cached is True
        assert result.answer == "Cached KITAS answer"
        self.mock_enrichment.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_result_cached_after_query(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = {
            "answer": "Fresh answer",
            "citations": [],
        }

        await self.orch.query("test?", domain="visa")

        self.mock_cache.set.assert_called_once()

    # ── Rate limiting ──

    @pytest.mark.asyncio
    async def test_rate_limit_reached_returns_none(self) -> None:
        self.mock_redis.get.return_value = b"10"  # at limit

        result = await self.orch.query("test?", domain="visa")

        assert result is None
        self.mock_enrichment.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_counter_incremented(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = b"5"  # under limit
        self.mock_enrichment.query.return_value = {"answer": "ok", "citations": []}

        await self.orch.query("test?", domain="visa")

        self.mock_redis.incr.assert_called_once()

    # ── Graceful degradation ──

    @pytest.mark.asyncio
    async def test_enrichment_unavailable_returns_none(self) -> None:
        self.mock_cache.get.return_value = None
        self.mock_redis.get.return_value = None
        self.mock_enrichment.query.return_value = None

        result = await self.orch.query("test?", domain="visa")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_enrichment_service_returns_none(self) -> None:
        orch = NLMOrchestrator()
        result = await orch.query("test?", domain="visa")
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_domain_returns_none(self) -> None:
        self.mock_redis.get.return_value = None
        result = await self.orch.query("test?", domain="unknown_domain")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_failure_still_works(self) -> None:
        """Redis failure → fail-open, proceed with query."""
        self.mock_cache.get.return_value = None
        self.mock_redis.get.side_effect = Exception("Redis down")
        self.mock_enrichment.query.return_value = {"answer": "ok", "citations": []}

        result = await self.orch.query("test?", domain="visa")

        assert result is not None
        assert result.answer == "ok"

    # ── Domain coverage ──

    def test_expanded_domain_coverage(self) -> None:
        """Verify 7+ domains are mapped."""
        assert len(DOMAIN_NOTEBOOK_MAP_V2) >= 7
        for domain in ["visa", "immigration", "tax", "legal", "company", "kbli", "property"]:
            assert domain in DOMAIN_NOTEBOOK_MAP_V2, f"Missing domain: {domain}"

    # ── NLMResult dataclass ──

    def test_nlm_result_defaults(self) -> None:
        result = NLMResult()
        assert result.answer == ""
        assert result.citations == []
        assert result.cached is False
        assert result.synthesis == ""
